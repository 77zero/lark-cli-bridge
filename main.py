"""
cli_lark_bridge — 飞书 × CLI 工具桥接
通过飞书 WebSocket 长连接接收私聊消息，调用本机 CLI 工具并流式回复。

启动：python main.py

支持的 CLI 工具（通过 .env 中 CLI_TYPE 配置）：
  - opencode: 调用 opencode run
  - claude:   调用 claude -p --output-format stream-json
"""

import asyncio
import json
import sys
import os
import threading
import time
import traceback
import atexit
from typing import Optional

# 确保项目目录在 sys.path 最前面
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import lark_oapi as lark
from lark_oapi.api.im.v1.model import P2ImMessageReceiveV1

import bot_config as config
from feishu_client import FeishuClient
from session_store import SessionStore
from cli_runner import run_cli, format_tool
from run_control import ActiveRun, ActiveRunRegistry, stop_active_run


# ── 看门狗：自适应重启 ──────────────────────────────────────

MAX_UPTIME = 4 * 3600          # 最长连续运行 4 小时
IDLE_RESTART_THRESHOLD = 1800   # 空闲超过 30 分钟才允许重启
_start_time = time.time()
_last_event = time.time()


def _watchdog():
    """后台线程：仅在长时间无消息时才主动重启，避免打断活跃对话。"""
    while True:
        time.sleep(300)  # 每 5 分钟检查
        uptime = time.time() - _start_time
        idle = time.time() - _last_event

        if uptime > MAX_UPTIME and idle > IDLE_RESTART_THRESHOLD:
            print(f"[watchdog] 运行{uptime/3600:.1f}h, 空闲{idle/60:.0f}min, 定时重启", flush=True)
            os._exit(0)

        print(f"[watchdog] uptime={uptime/3600:.1f}h idle={idle/60:.0f}min", flush=True)


# ── 全局单例 ──────────────────────────────────────────────────

# 独立的 asyncio 事件循环
_bot_loop: asyncio.AbstractEventLoop = asyncio.new_event_loop()


def _start_bot_loop():
    asyncio.set_event_loop(_bot_loop)
    _bot_loop.run_forever()


threading.Thread(target=_start_bot_loop, daemon=True, name="bot-loop").start()

lark_client = lark.Client.builder() \
    .app_id(config.FEISHU_APP_ID) \
    .app_secret(config.FEISHU_APP_SECRET) \
    .log_level(lark.LogLevel.INFO) \
    .build()

feishu = FeishuClient(lark_client)
store = SessionStore()
_active_runs = ActiveRunRegistry()

# 飞书消息处理超时（3 秒内必须返回，否则重推）
FEISHU_TIMEOUT = 2


# ── 上线通知 ──────────────────────────────────────────────────

async def _send_boot_notification():
    """启动时发送上线通知"""
    if not config.OWNER_OPEN_ID:
        return
    try:
        msg = (
            f"[OK] **{config.CLI_TYPE} Bridge 已上线**\n"
            f"工作目录: `{config.CLI_WORK_DIR}`\n"
            f"启动时间: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            f"发送消息即可开始对话。\n"
            f"输入 `/new` 开启新会话\n"
            f"输入 `/stop` 停止当前任务"
        )
        await feishu.send_card_to_user(config.OWNER_OPEN_ID, content=msg, loading=False)
        print(f"[上线通知] 已发送到 {config.OWNER_OPEN_ID[:8]}...", flush=True)
    except Exception as e:
        print(f"[上线通知] 发送失败: {e}", flush=True)


# ── /new 和 /stop 命令处理 ──────────────────────────────────

async def _handle_new_command(user_id: str) -> str:
    """开启新会话"""
    await store.new_session(user_id)
    # 同时停止正在运行的任务
    active = _active_runs.get_run(user_id)
    if active:
        await stop_active_run(_active_runs, user_id)
    return "[OK] 已开启新会话，发送消息开始对话。"


async def _handle_stop_command(user_id: str) -> str:
    """停止当前任务"""
    active_run = _active_runs.get_run(user_id)
    if active_run is None:
        return "当前没有正在运行的任务。"
    if active_run.stop_requested:
        return "正在停止当前任务，请稍候..."

    stopped = await stop_active_run(
        _active_runs,
        user_id,
        on_stopped=lambda r: _announce_stopped(r),
    )
    if not stopped:
        return "当前没有正在运行的任务。"
    return "已发送停止请求，正在终止..."


