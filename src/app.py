"""Flask Web 应用：新闻展示与交互"""

import os
import re
import threading
import time
from datetime import date, datetime

from flask import Flask, jsonify, render_template, request

from . import config, models
from .collector import collect_all, set_progress_callback

app = Flask(__name__)
app.jinja_env.auto_reload = True

# 采集状态
_collecting = False
_collect_progress = []
_collect_result = None


def _background_collect():
    global _collecting, _collect_progress, _collect_result
    _collecting = True
    _collect_progress = []
    _collect_result = None

    def progress(name, status, detail):
        _collect_progress.append({
            "source": name,
            "status": status,
            "detail": detail,
            "time": datetime.now().strftime("%H:%M:%S"),
        })
    set_progress_callback(progress)

    try:
        result = collect_all()
        _collect_result = result
    except Exception as e:
        _collect_result = {"error": str(e)}
    finally:
        _collecting = False
        set_progress_callback(None)

    # 采集完成后，异步生成 AI 摘要
    try:
        _background_summarize()
    except Exception:
        pass


def _background_summarize():
    """为新采集的新闻生成 AI 摘要"""
    from . import summarizer
    articles = models.get_news_without_summary(limit=30)
    if articles:
        summarizer.batch_summarize(articles)


def start_collection():
    thread = threading.Thread(target=_background_collect, daemon=True)
    thread.start()


# ─── API Routes ────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/news")
def api_news():
    today = date.today().isoformat()
    news = models.get_news(
        date_filter=request.args.get("date") or None,
        source=request.args.get("source") or None,
        category=request.args.get("category") or None,
        read_filter=request.args.get("read") or None,
        bookmarked=request.args.get("bookmarked") == "1",
        q=request.args.get("q") or None,
        limit=int(request.args.get("limit", 200)),
        offset=int(request.args.get("offset", 0)),
    )
    return jsonify({"news": news, "total": len(news)})


@app.route("/api/news/<article_id>/read", methods=["POST"])
def api_mark_read(article_id):
    models.mark_read(article_id)
    return jsonify({"ok": True})


@app.route("/api/news/<article_id>/bookmark", methods=["POST"])
def api_toggle_bookmark(article_id):
    new_val = models.toggle_bookmark(article_id)
    return jsonify({"ok": True, "bookmarked": new_val})


@app.route("/api/filters")
def api_filters():
    return jsonify({
        "sources": models.get_sources(),
        "categories": models.get_categories(),
    })


@app.route("/api/refresh", methods=["POST"])
def api_refresh():
    if _collecting:
        return jsonify({"status": "already_running"})
    today = date.today().isoformat()
    start_collection()
    return jsonify({"status": "started", "date": today})


@app.route("/api/status")
def api_status():
    return jsonify({
        "collecting": _collecting,
        "progress": _collect_progress,
        "result": _collect_result,
    })


@app.route("/api/news/<article_id>/crawl", methods=["POST"])
def api_crawl(article_id):
    """要点总结：获取全文 + AI 分析"""
    conn = models.get_conn()
    row = conn.execute("SELECT id, url, title FROM news WHERE id = ?", (article_id,)).fetchone()
    conn.close()
    if not row:
        return jsonify({"error": "新闻不存在"}), 404

    from .crawler import crawl
    result = crawl(row["id"], row["url"], row["title"])
    return jsonify(result)


@app.route("/api/news/<article_id>/save-full", methods=["POST"])
def api_save_full(article_id):
    """爬取全文并保存为文件"""
    from .crawler import fetch_article
    conn = models.get_conn()
    row = conn.execute(
        "SELECT id, url, title, source, published_date, summary FROM news WHERE id = ?",
        (article_id,),
    ).fetchone()
    conn.close()
    if not row:
        return jsonify({"error": "新闻不存在"}), 404

    content = fetch_article(row["url"])
    if not content:
        return jsonify({"error": "无法获取文章内容"}), 400

    safe_title = re.sub(r'[\\/:*?"<>|]', '', row["title"])[:30] or "article"
    filename = f"[{row['source']}]_{row['published_date']}_{safe_title}.txt".replace(" ", "_")
    base = config.get_data_dir()
    filepath = os.path.join(base, filename)

    file_content = (
        f"标题：{row['title']}\n"
        f"来源：{row['source']}\n"
        f"日期：{row['published_date']}\n"
        f"链接：{row['url']}\n"
        f"摘要：{row['summary'] or '无'}\n"
        f"{'='*50}\n"
        f"{content}"
    )

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(file_content)

    return jsonify({"ok": True, "file": filename, "path": filepath})


@app.route("/api/stats")
def api_stats():
    today = date.today().isoformat()
    conn = models.get_conn()
    total = conn.execute("SELECT COUNT(*) as c FROM news").fetchone()["c"]
    today_count = conn.execute("SELECT COUNT(*) as c FROM news WHERE published_date = ?", (today,)).fetchone()["c"]
    unread = conn.execute("SELECT COUNT(*) as c FROM news WHERE is_read = 0").fetchone()["c"]
    bookmarked = conn.execute("SELECT COUNT(*) as c FROM news WHERE is_bookmarked = 1").fetchone()["c"]
    conn.close()
    return jsonify({
        "total": total,
        "today": today_count,
        "unread": unread,
        "bookmarked": bookmarked,
    })
