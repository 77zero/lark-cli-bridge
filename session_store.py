"""
会话持久化
基于 JSON 文件的轻量会话存储，每个用户维护一个 CLI session
"""

import asyncio
import json
import os
from datetime import datetime
from typing import Optional

from bot_config import SESSIONS_DIR, CLI_WORK_DIR

SESSIONS_FILE = os.path.join(SESSIONS_DIR, "sessions.json")


class Session:
    """会话对象"""
    def __init__(
        self,
        session_id: Optional[str] = None,
        cwd: str = "",
    ):
        self.session_id = session_id
        self.cwd = cwd or CLI_WORK_DIR


class SessionStore:
    """会话管理器，持久化 user_id → session 映射"""

    def __init__(self):
        os.makedirs(SESSIONS_DIR, exist_ok=True)
        self._save_lock = asyncio.Lock()
        self._data: dict = self._load()

    def _load(self) -> dict:
        """从 JSON 文件加载数据"""
        if os.path.exists(SESSIONS_FILE):
            try:
                with open(SESSIONS_FILE, encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    async def _save_async(self):
        """异步保存，使用锁保护并发写入"""
        async with self._save_lock:
            tmp = SESSIONS_FILE + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self._data, f, indent=2, ensure_ascii=False)
            os.replace(tmp, SESSIONS_FILE)

    def _ensure_user(self, user_id: str) -> dict:
        """确保用户数据存在"""
        return self._data.setdefault(user_id, {
            "session_id": None,
            "started_at": datetime.now().isoformat(),
        })

    async def get_current(self, user_id: str) -> Session:
        """获取用户当前会话"""
        user = self._ensure_user(user_id)
        return Session(
            session_id=user.get("session_id"),
            cwd=CLI_WORK_DIR,
        )

    async def on_cli_response(
        self, user_id: str, new_session_id: Optional[str], first_message: str
    ):
        """CLI 回复后更新会话状态"""
        user = self._ensure_user(user_id)

        if new_session_id:
            user["session_id"] = new_session_id
            user["started_at"] = datetime.now().isoformat()

        await self._save_async()

    async def new_session(self, user_id: str) -> None:
        """为用户开启新会话（清空 session_id）"""
        user = self._ensure_user(user_id)
        user["session_id"] = None
        user["started_at"] = datetime.now().isoformat()
        await self._save_async()

    async def reset_session(self, user_id: str) -> None:
        """重置用户会话（下次消息将开启新会话）"""
        await self.new_session(user_id)