async def _announce_stopped(active_run: ActiveRun):
    """任务停止后更新卡片"""
    try:
        await feishu.update_card(active_run.card_msg_id, "[STOP] 已停止当前任务")
    except Exception:
        pass


# ── 核心消息处理 ─────────────────────────────────────────────

def _extract_text(event: P2ImMessageReceiveV1) -> str:
    """从消息事件中提取文本内容"""
    msg = event.event.message
    if msg.message_type != "text":
        return ""
    try:
        return json.loads(msg.content).get("text", "").strip()
    except Exception:
        return ""


def _extract_sender_id(event: P2ImMessageReceiveV1) -> str:
    """提取发送者的 open_id"""
    return event.event.sender.sender_id.open_id


def _clean_opencode_output(text: str) -> str:
    """清洗 opencode 响应，去除 agent 自我介绍等系统前缀"""
    lines = text.strip().split("\n")
    # 跳过开头的系统/环境提示行
    clean_start = 0
    skip_patterns = [
        "> Sisyphus",           # agent 身份行
        "我先看看",              # opencode agent 常见开头
        "让我看看",              # agent 观察
        "我来看看",              # agent 观察
        "好的，",               # agent 应答
        "<system-reminder>",    # 系统提示
        "<local-command",       # 本地命令提示
        "Tool:",               # 工具调用残留
        "[环境：",              # 环境信息
    ]
    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            clean_start = i + 1
            continue
        if any(stripped.startswith(p) for p in skip_patterns):
            clean_start = i + 1
            continue
        break

    return "\n".join(lines[clean_start:]).strip()


def on_message_receive(data: P2ImMessageReceiveV1) -> None:
    """
    飞书 SDK 同步回调入口。
    收到消息后立即返回（3 秒内），异步任务调度到 _bot_loop 执行。
    """
    global _last_event
    _last_event = time.time()

    # 同步阶段：快速获取必要信息
    user_id = _extract_sender_id(data)
    text = _extract_text(data)
    msg = data.event.message

    if not text:
        return

    # /stop 和 /new 在同步阶段快速响应，不排队等 CLI
    if text.lower() == "/stop" or text.strip().endswith("/stop"):
        asyncio.run_coroutine_threadsafe(
            _handle_stop_quick(user_id, msg.message_id), _bot_loop
        )
        return

    if text.lower() == "/new" or text.strip().endswith("/new"):
        asyncio.run_coroutine_threadsafe(
            _handle_new_quick(user_id, msg.message_id), _bot_loop
        )
        return

    # 调度异步处理
    asyncio.run_coroutine_threadsafe(
        handle_message_async(data), _bot_loop
    )


async def _handle_stop_quick(user_id: str, message_id: str):
    """快速响应 /stop"""
    reply = await _handle_stop_command(user_id)
    await feishu.reply_card(message_id, content=reply, loading=False)


async def _handle_new_quick(user_id: str, message_id: str):
    """快速响应 /new"""
    reply = await _handle_new_command(user_id)
    await feishu.reply_card(message_id, content=reply, loading=False)


