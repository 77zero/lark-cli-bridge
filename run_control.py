"""
任务运行控制
管理活跃的 CLI 运行实例，支持中断和超时
"""

import asyncio
from dataclasses import dataclass, field
from typing import Awaitable, Callable, Optional


@dataclass
class ActiveRun:
    """活跃的 CLI 运行实例"""
    user_id: str
    card_msg_id: str
    proc: Optional[asyncio.subprocess.Process] = None
    stop_requested: bool = False
    stop_announced: bool = False


class ActiveRunRegistry:
    """活跃运行注册表，支持按用户查找和控制"""

    def __init__(self):
        self._runs: dict[str, ActiveRun] = {}

    def start_run(self, user_id: str, card_msg_id: str) -> ActiveRun:
        """注册一个新的活跃运行"""
        active_run = ActiveRun(user_id=user_id, card_msg_id=card_msg_id)
        self._runs[user_id] = active_run
        return active_run

    def get_run(self, user_id: str) -> Optional[ActiveRun]:
        """获取用户的活跃运行"""
        return self._runs.get(user_id)

    def attach_process(self, user_id: str, proc: asyncio.subprocess.Process) -> Optional[ActiveRun]:
        """将进程附加到活跃运行"""
        active_run = self._runs.get(user_id)
        if active_run is None:
            return None
        active_run.proc = proc
        if active_run.stop_requested and proc.returncode is None:
            proc.terminate()
        return active_run

    def clear_run(self, user_id: str, active_run: Optional[ActiveRun] = None):
        """清除活跃运行"""
        current = self._runs.get(user_id)
        if current is None:
            return
        if active_run is not None and current is not active_run:
            return
        self._runs.pop(user_id, None)


async def stop_active_run(
    registry: ActiveRunRegistry,
    user_id: str,
    on_stopped: Optional[Callable[[ActiveRun], Awaitable[None]]] = None,
    grace_seconds: float = 2.0,
) -> bool:
    """停止用户的活跃运行"""
    active_run = registry.get_run(user_id)
    if active_run is None:
        return False

    active_run.stop_requested = True
    proc = active_run.proc

    if proc is not None and proc.returncode is None:
        proc.terminate()
        try:
            await asyncio.wait_for(proc.wait(), timeout=grace_seconds)
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()

    if on_stopped is not None and not active_run.stop_announced:
        await on_stopped(active_run)
        active_run.stop_announced = True

    return True
