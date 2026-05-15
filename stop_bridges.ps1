# ============================================================
# lark-cli-bridge 停止脚本
# ============================================================

$LogDir = Join-Path (Split-Path -Parent $MyInvocation.MyCommand.Path) "logs"
$PidFile = Join-Path $LogDir "services.pid"

if (-not (Test-Path $PidFile)) {
    Write-Host "[提示] 没有找到运行中的服务" -ForegroundColor Yellow
    exit 0
}

$procIds = Get-Content $PidFile
$stopped = 0

foreach ($procId in $procIds) {
    try {
        $proc = Get-Process -Id $procId -ErrorAction SilentlyContinue
        if ($proc) {
            Write-Host "[停止] PID $procId ($($proc.ProcessName))" -ForegroundColor Yellow
            Stop-Process -Id $procId -Force
            $stopped++
        } else {
            Write-Host "[过期] PID $procId 已不存在" -ForegroundColor Gray
        }
    } catch {
        Write-Host "[过期] PID $procId 已不存在" -ForegroundColor Gray
    }
}

Remove-Item $PidFile -Force
Write-Host "[完成] 已停止 $stopped 个服务" -ForegroundColor Green
