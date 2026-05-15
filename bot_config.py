"""
lark-cli-bridge 配置管理
从 .env 文件读取所有配置项，支持 BRIDGE_NAME 多桥接前缀
"""

import os
import shutil
from dotenv import load_dotenv

load_dotenv()

# ── 桥接前缀 ──────────────────────────────────────────────────
# 设置 BRIDGE_NAME=opencode 则优先读取 BRIDGE_OPENCODE_FEISHU_APP_ID 等
# 不设置则直接读取 FEISHU_APP_ID（向后兼容）
_prefix = os.environ.get("BRIDGE_NAME", "").strip().upper()
if _prefix:
    _prefix = f"BRIDGE_{_prefix}_"


def _bridge_env(key: str, default: str = "") -> str:
    """桥接级变量：优先 BRIDGE_{NAME}_{KEY}，回退 KEY（向后兼容单桥接）"""
    if _prefix:
        val = os.environ.get(f"{_prefix}{key}")
        if val is not None:
            return val
    val = os.environ.get(key)
    if val is not None:
        return val
    return default


def _direct_env(key: str, default: str = "") -> str:
    """工具级/全局变量：直接读取，不受 BRIDGE_NAME 影响"""
    val = os.environ.get(key)
    if val is not None:
        return val
    return default


# ── 实例变量（受 BRIDGE_NAME 影响）─────────────────────────

# 飞书凭证（必填）
FEISHU_APP_ID = _bridge_env("FEISHU_APP_ID")
FEISHU_APP_SECRET = _bridge_env("FEISHU_APP_SECRET")

# CLI 工具选择
CLI_TYPE = _bridge_env("CLI_TYPE", "opencode")  # opencode / claude
CLI_WORK_DIR = os.path.expanduser(
    _bridge_env("CLI_WORK_DIR", os.path.expanduser("~"))
)

# 上线通知接收人
OWNER_OPEN_ID = _bridge_env("OWNER_OPEN_ID", "")

# 会话持久化目录
SESSIONS_DIR = os.path.expanduser(
    _bridge_env("SESSIONS_DIR", f"~/.cli_lark_bridge_{CLI_TYPE}")
)


# ── 工具自身配置（不受 BRIDGE_NAME 影响）─────────────────────

# CLI 可执行文件路径
_OPENCODE = _direct_env("OPENCODE_PATH") or shutil.which("opencode") or "opencode"
_CLAUDE = _direct_env("CLAUDE_PATH") or shutil.which("claude") or "claude"


def get_cli_command() -> list[str]:
    """返回 CLI 可执行文件路径列表，根据 CLI_TYPE 决定"""
    if CLI_TYPE == "claude":
        return [_CLAUDE]
    return [_OPENCODE]


# opencode serve 模式配置
OPENCODE_SERVE_URL = _direct_env("OPENCODE_SERVE_URL", "")
OPENCODE_SERVE_PASSWORD = _direct_env("OPENCODE_SERVE_PASSWORD", "")
OPENCODE_SERVE_AUTO_START = _direct_env("OPENCODE_SERVE_AUTO_START", "true").lower() == "true"
OPENCODE_SERVE_PORT = int(_direct_env("OPENCODE_SERVE_PORT", "4096"))

# claude 默认模型
DEFAULT_MODEL = _direct_env("DEFAULT_MODEL", "")


# ── 全局配置（不受 BRIDGE_NAME 影响）─────────────────────────

LOG_LEVEL = _direct_env("LOG_LEVEL", "INFO")
STREAM_CHUNK_SIZE = int(_direct_env("STREAM_CHUNK_SIZE", "20"))
