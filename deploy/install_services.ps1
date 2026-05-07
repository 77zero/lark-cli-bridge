# ============================================================
# cli_lark_bridge 服务安装命令
# 在管理员 PowerShell 中逐条运行
# ============================================================

$python = (Get-Command python).Source

# ── opencode 实例 ──────────────────────────────────────────
$name_opencode = "CLILarkBridge-OpenCode"
$dir_opencode = "D:\Project\cli_lark_bridge"

nssm install $name_opencode $python "$dir_opencode\main.py"
nssm set $name_opencode AppDirectory $dir_opencode
nssm set $name_opencode Start SERVICE_AUTO_START
nssm set $name_opencode AppExit Default Restart
nssm set $name_opencode AppRestartDelay 5000
nssm set $name_opencode AppStdout "$dir_opencode\logs\stdout.log"
nssm set $name_opencode AppStderr "$dir_opencode\logs\stderr.log"

# ── claude 实例 ────────────────────────────────────────────
$name_claude = "CLILarkBridge-Claude"
$dir_claude = "D:\Project\cli_lark_bridge_claude"

nssm install $name_claude $python "$dir_claude\main.py"
nssm set $name_claude AppDirectory $dir_claude
nssm set $name_claude Start SERVICE_AUTO_START
nssm set $name_claude AppExit Default Restart
nssm set $name_claude AppRestartDelay 5000
nssm set $name_claude AppStdout "$dir_claude\logs\stdout.log"
nssm set $name_claude AppStderr "$dir_claude\logs\stderr.log"

Write-Host ""
Write-Host "安装完成。启动服务：" -ForegroundColor Green
Write-Host "  nssm start $name_opencode"
Write-Host "  nssm start $name_claude"
