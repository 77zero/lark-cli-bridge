"""
cli_lark_bridge 配置管理
从 .env 文件读取所有配置项
"""

import os
import shutil
from dotenv import load_dotenv

load_dotenv()

# ── 飞书凭证（必填）─────────────────────────────────────────
FEISHU_APP_ID = os.environ["FEISHU_APP_ID"]
FEISHU_APP_SECRET = os.environ["FEISHU_APP_SECRET"]

# ── CLI 工具配置（必填）─────────────────────────────────────
CLI_TYPE = os.environ.get("CLI_TYPE", "opencode")  # opencode / claude
CLI_WORK_DIR = os.path.expanduser(
    os.environ.get("CLI_WORK_DIR", os.path.expanduser("~"))
)

# ── 可选配置 ────────────────────────────────────────────────
# CLI 可执行文件路径
_OPENCODE = os.getenv("OPENCODE_PATH") or shutil.which("opencode") or "opencode"
_CLAUDE = os.getenv("CLAUDE_PATH") or shutil.which("claude") or "claude"

def get_cli_command() -> list[str]:
    """返回 CLI 可执行文件路径列表，根据 CLI_TYPE 决定"""
    if CLI_TYPE == "claude":
        return [_CLAUDE]
    return [_OPENCODE]

# 飞书 SDK 日志级别
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# 默认模型（仅 claude 模式有效）
DEFAULT_MODEL = os.getenv("DEFAULT_MODEL", "")

# 流式推送：每积累多少字符推送一次飞书卡片
STREAM_CHUNK_SIZE = int(os.getenv("STREAM_CHUNK_SIZE", "20"))

# 上线通知接收人（留空不发送）
OWNER_OPEN_ID = os.getenv("OWNER_OPEN_ID", "")

# 会话持久化目录
SESSIONS_DIR = os.path.expanduser("~/.cli_lark_bridge")
