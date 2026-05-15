"""
lark-cli-bridge 配置管理
从 .env 文件读取所有配置项，支持 BRIDGE_NAME 多桥接前缀
"""

import os
import shutil
from dotenv import load_dotenv

load_dotenv()

# ── 桥接前缀 ──────────────────────────────────────────────────
# 设置 BRIDGE_NAME=opencode 则优先读取 OPENCODE_FEISHU_APP_ID 等
# 不设置则直接读取 FEISHU_APP_ID（向后兼容）
_prefix = os.environ.get("BRIDGE_NAME", "").strip().upper()
if _prefix:
    _prefix += "_"


def _env(key: str, default: str = "") -> str:
    """读取环境变量，优先 {BRIDGE_NAME}_KEY，回退 KEY"""
    if _prefix:
        val = os.environ.get(f"{_prefix}{key}")
        if val is not None:
            return val
    val = os.environ.get(key)
    if val is not None:
        return val
    return default


# ── 飞书凭证（必填）─────────────────────────────────────────
FEISHU_APP_ID = _env("FEISHU_APP_ID")
FEISHU_APP_SECRET = _env("FEISHU_APP_SECRET")

# ── CLI 工具配置（必填）─────────────────────────────────────
CLI_TYPE = _env("CLI_TYPE", "opencode")  # opencode / claude
CLI_WORK_DIR = os.path.expanduser(
    _env("CLI_WORK_DIR", os.path.expanduser("~"))
)

# ── 可选配置 ────────────────────────────────────────────────
# CLI 可执行文件路径
_OPENCODE = _env("OPENCODE_PATH") or shutil.which("opencode") or "opencode"
_CLAUDE = _env("CLAUDE_PATH") or shutil.which("claude") or "claude"


def get_cli_command() -> list[str]:
    """返回 CLI 可执行文件路径列表，根据 CLI_TYPE 决定"""
    if CLI_TYPE == "claude":
        return [_CLAUDE]
    return [_OPENCODE]


# ── opencode serve 模式配置 ─────────────────────────────────
OPENCODE_SERVE_URL = _env("OPENCODE_SERVE_URL", "")
OPENCODE_SERVE_PASSWORD = _env("OPENCODE_SERVE_PASSWORD", "")
OPENCODE_SERVE_AUTO_START = _env("OPENCODE_SERVE_AUTO_START", "true").lower() == "true"
OPENCODE_SERVE_PORT = int(_env("OPENCODE_SERVE_PORT", "4096"))

# 飞书 SDK 日志级别
LOG_LEVEL = _env("LOG_LEVEL", "INFO")

# 默认模型（仅 claude 模式有效）
DEFAULT_MODEL = _env("DEFAULT_MODEL", "")

# 流式推送间隔
STREAM_CHUNK_SIZE = int(_env("STREAM_CHUNK_SIZE", "20"))

# 上线通知接收人（留空不发送）
OWNER_OPEN_ID = _env("OWNER_OPEN_ID", "")

# 会话持久化目录（按 CLI 类型隔离）
SESSIONS_DIR = os.path.expanduser(_env("SESSIONS_DIR", f"~/.cli_lark_bridge_{CLI_TYPE}"))