async def handle_message_async(event: P2ImMessageReceiveV1):
    """异步处理一条飞书消息"""
    msg = event.event.message
    user_id = _extract_sender_id(event)
    text = _extract_text(event)

    print(f"[消息] user={user_id[:8]}... text={text[:50]}", flush=True)

    # ── 处理图片消息 ──────────────────────────────────────────
    img_path: Optional[str] = None
    if msg.message_type == "image":
        try:
            image_key = json.loads(msg.content).get("image_key", "")
            if image_key:
                img_path = await feishu.download_image(msg.message_id, image_key)
                if img_path:
                    text = f"[用户发送了一张图片，路径：{img_path}，请读取并分析这张图片]"
                else:
                    await feishu.reply_card(msg.message_id, content="[ERR] 下载图片失败", loading=False)
                    return
        except Exception as e:
            print(f"[image] 下载失败: {e}", flush=True)
            await feishu.reply_card(msg.message_id, content=f"[ERR] 下载图片失败：{e}", loading=False)
            return

    if msg.message_type not in ("text", "image"):
        return

    if not text:
        return

    # ── 已读回执：表情回复 ──────────────────────────────────
    await feishu.add_reaction(msg.message_id, "OK")

    # ── 自动打断 ──────────────────────────────────────────────
    active = _active_runs.get_run(user_id)
    if active and not active.stop_requested:
        print(f"[打断] 新消息到达，自动停止当前任务", flush=True)
        await stop_active_run(_active_runs, user_id)

    # ── 调用 CLI ──────────────────────────────────────────────
    session = await store.get_current(user_id)

    # 发送"思考中"占位卡片，标题用消息摘要
    try:
        card_title = text[:40] + ("..." if len(text) > 40 else "")
        card_msg_id = await feishu.reply_card(msg.message_id, loading=True, title=card_title)
    except Exception as e:
        print(f"[error] 发送思考中卡片失败: {e}", flush=True)
        await feishu.reply_card(msg.message_id, content=f"[ERR] 发送失败：{e}", loading=False)
        return

    await _run_and_display(user_id, text, card_msg_id, session, card_title)


async def _run_and_display(
    user_id: str, text: str, card_msg_id: str, session, card_title: str = "",
):
    """调用 CLI 并流式展示结果"""
    active_run = _active_runs.start_run(user_id, card_msg_id)

    accumulated = ""
    tool_history: list[str] = []
    last_push_time = 0.0
    push_failures = 0
    _PUSH_INTERVAL = 0.4  # 400ms 推送间隔
    _MAX_DISPLAY = 4000

    async def push(content: str):
        nonlocal push_failures
        if push_failures >= 3:
            return
        try:
            await feishu.update_card(card_msg_id, content)
            push_failures = 0
        except Exception as e:
            push_failures += 1
            print(f"[warn] 推送失败 ({push_failures}/3): {e}", flush=True)

    def _build_display() -> str:
        parts = []
        if tool_history:
            parts.append("\n".join(tool_history[-5:]))
        if accumulated:
            if parts:
                parts.append("")
            d = accumulated
            if len(d) > _MAX_DISPLAY:
                d = "...\n\n" + d[-_MAX_DISPLAY:]
            parts.append(d)
        return "\n".join(parts) if parts else "[...] 思考中..."

    async def on_tool_use(name: str, inp: dict):
        nonlocal accumulated, last_push_time
        tool_line = format_tool(name, inp)
        if inp and tool_history:
            tool_history[-1] = tool_line
        else:
            tool_history.append(tool_line)
        await push(_build_display())
        last_push_time = time.time()

    async def on_text_chunk(chunk: str):
        nonlocal accumulated, last_push_time
        accumulated += chunk
        now = time.time()
        if now - last_push_time >= _PUSH_INTERVAL:
            await push(_build_display())
            last_push_time = now

    try:
        print(f"[run_cli] 开始调用 {config.CLI_TYPE}...", flush=True)
        full_text, new_session_id = await run_cli(
            message=text,
            session_id=session.session_id,
            on_text_chunk=on_text_chunk,
            on_tool_use=on_tool_use,
            on_process_start=lambda proc: _active_runs.attach_process(user_id, proc),
        )
        print(f"[run_cli] 完成, session={new_session_id}", flush=True)
    except Exception as e:
        if active_run.stop_requested:
            return
        print(f"[error] CLI 运行失败: {type(e).__name__}: {e}", flush=True)
        traceback.print_exc()
        try:
            await feishu.update_card(card_msg_id, f"[ERROR] CLI 执行出错：{type(e).__name__}: {e}")
        except Exception:
            pass
        return
    finally:
        _active_runs.clear_run(user_id, active_run)

    # 最终更新卡片
    final = full_text or accumulated or "（无输出）"
    final = _clean_opencode_output(final)
    try:
        await feishu.update_card(card_msg_id, final, title=card_title)
    except Exception as e:
        print(f"[error] 卡片更新失败: {e}", flush=True)
        try:
            await feishu.send_text_to_user(user_id, final)
        except Exception as e2:
            print(f"[error] 文本回退也失败: {e2}", flush=True)

    # 保存会话
    await store.on_cli_response(user_id, new_session_id, text)


