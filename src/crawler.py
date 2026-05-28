"""深度爬取：抓取新闻全文并生成 AI 分析"""

import json
import re

import httpx
from bs4 import BeautifulSoup

from . import config, models

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/125.0.0.0 Safari/537.36",
}


def fetch_article(url: str) -> str | None:
    """抓取文章正文，返回纯文本（适配多种站点结构）"""
    try:
        resp = httpx.get(url, headers=HEADERS, timeout=25, follow_redirects=True, verify=False)
        resp.raise_for_status()
    except Exception:
        return None

    soup = BeautifulSoup(resp.text, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header", "aside", "noscript", "iframe", "form"]):
        tag.decompose()

    # 1. 尝试找语义化容器
    article = soup.find("article")
    if article:
        text = _extract_text(article)
        if text and len(text) > 80:
            return text[:3000]

    # 2. 尝试常见 class/id 容器
    for selector in [
        {"class": ["article", "content", "post", "main-content", "news-content",
                    "article-content", "article-main", "detail-content", "rich-content"]},
        {"id": ["content", "article", "post", "main", "news-content"]},
        {"class": "detail-content"},
    ]:
        container = soup.find(**selector)
        if container:
            text = _extract_text(container)
            if text and len(text) > 80:
                return text[:3000]

    # 3. 取所有长 p 标签
    paragraphs = soup.find_all("p")
    texts = [p.get_text(strip=True) for p in paragraphs if len(p.get_text(strip=True)) > 15]
    if texts:
        combined = "\n".join(texts)
        if len(combined) > 80:
            return combined[:3000]

    # 4. 尝试 JSON-LD / NUXT 数据中提取
    for script in soup.find_all("script"):
        content = script.string or ""
        if "window.__NUXT__" in content:
            try:
                m = re.search(r"window\.__NUXT__\s*=\s*({.*?});?\s*$", content, re.DOTALL)
                if m:
                    data = json.loads(m.group(1))
                    text = _extract_nuxt_text(data)
                    if text and len(text) > 80:
                        return text[:3000]
            except Exception:
                pass

    # 5. 兜底：所有可见文本中找最长连续段落
    all_text = soup.get_text(separator="\n", strip=True)
    lines = [l.strip() for l in all_text.split("\n") if len(l.strip()) > 20]
    if lines:
        combined = "\n".join(lines[:50])
        if len(combined) > 80:
            return combined[:3000]

    return None


def _extract_text(container) -> str:
    """从容器中提取纯文本"""
    for tag in container(["script", "style"]):
        tag.decompose()
    return container.get_text(separator="\n", strip=True)


def _extract_nuxt_text(data, depth=0) -> str:
    """从 Nuxt.js 数据中提取文本"""
    if depth > 5:
        return ""
    if isinstance(data, str):
        return data if len(data) > 20 else ""
    if isinstance(data, list):
        return "\n".join(filter(None, (_extract_nuxt_text(item, depth + 1) for item in data)))
    if isinstance(data, dict):
        # 优先查找内容字段
        for key in ["content", "text", "body", "description", "summary", "articleContent"]:
            if key in data:
                val = _extract_nuxt_text(data[key], depth + 1)
                if val and len(val) > 50:
                    return val
        return "\n".join(filter(None, (_extract_nuxt_text(v, depth + 1) for v in data.values())))
    return ""


def analyze_article(title: str, content: str) -> dict | None:
    """调用 DeepSeek 分析文章，返回结构化结果"""
    api_key = config.get_deepseek_key()
    if not api_key:
        return None

    prompt = (
        "你是一个深度新闻分析助手。分析以下新闻，返回 JSON 格式：\n"
        "{\n"
        '  "summary": "一句话核心摘要",\n'
        '  "key_points": ["要点1", "要点2", "要点3"],\n'
        '  "background": "背景信息",\n'
        '  "related_topics": ["相关话题1", "相关话题2"]\n'
        "}\n\n"
        f"标题：{title}\n正文：{content}"
    )

    payload = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": "你返回纯 JSON，不要加 markdown 标记。"},
            {"role": "user", "content": prompt},
        ],
        "max_tokens": 600,
        "temperature": 0.1,
    }

    try:
        resp = httpx.post(
            "https://api.deepseek.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json=payload,
            timeout=30,
        )
        resp.raise_for_status()
        raw = resp.json()["choices"][0]["message"]["content"]
        raw = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        return json.loads(raw)
    except Exception as e:
        print(f"[crawler] DeepSeek 分析失败: {e}")
        return None


def crawl(article_id: str, url: str, title: str) -> dict:
    """完整爬取流程：抓取 → 分析 → 缓存 → 返回"""
    cached = models.get_crawl_result(article_id)
    if cached:
        return cached

    content = fetch_article(url)
    if not content:
        return {"error": "无法获取文章内容"}

    analysis = analyze_article(title, content)
    if not analysis:
        return {"error": "AI 分析失败（请检查 DeepSeek Key 是否配置正确）"}

    result = {"content_preview": content[:300], "analysis": analysis}
    models.save_crawl_result(article_id, result)
    return result
