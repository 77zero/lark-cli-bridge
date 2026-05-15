"""
CLI 子进程管理
封装 opencode / claude 的 subprocess 调用，支持流式输出解析

opencode:
    opencode run [--session ID] "prompt"

claude:
    claude --print --output-format stream-json --verbose --include-partial-messages
"""

import asyncio
import json
import os
import re
import subprocess as sp
from typing import Callable, Optional

from bot_config import (
    CLI_TYPE, CLI_WORK_DIR, DEFAULT_MODEL, get_cli_command,
)


IDLE_TIMEOUT = 300  # 5 分钟无输出且无子进程，视为挂死
_CHECK_INTERVAL = 30  # 静默时每 30 秒检查一次子进程


def _has_children(pid: int) -> bool:
    """检查进程是否有活跃子进程（说明在跑命令、编译等）"""
    try:
        if os.name == "nt":
            # Windows 上用 tasklist 检查
            result = sp.run(
                ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
                capture_output=True, timeout=5, text=True
            )
            return result.returncode == 0 and result.stdout.strip() != ""
        else:
            result = sp.run(
                ["pgrep", "-P", str(pid)],
                capture_output=True, timeout=5
            )
            return result.returncode == 0
    except Exception:
        return False


async def _fire_callback(cb, *args):
    """安全调用回调（支持同步和异步）"""
    if cb is None:
        return
    if asyncio.iscoroutinefunction(cb):
        await cb(*args)
    else:
        cb(*args)


async def run_cli(
    message: str,
    session_id: Optional[str] = None,
    on_text_chunk: Optional[Callable[[str], None]] = None,
    on_tool_use: Optional[Callable[[str, dict], None]] = None,
    on_process_start: Optional[Callable[[asyncio.subprocess.Process], None]] = None,
) -> tuple[str, Optional[str]]:
    """
    调用 CLI 工具并流式解析输出。

    Returns:
        (full_response_text, new_session_id)
    """
    if CLI_TYPE == "claude":
        return await _run_claude(message, session_id, on_text_chunk, on_tool_use, on_process_start)
    else:
        return await _run_opencode(message, session_id, on_text_chunk, on_process_start)


# ── opencode session 追踪 ───────────────────────────────────

async def _list_opencode_sessions() -> set[str]:
    """获取本地 opencode session 列表（读取本地 DB，无需 serve）"""
    cmd = get_cli_command() + ["session", "list"]
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=CLI_WORK_DIR,
        )
        stdout, _ = await proc.communicate()
        text = stdout.decode("utf-8", errors="replace")
        # 解析表格输出，提取 session ID（格式：ses_xxx...）
        ids = set(re.findall(r'(ses_[a-zA-Z0-9]+)', text))
        return ids
    except Exception:
        return set()


async def _run_opencode(
    message: str,
    session_id: Optional[str] = None,
    on_text_chunk: Optional[Callable[[str], None]] = None,
    on_process_start: Optional[Callable[[asyncio.subprocess.Process], None]] = None,
) -> tuple[str, Optional[str]]:
    """
    调用 opencode run。

    新建会话: opencode run "message" → 扫描 session 列表提取新 ID
    复用会话: opencode run --session ID "message" → 继续对话
    """
    cmd = get_cli_command() + ["run"]

    new_session_id: Optional[str] = None

    if session_id:
        cmd += ["--session", session_id]
    else:
        before = await _list_opencode_sessions()

    cmd += [message]

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=CLI_WORK_DIR,
    )

    await _fire_callback(on_process_start, proc)

    stdout_bytes, stderr_bytes = await proc.communicate()
    full_text = stdout_bytes.decode("utf-8", errors="replace").strip()
    stderr_text = stderr_bytes.decode("utf-8", errors="replace").strip()

    if proc.returncode != 0:
        if session_id and not full_text:
            print(f"[opencode] session {session_id[:8]} 恢复失败，使用新会话", flush=True)
            return await _run_opencode(message, None, on_text_chunk, on_process_start)
        err_detail = stderr_text or "no stderr"
        if full_text:
            return full_text, session_id
        raise RuntimeError(f"opencode 退出码 {proc.returncode}: {err_detail}")

    # 扫描新增的 session_id
    if not session_id:
        after = await _list_opencode_sessions()
        new_ids = after - before
        if new_ids:
            new_session_id = new_ids.pop()
            print(f"[opencode] 新 session: {new_session_id[:12]}...", flush=True)

    return full_text, new_session_id or session_id


