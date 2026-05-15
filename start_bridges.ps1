# ============================================================
# lark-cli-bridge 双服务启动脚本
# 后台运行 opencode + claude 两个桥接实例
# ============================================================

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$LogDir = Join-Path $ScriptDir "logs"
$PidFile = Join-Path $LogDir "services.pid"

New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

# ── 停止已运行的实例 ────────────────────────────────────────
if (Test-Path $PidFile) {
    Write-Host "[清理] 检查已有进程..." -ForegroundColor Yellow
    $oldPids = Get-Content $PidFile
    foreach ($procId in $oldPids) {
        try {
            $proc = Get-Process -Id $procId -ErrorAction SilentlyContinue
            if ($proc) {
                Write-Host "  停止进程 $procId ($($proc.ProcessName))" -ForegroundColor Yellow
                Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
            }
        } catch {}
    }
    Remove-Item $PidFile -Force
    Start-Sleep -Seconds 2
}

# ── 获取 Python 路径 ────────────────────────────────────────
$Python = (Get-Command python -ErrorAction Stop).Source
Write-Host "[Python] $Python" -ForegroundColor Gray

# ── 启动 opencode 实例 ─────────────────────────────────────
$OpenCodeLog = Join-Path $LogDir "opencode.log"
Write-Host "[启动] opencode bridge..." -ForegroundColor Green

$env:BRIDGE_NAME = "opencode"
$openProc = Start-Process -FilePath $Python `
    -ArgumentList "`"$ScriptDir\main.py`"" `
    -WorkingDirectory $ScriptDir `
    -RedirectStandardOutput $OpenCodeLog `
    -RedirectStandardError $OpenCodeLog `
    -NoNewWindow `
    -PassThru

$openProc.Id | Out-File (Join-Path $LogDir "opencode.pid")
$openProc.Id | Out-File $PidFile -Append
Write-Host "  PID: $($openProc.Id)  日志: $OpenCodeLog" -ForegroundColor Gray

# ── 启动 claude 实例（同目录，用 BRIDGE_NAME 区分）─────────
$ClaudeLog = Join-Path $LogDir "claude.log"
Write-Host "[启动] claude bridge..." -ForegroundColor Green

$env:BRIDGE_NAME = "claude"
$claudeProc = Start-Process -FilePath $Python `
    -ArgumentList "`"$ScriptDir\main.py`"" `
    -WorkingDirectory $ScriptDir `
    -RedirectStandardOutput $ClaudeLog `
    -RedirectStandardError $ClaudeLog `
    -NoNewWindow `
    -PassThru

$claudeProc.Id | Out-File (Join-Path $LogDir "claude.pid")
$claudeProc.Id | Out-File $PidFile -Append
Write-Host "  PID: $($claudeProc.Id)  日志: $ClaudeLog" -ForegroundColor Gray

Remove-Item Env:\BRIDGE_NAME -ErrorAction SilentlyContinue

# ── 完成 ────────────────────────────────────────────────────
Write-Host ""
Write-Host "[完成] 两个服务已后台启动" -ForegroundColor Green
Write-Host ""
Write-Host "  查看日志:" -ForegroundColor Cyan
Write-Host "    Get-Content '$OpenCodeLog' -Tail 20"
Write-Host "    Get-Content '$ClaudeLog' -Tail 20"
Write-Host ""
Write-Host "  停止: .\stop_bridges.ps1"
