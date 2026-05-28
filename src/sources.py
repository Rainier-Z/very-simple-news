"""新闻源定义

每家媒体包含：
  - name: 中文名称
  - rss: RSS 地址（可选，为空则跳过 RSS）
  - site: 首页地址（RSS 失败或无 RSS 时用作兜底爬取）
  - category: 分类
  - url_pattern: 新闻链接的正则特征（用于过滤非新闻链接）
"""

import re

NEWS_SOURCES = [
    {
        "name": "新华社",
        "rss": "",  # RSS 已失效（403）
        "site": "https://www.xinhuanet.com/",
        "category": "时政",
        "url_pattern": re.compile(r"/politics/|/local/|/world/|/news/|/2026"),
    },
    {
        "name": "人民日报",
        "rss": "http://www.people.com.cn/rss/opml.xml",
        "site": "http://www.people.com.cn/",
        "category": "时政",
        "url_pattern": re.compile(r"/n1/|/\d{4}/\d{4}/"),
    },
    {
        "name": "央视新闻",
        "rss": "",  # RSS 已失效（404）
        "site": "https://news.cctv.com/",
        "category": "时政",
        "url_pattern": re.compile(r"/2026/\d{2}/\d{2}/|/news\.cctv\.com"),
    },
    {
        "name": "澎湃新闻",
        "rss": "",  # RSS 已失效
        "site": "https://www.thepaper.cn/",
        "category": "时政",
        "url_pattern": re.compile(r"/newsDetail_forward_"),
    },
    {
        "name": "财新",
        "rss": "",  # RSS 已重定向
        "site": "https://www.caixin.com/",
        "category": "财经",
        "url_pattern": re.compile(r"/\d{4}-\d{2}-\d{2}/|/news/"),
    },
    {
        "name": "36氪",
        "rss": "https://36kr.com/feed",
        "site": "https://36kr.com/",
        "category": "科技",
        "url_pattern": re.compile(r"/p/\d+"),
    },
    {
        "name": "新浪新闻",
        "rss": "",
        "site": "https://news.sina.com.cn/",
        "category": "综合",
        "url_pattern": re.compile(r"/doc-[a-z]+", re.I),
    },
]
