# ============================================================
# cli_lark_bridge 双服务启动脚本
# 后台运行 opencode + claude 两个桥接实例，输出留存到日志
# 放在 cli_lark_bridge_opencode 目录下运行
# ============================================================

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$LogDir = Join-Path $ScriptDir "logs"
$PidFile = Join-Path $LogDir "services.pid"

New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

# ── 停止已运行的实例 ────────────────────────────────────────
if (Test-Path $PidFile) {
    Write-Host "[清理] 检查已有进程..." -ForegroundColor Yellow
    $oldPids = Get-Content $PidFile
    foreach ($pid in $oldPids) {
        try {
            $proc = Get-Process -Id $pid -ErrorAction SilentlyContinue
            if ($proc) {
                Write-Host "  停止进程 $pid ($($proc.ProcessName))" -ForegroundColor Yellow
                Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue
            }
        } catch {}
    }
    Remove-Item $PidFile -Force
    Start-Sleep -Seconds 2
}

# ── 获取 Python 路径 ────────────────────────────────────────
$Python = (Get-Command python -ErrorAction Stop).Source
Write-Host "[Python] $Python" -ForegroundColor Gray

# ── 启动 opencode 实例（本目录）─────────────────────────────
$OpenCodeDir = $ScriptDir
$OpenCodeLog = Join-Path $OpenCodeDir "logs" "opencode.log"
New-Item -ItemType Directory -Force -Path (Join-Path $OpenCodeDir "logs") | Out-Null

Write-Host "[启动] opencode bridge..." -ForegroundColor Green

$openProc = Start-Process -FilePath $Python `
    -ArgumentList "`"$OpenCodeDir\main.py`"" `
    -WorkingDirectory $OpenCodeDir `
    -RedirectStandardOutput $OpenCodeLog `
    -RedirectStandardError $OpenCodeLog `
    -NoNewWindow `
    -PassThru

$openProc.Id | Out-File (Join-Path $OpenCodeDir "logs" "opencode.pid")
$openProc.Id | Out-File $PidFile -Append
Write-Host "  PID: $($openProc.Id)  日志: $OpenCodeLog" -ForegroundColor Gray

# ── 启动 claude 实例（同级目录）─────────────────────────────
$ClaudeDir = Join-Path (Split-Path $ScriptDir -Parent) "cli_lark_bridge_claudecode"
$ClaudeLog = Join-Path $ClaudeDir "logs" "claudecode.log"
New-Item -ItemType Directory -Force -Path (Join-Path $ClaudeDir "logs") | Out-Null

Write-Host "[启动] claude bridge..." -ForegroundColor Green

$claudeProc = Start-Process -FilePath $Python `
    -ArgumentList "`"$ClaudeDir\main.py`"" `
    -WorkingDirectory $ClaudeDir `
    -RedirectStandardOutput $ClaudeLog `
    -RedirectStandardError $ClaudeLog `
    -NoNewWindow `
    -PassThru

$claudeProc.Id | Out-File (Join-Path $ClaudeDir "logs" "claudecode.pid")
$claudeProc.Id | Out-File $PidFile -Append
Write-Host "  PID: $($claudeProc.Id)  日志: $ClaudeLog" -ForegroundColor Gray

# ── 完成 ────────────────────────────────────────────────────
Write-Host ""
Write-Host "[完成] 两个服务已后台启动" -ForegroundColor Green
Write-Host ""
Write-Host "  查看日志:" -ForegroundColor Cyan
Write-Host "    Get-Content '$OpenCodeLog' -Tail 20"
Write-Host "    Get-Content '$ClaudeLog' -Tail 20"
Write-Host ""
Write-Host "  停止: .\stop_bridges.ps1"
