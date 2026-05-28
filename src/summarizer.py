"""AI 摘要生成：调用 DeepSeek API 为新闻生成摘要"""

import json

import httpx

from . import config

API_URL = "https://api.deepseek.com/v1/chat/completions"
MODEL = "deepseek-chat"
TIMEOUT = 30.0

SUMMARY_PROMPT = "你是一个新闻摘要助手。请为以下新闻生成一段1-2句中文摘要，要求简洁客观，保留关键信息（人物、事件、数据）。不要加开头词，直接输出摘要。"


def summarize(title: str, content: str = "") -> str | None:
    """调用 DeepSeek 生成新闻摘要"""
    api_key = config.get_deepseek_key()
    if not api_key:
        return None

    # 用标题作为输入，如有正文则加上正文
    prompt_content = f"标题：{title}"
    if content:
        # 正文限制长度，避免 token 浪费
        content_truncated = content[:1000]
        prompt_content += f"\n正文：{content_truncated}"

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": SUMMARY_PROMPT},
            {"role": "user", "content": prompt_content},
        ],
        "max_tokens": 150,
        "temperature": 0.1,
    }

    try:
        resp = httpx.post(API_URL, headers=headers, json=payload, timeout=TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
        summary = data["choices"][0]["message"]["content"].strip()
        return summary
    except Exception as e:
        print(f"[summarizer] DeepSeek API 调用失败: {e}")
        return None


def batch_summarize(articles: list[dict], max_batch: int = 30) -> int:
    """为一批文章生成摘要，返回成功数"""
    success = 0
    for art in articles[:max_batch]:
        # 用正文片段作输入（如果没有摘要且有 URL，可以尝试抓取正文，但会增加复杂度）
        summary = summarize(art["title"])
        if summary:
            from . import models
            models.update_summary(art["id"], summary)
            success += 1
    return success
