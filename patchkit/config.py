"""路径与目标文件配置。可用环境变量覆盖：
DEVIN_APPDIR   默认 D:\\Windsurf
DEVIN_USERDATA 默认 D:\\Roaming\\devin
"""
import os
from pathlib import Path


def _p(env_key: str, default: str) -> Path:
    return Path(os.environ.get(env_key, default))


WINDSURF_DIR = _p("DEVIN_APPDIR", r"D:\Windsurf")
APP_DIR = WINDSURF_DIR / "resources" / "app"
USERDATA = _p("DEVIN_USERDATA", r"D:\Roaming\devin")

# key, 文件路径, product.json checksums 里的键（None = 不参与校验）
BUNDLES = [
    ("main", APP_DIR / "out" / "vs" / "sessions" / "sessions.desktop.main.js",
     "vs/sessions/sessions.desktop.main.js"),
    ("chat", APP_DIR / "out" / "vs" / "workbench" / "windsurf-chat-client" / "index.js",
     "vs/workbench/windsurf-chat-client/index.js"),
    ("exa", APP_DIR / "node_modules" / "@exa" / "chat-client" / "index.js",
     None),
]
BUNDLE_MAP = {k: (p, ck) for k, p, ck in BUNDLES}

PRODUCT_JSON = APP_DIR / "product.json"
BACKUP_ROOT = USERDATA / "Backups"
SHIM_PATH = USERDATA / "acp_expand_shim.py"
SNAPSHOT_KEY = "__JB_SESS"   # 渲染进程 localStorage 里的会话快照键


def workspace_pyrightconfig(workspace: str) -> Path:
    return Path(workspace) / "pyrightconfig.json"