# ── 启动 ──────────────────────────────────────────────────────

def _start_opencode_serve():
    """后台启动 opencode serve 进程（如果配置了）"""
    if config.CLI_TYPE != "opencode":
        return None
    if not config.OPENCODE_SERVE_AUTO_START:
        return None

    import subprocess as sp
    port = config.OPENCODE_SERVE_PORT
    serve_url = f"http://localhost:{port}"

    # 检查 serve 是否已在运行
    import socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.connect(("localhost", port))
        sock.close()
        print(f"   opencode serve 已在运行: {serve_url}")
        return serve_url
    except Exception:
        sock.close()

    # 启动 serve
    print(f"   启动 opencode serve: {serve_url} ...")
    env = os.environ.copy()
    if config.OPENCODE_SERVE_PASSWORD:
        env["OPENCODE_SERVER_PASSWORD"] = config.OPENCODE_SERVE_PASSWORD

    cmd = config.get_cli_command() + ["serve", "--port", str(port)]
    try:
        sp.Popen(
            cmd,
            stdout=sp.DEVNULL,
            stderr=sp.DEVNULL,
            cwd=config.CLI_WORK_DIR,
            env=env,
        )
        # 等 3 秒让 serve 启动
        time.sleep(3)
        print(f"   opencode serve 已启动: {serve_url}")
        return serve_url
    except Exception as e:
        print(f"   [warn] opencode serve 启动失败: {e}")
        return None


def _pid_exists(pid: int) -> bool:
    """检查进程是否存在（跨平台）"""
    if os.name == "nt":
        import subprocess as _sp
        result = _sp.run(
            ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
            capture_output=True, text=True, timeout=5
        )
        return str(pid) in result.stdout
    else:
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False


def main():
    # ── PID 锁：防止 NSSM 快速重启导致多实例并发 ────────────
    pid_file = os.path.join(config.SESSIONS_DIR, "pid.lock")
    os.makedirs(config.SESSIONS_DIR, exist_ok=True)

    if os.path.exists(pid_file):
        try:
            with open(pid_file) as f:
                old_pid = int(f.read().strip())
            # 检查旧进程是否还活着
            if _pid_exists(old_pid):
                print(f"[PID锁] 进程 {old_pid} 仍在运行，退出", flush=True)
                sys.exit(1)
            print(f"[PID锁] 旧进程 {old_pid} 已退出，覆盖锁文件", flush=True)
        except (ValueError, FileNotFoundError):
            pass

    with open(pid_file, "w") as f:
        f.write(str(os.getpid()))

    # 退出时清理
    def _cleanup_pid():
        try:
            os.remove(pid_file)
        except OSError:
            pass
    atexit.register(_cleanup_pid)

    print(f"[启动] lark-cli-bridge v{config.__version__} [PID={os.getpid()}]")
    print(f"   CLI 类型    : {config.CLI_TYPE}")
    print(f"   CLI 命令    : {' '.join(config.get_cli_command())}")
    print(f"   工作目录    : {config.CLI_WORK_DIR}")
    print(f"   App ID      : {config.FEISHU_APP_ID}")

    # 启动 opencode serve（如果配置了）
    _start_opencode_serve()

    # 事件处理器
    handler = lark.EventDispatcherHandler.builder("", "") \
        .register_p2_im_message_receive_v1(on_message_receive) \
        .build()

    ws_client = lark.ws.Client(
        config.FEISHU_APP_ID,
        config.FEISHU_APP_SECRET,
        event_handler=handler,
        log_level=lark.LogLevel.INFO,
    )

    # 启动看门狗
    threading.Thread(target=_watchdog, daemon=True).start()

    # 延迟发送上线通知（等 WebSocket 连上）
    def _delayed_notify():
        time.sleep(5)
        future = asyncio.run_coroutine_threadsafe(_send_boot_notification(), _bot_loop)
        try:
            future.result(timeout=10)
        except Exception:
            pass
    threading.Thread(target=_delayed_notify, daemon=True).start()

    print("[连接] 飞书 WebSocket 长连接（自动重连）...")
    ws_client.start()  # 阻塞，内部运行事件循环


if __name__ == "__main__":
    main()
