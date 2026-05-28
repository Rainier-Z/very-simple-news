"""简简单单的新闻 — 入口点

双击运行或 python -m src 启动后：
1. 初始化数据库
2. 启动本地 Web 服务器
3. 自动打开浏览器
4. 如已配置 Key，自动开始采集今日新闻
"""

import os
import sys
import threading
import time
import webbrowser

# 确保 src 在路径中（PyInstaller 兼容）
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import config, models
from src.app import app, start_collection, _background_summarize

PORT = 5678


def _open_browser():
    """延迟 1.5 秒打开浏览器，确保服务器已就绪"""
    time.sleep(1.5)
    webbrowser.open(f"http://localhost:{PORT}")


def _auto_start():
    """自动采集逻辑"""
    models.init_db()
    if models.count_news_today() == 0:
        start_collection()
    elif config.is_configured():
        # 后台检查是否有需要摘要的新闻
        threading.Thread(target=_background_summarize, daemon=True).start()


def main():
    models.init_db()

    # 启动浏览器
    threading.Thread(target=_open_browser, daemon=True).start()

    # 自动采集（后台线程）
    threading.Thread(target=_auto_start, daemon=True).start()

    # 打印提示（避免 Windows GBK 编码的 emoji 问题）
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print(f"[News] 简简单单的新闻已启动 => http://localhost:{PORT}")
    print("[News] 按 Ctrl+C 停止服务")

    # 启动 Flask（禁用 reloader，避免多进程问题）
    app.run(
        host="127.0.0.1",
        port=PORT,
        debug=False,
        use_reloader=False,
    )


if __name__ == "__main__":
    main()
