#!/usr/bin/env bash
# ============================================================
# lark-cli-bridge 双服务启动脚本 (Linux/macOS)
# 后台运行 opencode + claude 两个桥接实例
# ============================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOG_DIR="$SCRIPT_DIR/logs"
PID_FILE="$LOG_DIR/services.pid"

mkdir -p "$LOG_DIR"

# ── 颜色 ──────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
GRAY='\033[0;37m'
NC='\033[0m'

# ── 停止已运行的实例 ──────────────────────────────────────
if [ -f "$PID_FILE" ]; then
    echo -e "${YELLOW}[清理] 检查已有进程...${NC}"
    while read -r old_pid; do
        if [ -n "$old_pid" ] && kill -0 "$old_pid" 2>/dev/null; then
            echo -e "${YELLOW}  停止进程 $old_pid${NC}"
            kill "$old_pid" 2>/dev/null || true
        fi
    done < "$PID_FILE"
    rm -f "$PID_FILE"
    sleep 2
fi

# ── 获取 Python 路径 ──────────────────────────────────────
PYTHON="$(command -v python3 || command -v python)"
echo -e "${GRAY}[Python] $PYTHON${NC}"

# ── 启动 opencode 实例 ────────────────────────────────────
OPENCODE_LOG="$LOG_DIR/opencode.log"
echo -e "${GREEN}[启动] opencode bridge...${NC}"

BRIDGE_NAME=opencode nohup "$PYTHON" "$SCRIPT_DIR/main.py" \
    >> "$OPENCODE_LOG" 2>&1 &

OPEN_PID=$!
echo "$OPEN_PID" > "$LOG_DIR/opencode.pid"
echo "$OPEN_PID" >> "$PID_FILE"
echo -e "${GRAY}  PID: $OPEN_PID  日志: $OPENCODE_LOG${NC}"

# ── 启动 claude 实例 ─────────────────────────────────────
CLAUDE_LOG="$LOG_DIR/claude.log"
echo -e "${GREEN}[启动] claude bridge...${NC}"

BRIDGE_NAME=claude nohup "$PYTHON" "$SCRIPT_DIR/main.py" \
    >> "$CLAUDE_LOG" 2>&1 &

CLAUDE_PID=$!
echo "$CLAUDE_PID" > "$LOG_DIR/claude.pid"
echo "$CLAUDE_PID" >> "$PID_FILE"
echo -e "${GRAY}  PID: $CLAUDE_PID  日志: $CLAUDE_LOG${NC}"

# ── 完成 ──────────────────────────────────────────────────
echo ""
echo -e "${GREEN}[完成] 两个服务已后台启动${NC}"
echo ""
echo -e "${CYAN}  查看日志:${NC}"
echo "    tail -f '$OPENCODE_LOG'"
echo "    tail -f '$CLAUDE_LOG'"
echo ""
echo -e "${CYAN}  停止: ./stop_bridges.sh${NC}"
