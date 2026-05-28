"""数据模型和 SQLite 存储层"""

import hashlib
import sqlite3
import os
import sys
from datetime import date
from typing import Optional

DB_FILE = "news.db"


def _db_path():
    if getattr(sys, "frozen", False):
        base = os.path.dirname(sys.executable)
    else:
        base = os.getcwd()
    return os.path.join(base, DB_FILE)


def get_conn():
    conn = sqlite3.connect(_db_path())
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    conn = get_conn()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS news (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            url TEXT NOT NULL,
            source TEXT NOT NULL,
            summary TEXT DEFAULT '',
            published_date TEXT NOT NULL,
            collected_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
            is_read INTEGER DEFAULT 0,
            is_bookmarked INTEGER DEFAULT 0,
            category TEXT DEFAULT ''
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_news_date ON news(published_date DESC)
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_news_source ON news(source)
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_news_category ON news(category)
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS crawl_cache (
            article_id TEXT PRIMARY KEY,
            result TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
        )
    """)
    conn.commit()
    conn.close()


def make_id(url: str) -> str:
    return hashlib.md5(url.encode()).hexdigest()


def insert_article(article: dict) -> bool:
    """插入一篇文章。如果已存在（按 id 去重）则忽略。返回 True 表示新插入。"""
    conn = get_conn()
    try:
        aid = make_id(article["url"])
        conn.execute(
            """INSERT OR IGNORE INTO news
               (id, title, url, source, summary, published_date, category)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                aid,
                article["title"],
                article["url"],
                article["source"],
                article.get("summary", ""),
                article.get("published_date", date.today().isoformat()),
                article.get("category", ""),
            ),
        )
        conn.commit()
        return conn.total_changes > 0
    finally:
        conn.close()


def update_summary(article_id: str, summary: str):
    conn = get_conn()
    conn.execute("UPDATE news SET summary = ? WHERE id = ?", (summary, article_id))
    conn.commit()
    conn.close()


def get_news_without_summary(limit: int = 50):
    """获取需要 AI 生成摘要的新闻（summary 为空且不是空字符串占位）。"""
    conn = get_conn()
    rows = conn.execute(
        "SELECT id, title, url, source, summary FROM news WHERE summary = '' LIMIT ?",
        (limit,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_news(
    *,
    date_filter: Optional[str] = None,
    source: Optional[str] = None,
    category: Optional[str] = None,
    read_filter: Optional[str] = None,
    bookmarked: Optional[bool] = None,
    q: Optional[str] = None,
    limit: int = 200,
    offset: int = 0,
):
    """查询新闻列表，支持多种筛选条件组合。"""
    conn = get_conn()
    conditions = []
    params = []

    if date_filter:
        conditions.append("published_date = ?")
        params.append(date_filter)
    if source:
        conditions.append("source = ?")
        params.append(source)
    if category:
        conditions.append("category = ?")
        params.append(category)
    if read_filter == "unread":
        conditions.append("is_read = 0")
    elif read_filter == "read":
        conditions.append("is_read = 1")
    if bookmarked is True:
        conditions.append("is_bookmarked = 1")
    if q:
        conditions.append("(title LIKE ? OR summary LIKE ?)")
        params.extend([f"%{q}%", f"%{q}%"])

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    sql = f"SELECT * FROM news {where} ORDER BY published_date DESC, collected_at DESC LIMIT ? OFFSET ?"
    rows = conn.execute(sql, params + [limit, offset]).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def mark_read(article_id: str):
    conn = get_conn()
    conn.execute("UPDATE news SET is_read = 1 WHERE id = ?", (article_id,))
    conn.commit()
    conn.close()


def toggle_bookmark(article_id: str) -> bool:
    """切换收藏状态，返回新的收藏值。"""
    conn = get_conn()
    row = conn.execute("SELECT is_bookmarked FROM news WHERE id = ?", (article_id,)).fetchone()
    if row is None:
        conn.close()
        return False
    new_val = 0 if row["is_bookmarked"] else 1
    conn.execute("UPDATE news SET is_bookmarked = ? WHERE id = ?", (new_val, article_id))
    conn.commit()
    conn.close()
    return bool(new_val)


def get_sources() -> list[str]:
    conn = get_conn()
    rows = conn.execute("SELECT DISTINCT source FROM news ORDER BY source").fetchall()
    conn.close()
    return [r["source"] for r in rows]


def get_categories() -> list[str]:
    conn = get_conn()
    rows = conn.execute("SELECT DISTINCT category FROM news WHERE category != '' ORDER BY category").fetchall()
    conn.close()
    return [r["category"] for r in rows]


def get_date_range() -> tuple:
    """获取数据库中最早和最晚的日期"""
    conn = get_conn()
    row = conn.execute("SELECT MIN(published_date) as min_date, MAX(published_date) as max_date FROM news").fetchone()
    conn.close()
    return (row["min_date"], row["max_date"]) if row else (None, None)


def count_news_today() -> int:
    today = date.today().isoformat()
    conn = get_conn()
    cnt = conn.execute("SELECT COUNT(*) as c FROM news WHERE published_date = ?", (today,)).fetchone()["c"]
    conn.close()
    return cnt


# ─── 爬取缓存 ────────────────────────────────────────────

def get_crawl_result(article_id: str) -> dict | None:
    conn = get_conn()
    row = conn.execute(
        "SELECT result FROM crawl_cache WHERE article_id = ?", (article_id,)
    ).fetchone()
    conn.close()
    if row:
        import json
        return {"cached": True, **json.loads(row["result"])}
    return None


def save_crawl_result(article_id: str, result: dict):
    import json
    conn = get_conn()
    conn.execute(
        "INSERT OR REPLACE INTO crawl_cache (article_id, result) VALUES (?, ?)",
        (article_id, json.dumps(result, ensure_ascii=False)),
    )
    conn.commit()
    conn.close()