async def _run_claude(
    message: str,
    session_id: Optional[str] = None,
    on_text_chunk: Optional[Callable[[str], None]] = None,
    on_tool_use: Optional[Callable[[str, dict], None]] = None,
    on_process_start: Optional[Callable[[asyncio.subprocess.Process], None]] = None,
) -> tuple[str, Optional[str]]:
    """调用 claude -p 非交互模式，解析 stream-json 输出"""

    async def _run_once(active_session_id: Optional[str]) -> tuple[str, Optional[str], int, str]:
        cmd = get_cli_command()
        cmd += [
            "--print",
            "--output-format", "stream-json",
            "--verbose",
            "--include-partial-messages",
            "--permission-mode", "bypassPermissions",
        ]
        if active_session_id:
            cmd += ["--resume", active_session_id]
        if DEFAULT_MODEL:
            cmd += ["--model", DEFAULT_MODEL]

        env = os.environ.copy()
        env.pop("CLAUDECODE", None)

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=CLI_WORK_DIR,
            env=env,
            limit=10 * 1024 * 1024,
        )

        await _fire_callback(on_process_start, proc)

        proc.stdin.write((message + "\n").encode())
        await proc.stdin.drain()
        proc.stdin.close()

        full_text = ""
        new_session_id = None
        pending_tool_name = ""
        pending_tool_input_json = ""

        idle_seconds = 0

        try:
            while True:
                try:
                    raw_line = await asyncio.wait_for(
                        proc.stdout.readline(), timeout=_CHECK_INTERVAL
                    )
                    idle_seconds = 0
                except asyncio.TimeoutError:
                    if _has_children(proc.pid):
                        idle_seconds = 0
                        continue
                    idle_seconds += _CHECK_INTERVAL
                    if idle_seconds >= IDLE_TIMEOUT:
                        proc.kill()
                        await proc.wait()
                        raise RuntimeError(
                            f"Claude 执行超时（{IDLE_TIMEOUT}秒无输出），已终止进程"
                        )
                    continue

                if not raw_line:
                    break

                line = raw_line.decode("utf-8", errors="replace").strip()
                if not line:
                    continue

                try:
                    data = json.loads(line)
                except (json.JSONDecodeError, ValueError):
                    # 跳过非 JSON 行（启动横幅、stderr 混杂等）
                    continue

                event_type = data.get("type")

                if event_type == "system":
                    sid = data.get("session_id")
                    if sid:
                        new_session_id = sid

                elif event_type == "stream_event":
                    evt = data.get("event", {})
                    evt_type = evt.get("type")

                    if evt_type == "content_block_delta":
                        delta = evt.get("delta", {})
                        delta_type = delta.get("type")

                        if delta_type == "text_delta":
                            chunk = delta.get("text", "")
                            if chunk:
                                full_text += chunk
                                await _fire_callback(on_text_chunk, chunk)

                        elif delta_type == "input_json_delta":
                            pending_tool_input_json += delta.get("partial_json", "")

                    elif evt_type == "content_block_start":
                        block = evt.get("content_block", {})
                        if block.get("type") == "tool_use":
                            pending_tool_name = block.get("name", "")
                            pending_tool_input_json = ""
                            await _fire_callback(on_tool_use, pending_tool_name, {})

                    elif evt_type == "content_block_stop":
                        if pending_tool_name and pending_tool_input_json:
                            try:
                                inp = json.loads(pending_tool_input_json)
                            except json.JSONDecodeError:
                                inp = {}
                            await _fire_callback(on_tool_use, pending_tool_name, inp)
                        pending_tool_name = ""
                        pending_tool_input_json = ""

                elif event_type == "result":
                    sid = data.get("session_id")
                    if sid:
                        new_session_id = sid
                    final_text = _extract_text_content(data.get("result", ""))
                    if final_text:
                        full_text = final_text

        except RuntimeError:
            raise

        stderr_output = await proc.stderr.read()
        await proc.wait()
        stderr_text = stderr_output.decode("utf-8", errors="replace").strip()
        return full_text.strip(), new_session_id, proc.returncode, stderr_text

    final_text, new_session_id, returncode, stderr_text = await _run_once(session_id)

    # session 恢复失败时自动回退到新 session
    # 条件：有 session_id、退出码非零、无有效输出
    # 触发：stderr 为空 OR stderr 包含 session 失效关键词
    if session_id and returncode != 0 and not final_text:
        _stderr_lower = stderr_text.lower()
        _session_failure_keywords = [
            "no conversation found",
            "session not found",
            "session id",
            "not found",
            "does not exist",
        ]
        _is_session_failure = (
            not stderr_text
            or any(kw in _stderr_lower for kw in _session_failure_keywords)
        )
        if _is_session_failure:
            print(f"[claude] resume 失败（{stderr_text[:80] or '无 stderr 输出'}），使用新 session 重试", flush=True)
            final_text, new_session_id, returncode, stderr_text = await _run_once(None)

    if returncode != 0:
        detail = stderr_text or "no stderr"
        if final_text:
            return final_text, new_session_id
        raise RuntimeError(f"claude 退出码 {returncode}: {detail}")

    return final_text, new_session_id


def _extract_text_content(value) -> str:
    """从 claude result 中提取纯文本"""
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        parts = []
        for item in value:
            if isinstance(item, dict) and item.get("type") == "text":
                parts.append(item.get("text", ""))
        return "".join(parts)
    return ""


# ── 工具调用格式化 ──────────────────────────────────────────

def format_tool(name: str, inp: dict) -> str:
    """格式化工具调用的进度提示文本"""
    n = name.lower()
    if n == "bash":
        cmd = inp.get("command", "")
        if len(cmd) > 80:
            cmd = cmd[:77] + "..."
        return f" **执行命令：** `{cmd}`" if cmd else f" **执行命令...**"
    elif n in ("read_file", "read"):
        return f" **读取：** `{inp.get('file_path', inp.get('path', ''))}`"
    elif n in ("write_file", "write"):
        return f" **写入：** `{inp.get('file_path', inp.get('path', ''))}`"
    elif n in ("edit_file", "edit"):
        return f" **编辑：** `{inp.get('file_path', inp.get('path', ''))}`"
    elif n == "glob":
        return f" **搜索文件：** `{inp.get('pattern', '')}`"
    elif n == "grep":
        return f" **搜索内容：** `{inp.get('pattern', '')}`"
    elif n == "task":
        desc = inp.get('description', inp.get('prompt', ''))
        return f" **子任务：** {desc[:40]}"
    elif n == "webfetch":
        return f" **抓取网页...**"
    elif n == "websearch":
        return f" **搜索：** {inp.get('query', '')}"
    else:
        return f" **{name}**"
