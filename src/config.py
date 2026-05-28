"""配置管理：DeepSeek API Key 读取

优先级：
  1. 环境变量 DEEPSEEK_API_KEY（GitHub Actions 构建时注入）
  2. secret.py（本地开发，已 gitignore）
  3. config.json（本地运行时的配置文件）
"""

import json
import os
import sys

CONFIG_FILE = "config.json"


def _get_env_key() -> str:
    return os.environ.get("DEEPSEEK_API_KEY", "") or ""


def _get_secret_key() -> str:
    try:
        from . import _secret
        return getattr(_secret, "DEEPSEEK_API_KEY", "") or ""
    except Exception:
        return ""


def _config_path():
    if getattr(sys, "frozen", False):
        base = os.path.dirname(sys.executable)
    else:
        base = os.getcwd()
    return os.path.join(base, CONFIG_FILE)


def load():
    path = _config_path()
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save(data: dict):
    path = _config_path()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def get_deepseek_key() -> str | None:
    # 1. 环境变量
    env_key = _get_env_key()
    if env_key:
        return env_key
    # 2. secret.py
    secret_key = _get_secret_key()
    if secret_key:
        return secret_key
    # 3. config.json
    return load().get("deepseek_api_key")


def is_configured() -> bool:
    return bool(get_deepseek_key())


def get_data_dir() -> str:
    return os.path.dirname(_config_path())
