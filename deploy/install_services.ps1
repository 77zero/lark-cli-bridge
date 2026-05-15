# ============================================================
# lark-cli-bridge 双服务安装脚本
# 在管理员 PowerShell 中运行
# ============================================================

$python = (Get-Command python).Source

# 项目根目录 = 脚本所在 deploy/ 的上一级
$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)

# ── opencode 实例 ──────────────────────────────────────────
$name_opencode = "CLILarkBridge-OpenCode"

nssm install $name_opencode $python "$ProjectRoot\main.py"
nssm set $name_opencode AppDirectory $ProjectRoot
nssm set $name_opencode Start SERVICE_AUTO_START
nssm set $name_opencode AppExit Default Restart
nssm set $name_opencode AppRestartDelay 5000
nssm set $name_opencode AppEnvironmentExtra "BRIDGE_NAME=opencode"
nssm set $name_opencode AppStdout "$ProjectRoot\logs\opencode-stdout.log"
nssm set $name_opencode AppStderr "$ProjectRoot\logs\opencode-stderr.log"

# ── claude 实例 ────────────────────────────────────────────
$name_claude = "CLILarkBridge-Claude"

nssm install $name_claude $python "$ProjectRoot\main.py"
nssm set $name_claude AppDirectory $ProjectRoot
nssm set $name_claude Start SERVICE_AUTO_START
nssm set $name_claude AppExit Default Restart
nssm set $name_claude AppRestartDelay 5000
nssm set $name_claude AppEnvironmentExtra "BRIDGE_NAME=claude"
nssm set $name_claude AppStdout "$ProjectRoot\logs\claude-stdout.log"
nssm set $name_claude AppStderr "$ProjectRoot\logs\claude-stderr.log"

Write-Host ""
Write-Host "安装完成。启动服务：" -ForegroundColor Green
Write-Host "  nssm start $name_opencode"
Write-Host "  nssm start $name_claude"
