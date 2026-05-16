#!/usr/bin/env bash
# ============================================================
# lark-cli-bridge 停止脚本 (Linux/macOS)
# ============================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOG_DIR="$SCRIPT_DIR/logs"
PID_FILE="$LOG_DIR/services.pid"

if [ ! -f "$PID_FILE" ]; then
    echo -e "\033[1;33m[提示] 没有找到运行中的服务\033[0m"
    exit 0
fi

STOPPED=0

while read -r pid; do
    if [ -z "$pid" ]; then
        continue
    fi
    if kill -0 "$pid" 2>/dev/null; then
        echo -e "\033[1;33m[停止] PID $pid\033[0m"
        kill "$pid" 2>/dev/null || true
        sleep 2
        if kill -0 "$pid" 2>/dev/null; then
            echo -e "\033[1;33m  未响应，强制终止...\033[0m"
            kill -9 "$pid" 2>/dev/null || true
            sleep 1
        fi
        if kill -0 "$pid" 2>/dev/null; then
            echo -e "\033[0;31m[失败] PID $pid 无法停止\033[0m"
        else
            STOPPED=$((STOPPED + 1))
        fi
    else
        echo -e "\033[0;37m[过期] PID $pid 已不存在\033[0m"
    fi
done < "$PID_FILE"

rm -f "$PID_FILE"
echo -e "\033[0;32m[完成] 已停止 $STOPPED 个服务\033[0m"
