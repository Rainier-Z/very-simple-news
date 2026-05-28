"""PyInstaller 打包脚本

用法：
    python build.py                   # 用 _secret.py 中的 Key
    DEEPSEEK_API_KEY=sk-xxx build.py  # 用环境变量中的 Key

输出：dist/news-collector/ （文件夹模式）
"""

import os
import sys

os.chdir(os.path.dirname(os.path.abspath(__file__)))

try:
    import PyInstaller.__main__
except ImportError:
    print("请先安装 PyInstaller: pip install pyinstaller")
    sys.exit(1)

# 从环境变量注入 Key（GitHub Actions 场景）
env_key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
if env_key:
    # 写入 _secret.py 供打包时嵌入
    secret_path = os.path.join("src", "_secret.py")
    with open(secret_path, "w", encoding="utf-8") as f:
        f.write(f'# 由 build.py 自动生成，不要手动修改\n')
        f.write(f'DEEPSEEK_API_KEY = {repr(env_key)}\n')
    print("[Build] 已从环境变量注入 DeepSeek API Key")

import src.templates as templates_mod
import src.static as static_mod

templates_dir = os.path.dirname(templates_mod.__file__)
static_dir = os.path.dirname(static_mod.__file__)

PyInstaller.__main__.run([
    "src/__main__.py",
    "--name=news-collector",
    "--onedir",
    "--console",
    f"--add-data={templates_dir}{os.pathsep}src/templates",
    f"--add-data={static_dir}{os.pathsep}src/static",
    "--clean",
    "--noconfirm",
])

print("\n[OK] 打包完成！")
print(f"[OK] 输出目录: {os.path.abspath('dist/news-collector')}")
print("[OK] 运行: dist/news-collector/news-collector.exe")
