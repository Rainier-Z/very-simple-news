"""新闻采集器：RSS 抓取 + 首页爬虫兜底"""

from datetime import date, datetime
from typing import Optional
from urllib.parse import urljoin

import feedparser
import httpx
from bs4 import BeautifulSoup

from . import models
from .sources import NEWS_SOURCES

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "zh-CN,zh;q=0.9",
}
TIMEOUT = httpx.Timeout(20.0, connect=10.0)

_progress_callback = None


def set_progress_callback(cb):
    global _progress_callback
    _progress_callback = cb


def _report(source_name: str, status: str, detail: str = ""):
    if _progress_callback:
        _progress_callback(source_name, status, detail)


def collect_all() -> dict:
    """采集所有新闻源，返回统计信息"""
    results = {"total": 0, "new": 0, "sources": [], "errors": []}

    for src in NEWS_SOURCES:
        try:
            articles = _collect_source(src)
            if not articles:
                _report(src["name"], "skip", "无可用内容")
                continue

            new_count = 0
            for art in articles:
                if models.insert_article(art):
                    new_count += 1
            results["total"] += len(articles)
            results["new"] += new_count
            results["sources"].append({
                "name": src["name"],
                "count": len(articles),
                "new": new_count,
            })
            _report(src["name"], "ok", f"获取 {len(articles)} 条，新增 {new_count} 条")
        except Exception as e:
            err_msg = str(e)[:100]
            results["errors"].append({"source": src["name"], "error": err_msg})
            _report(src["name"], "fail", err_msg)

    return results


def _collect_source(src) -> list[dict]:
    """采集单个新闻源：RSS → 首页爬虫"""
    articles = _try_rss(src)
    if articles:
        return articles
    return _scrape_homepage(src)


# ── RSS 采集 ──────────────────────────────────────────────


def _try_rss(src) -> list[dict]:
    rss_url = src.get("rss", "").strip()
    if not rss_url:
        return []

    try:
        feed = feedparser.parse(rss_url)
    except Exception:
        return []

    if not feed.entries:
        return []

    articles = []
    for entry in feed.entries:
        link = _entry_link(entry)
        if not link:
            continue

        title = entry.get("title", "").strip()
        if not title or len(title) < 5:
            continue

        published = _parse_pub_date(
            getattr(entry, "published_parsed", None)
            or getattr(entry, "updated_parsed", None)
        )

        summary = _clean_html(
            entry.get("summary", "") or entry.get("description", "") or ""
        )
        if len(summary) > 500:
            summary = summary[:500] + "…"

        articles.append({
            "title": title,
            "url": link,
            "source": src["name"],
            "summary": summary,
            "published_date": published,
            "category": src["category"],
        })
    return articles


# ── 首页爬虫 ──────────────────────────────────────────────


def _scrape_homepage(src) -> list[dict]:
    site = src.get("site", "")
    if not site:
        return []

    try:
        resp = httpx.get(
            site,
            headers=HEADERS,
            timeout=TIMEOUT,
            follow_redirects=True,
            verify=False,
        )
        resp.raise_for_status()
    except Exception:
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    pattern = src.get("url_pattern")
    today = date.today().isoformat()
    seen = set()
    articles = []

    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        title = a.get_text(strip=True)

        # 基础过滤：标题太短或太长（导航栏）的跳过
        if not title or len(title) < 10 or len(title) > 120:
            continue

        # 用 url_pattern 过滤新闻链接
        if pattern and not pattern.search(href):
            continue

        # 补全 URL
        full_url = urljoin(str(resp.url), href)
        if not full_url.startswith("http"):
            continue

        # 去重
        if full_url in seen:
            continue
        seen.add(full_url)

        # 标题清洗：去掉开头常见的分类前缀如"滚动丨""视频丨"
        clean_title = _clean_title(title)

        articles.append({
            "title": clean_title,
            "url": full_url,
            "source": src["name"],
            "summary": "",
            "published_date": today,
            "category": src["category"],
        })

    # 限制数量，避免过多
    return articles[:30]


# ── 辅助函数 ──────────────────────────────────────────────


def _entry_link(entry) -> Optional[str]:
    link = entry.get("link", "").strip()
    if link:
        return link
    for l in entry.get("links", []):
        if l.get("rel") == "alternate":
            return l.get("href", "")
    return None


def _parse_pub_date(struct_time) -> str:
    if struct_time:
        try:
            return datetime(*struct_time[:6]).strftime("%Y-%m-%d")
        except Exception:
            pass
    return date.today().isoformat()


def _clean_html(text: str) -> str:
    if not text:
        return ""
    soup = BeautifulSoup(text, "html.parser")
    return soup.get_text(separator=" ", strip=True)


def _clean_title(title: str) -> str:
    """去掉标题开头的分类冒号前缀"""
    import re
    # 匹配 "科技丨" "滚动丨" "视频丨" 等前缀
    title = re.sub(r"^[^一-鿿]{0,6}[丨|]\s*", "", title).strip()
    return title
