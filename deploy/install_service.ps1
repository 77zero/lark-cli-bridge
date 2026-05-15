# ============================================================
# lark-cli-bridge NSSM Windows Service 一键部署脚本
# 以管理员身份运行此脚本
# ============================================================

param(
    [string]$ServiceName = "CLILarkBridge",
    [string]$PythonPath = "",
    [string]$WorkDir = ""
)

# 需要管理员权限
if (-NOT ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole] "Administrator")) {
    Write-Host "[错误] 请以管理员身份运行此脚本" -ForegroundColor Red
    exit 1
}

# 自动检测 Python 路径
if (-not $PythonPath) {
    $PythonPath = (Get-Command python -ErrorAction SilentlyContinue).Source
}
if (-not $PythonPath) {
    $PythonPath = (Get-Command python3 -ErrorAction SilentlyContinue).Source
}
if (-not $PythonPath) {
    Write-Host "[错误] 未找到 Python，请先安装 Python 3.11+" -ForegroundColor Red
    exit 1
}
Write-Host "[信息] Python 路径: $PythonPath" -ForegroundColor Green

# 工作目录 = 脚本所在目录
if (-not $WorkDir) {
    $WorkDir = Split-Path -Parent $MyInvocation.MyCommand.Path
    $WorkDir = Split-Path -Parent $WorkDir  # deploy/ 的上一级即项目根目录
}

# 检查 NSSM 是否安装
$nssm = Get-Command nssm -ErrorAction SilentlyContinue
if (-not $nssm) {
    Write-Host "[提示] 未检测到 NSSM，请先安装：" -ForegroundColor Yellow
    Write-Host "  winget install nssm"
    Write-Host "  或下载: https://nssm.cc/download"
    Write-Host ""
    $install = Read-Host "是否使用 winget 自动安装？(y/n)"
    if ($install -eq 'y') {
        winget install nssm
        $nssm = Get-Command nssm -ErrorAction SilentlyContinue
        if (-not $nssm) {
            Write-Host "[错误] NSSM 安装失败" -ForegroundColor Red
            exit 1
        }
    } else {
        exit 1
    }
}

$MainScript = Join-Path $WorkDir "main.py"

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  lark-cli-bridge Windows 服务部署" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  服务名  : $ServiceName"
Write-Host "  工作目录: $WorkDir"
Write-Host "  Python  : $PythonPath"
Write-Host "  主脚本  : $MainScript"
Write-Host "============================================" -ForegroundColor Cyan

# 停止已有服务
$existing = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
if ($existing) {
    Write-Host "[步骤] 停止已存在的服务..." -ForegroundColor Yellow
    nssm stop $ServiceName 2>$null
    nssm remove $ServiceName confirm 2>$null
    Start-Sleep -Seconds 2
}

# 安装服务
Write-Host "[步骤] 安装 Windows 服务..." -ForegroundColor Yellow
nssm install $ServiceName $PythonPath $MainScript
if ($LASTEXITCODE -ne 0) {
    Write-Host "[错误] 服务安装失败" -ForegroundColor Red
    exit 1
}

# 配置服务
Write-Host "[步骤] 配置服务参数..." -ForegroundColor Yellow

# 工作目录
nssm set $ServiceName AppDirectory $WorkDir

# 开机自启
nssm set $ServiceName Start SERVICE_AUTO_START

# 崩溃自动重启（延迟 5 秒防重启风暴）
nssm set $ServiceName AppExit Default Restart
nssm set $ServiceName AppRestartDelay 5000

# 输出重定向到日志文件
$LogDir = Join-Path $WorkDir "logs"
if (-not (Test-Path $LogDir)) {
    New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
}
$StdoutLog = Join-Path $LogDir "stdout.log"
$StderrLog = Join-Path $LogDir "stderr.log"
nssm set $ServiceName AppStdout $StdoutLog
nssm set $ServiceName AppStderr $StderrLog

Write-Host "[完成] 服务配置完毕" -ForegroundColor Green
Write-Host ""
Write-Host "  启动服务: nssm start $ServiceName" -ForegroundColor Cyan
Write-Host "  停止服务: nssm stop $ServiceName" -ForegroundColor Cyan
Write-Host "  查看状态: nssm status $ServiceName" -ForegroundColor Cyan
Write-Host "  查看日志: Get-Content '$StdoutLog' -Tail 50" -ForegroundColor Cyan
Write-Host "  卸载服务: nssm remove $ServiceName confirm" -ForegroundColor Cyan
Write-Host ""

# 询问是否立即启动
$start = Read-Host "是否立即启动服务？(y/n)"
if ($start -eq 'y') {
    nssm start $ServiceName
    Start-Sleep -Seconds 3
    $svc = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
    if ($svc -and $svc.Status -eq 'Running') {
        Write-Host "[成功] 服务已启动！" -ForegroundColor Green
    } else {
        Write-Host "[警告] 服务可能未成功启动，请查看日志" -ForegroundColor Yellow
    }
}
