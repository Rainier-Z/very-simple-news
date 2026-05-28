# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Build & Run

```bash
# Run locally (development)
pip install -r requirements.txt
python -m src

# Package as single exe
pip install pyinstaller
python -m PyInstaller --onefile --console --name=news-collector --add-data "src/templates;src/templates" --add-data "src/static;src/static" --noconfirm src/__main__.py
# Output: dist/news-collector.exe (19MB)

# Package with API key embedded
DEEPSEEK_API_KEY="sk-xxx" python build.py

# CI builds triggered by: git tag v1.0 && git push origin v1.0
```

## Key Design Decisions

**API Key 三層注入**（config.py）:
1. 环境变量 `DEEPSEEK_API_KEY`（GitHub Actions 用）
2. `src/_secret.py`（已 gitignore，本地开发用）
3. `config.json`（运行时回退）

**中文新闻源采集**：RSS 大面积失效，改用首页爬虫兜底。每个源定义 `url_pattern` 正则过滤新闻链接。sources.py 的 `NEWS_SOURCES` 列表管理。

**PyInstaller 打包注意**：`--add-data` 目标路径必须是 `src/templates` 和 `src/static`（不是 `templates`/`static`），否则 Flask 在打包后找不到模板。

**前端**：Flask Jinja2 模板 + 原生 CSS/JS，无前端框架。明暗主题通过 `data-theme` 属性和 CSS 变量切换，偏好存 `localStorage`。

## Architecture Overview

```
src/__main__.py        入口 → 启动 Flask + 打开浏览器 + 后台采集
src/app.py             Flask API 路由 + 采集调度
src/collector.py       RSS/首页爬虫（7 个新闻源）
src/config.py          API Key 读取（env > _secret.py > config.json）
src/crawler.py         深度爬取（全文提取 + DeepSeek AI 分析）
src/models.py          SQLite CRUD + crawl_cache
src/sources.py         新闻源定义（name/rss/site/category/url_pattern）
src/summarizer.py      DeepSeek API 摘要生成
src/templates/index.html  页面模板
src/static/style.css       样式（亮色/暗色）
src/static/script.js       前端交互
.github/workflows/build.yml  CI 自动构建（推送 v* 标签触发）
```

## SQLite Schema

`news` 表：id(MD5 URL hash), title, url, source, summary, published_date, collected_at, is_read, is_bookmarked, category
`crawl_cache` 表：article_id(FK), result(JSON), created_at

App 数据（news.db, config.json, _secret.py）存于 exe 同级目录。
