# lark-cli-bridge

**飞书 × CLI 工具桥接** — 通过飞书即时消息远程操控本机 CLI（opencode / claude），流式卡片实时返回结果。

## 背景

在远程开发场景中，经常需要通过手机或平板快速调用本机 CLI 工具（代码分析、文件操作、命令执行等）。lark-cli-bridge 将飞书变成 CLI 的远程终端：你发消息，本机执行，结果流式推送回飞书卡片。

核心流程：

```
飞书消息 → WebSocket 长连接 → Python 桥接 → CLI subprocess → 流式解析 → 飞书卡片（实时更新）
```

## 功能

- **双 CLI 支持** — 兼容 [opencode](https://github.com/nicepkg/opencode) 和 [claude](https://github.com/anthropics/claude-code)，通过 `.env` 切换
- **多桥接并发** — 同一份代码可同时运行 opencode + claude 两个桥接（各自独立飞书应用）
- **流式卡片推送** — CLI 输出实时更新飞书卡片（400ms 间隔、4000 字截断、工具调用进度展示）
- **会话持久化** — opencode serve 模式支持 `--attach --session` 跨消息保持对话上下文
- **图片识别** — 支持接收飞书图片消息，下载后传给 CLI 分析
- **命令控制** — `/new` 开启新会话、`/stop` 终止当前任务
- **自动打断** — 新消息到达自动停止当前运行，立即响应最新请求
- **自适应看门狗** — 空闲时定时重启防假死，活跃对话中不打断
- **PID 锁** — 防止 NSSM 快速重启导致多实例并发
- **会话隔离** — 不同 CLI 类型使用独立会话目录

## 环境要求

- Windows / Linux / macOS
- Python 3.11+
- 飞书企业自建应用（[open.feishu.cn](https://open.feishu.cn/app)）

## 快速开始

### 1. 克隆并安装依赖

```bash
git clone <repo-url>
cd lark-cli-bridge
pip install -r requirements.txt
```

### 2. 配置 `.env`

```bash
cp .env.example .env
```

编辑 `.env`，填入飞书应用凭证和 CLI 配置：

```ini
# 飞书应用凭证（必填）
FEISHU_APP_ID=cli_xxxxxxxxxxxxxxxx
FEISHU_APP_SECRET=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# CLI 类型：opencode / claude
CLI_TYPE=opencode

# CLI 工作目录
CLI_WORK_DIR=D:/project

# opencode serve 模式（推荐，支持会话持久化）
OPENCODE_SERVE_URL=http://localhost:4096
OPENCODE_SERVE_PASSWORD=your-password

# 上线通知接收人（飞书 open_id，可选）
OWNER_OPEN_ID=ou_xxxxxxxxxxxxxxxx
```

### 3. 启动

```bash
python main.py
```

成功启动后，向飞书应用发送消息即可开始对话。

### 4. 飞书应用配置要点

在飞书开放平台完成：
1. **添加应用能力** → 开启「机器人」
2. **权限管理** → 添加 `im:message:send_as_bot`、`im:message:read`、`im:message:reaction` 等权限
3. **事件订阅** → 订阅 `im.message.receive_v1` 事件

## 同时运行 opencode + claude

一份代码可以同时跑两个桥接，各自连接独立的飞书应用：

### 方式一：启动脚本

```powershell
# Windows
.\start_bridges.ps1
.\stop_bridges.ps1

# Linux / macOS
./start_bridges.sh
./stop_bridges.sh
```

### 方式二：手动启动

```bash
# Windows PowerShell
$env:BRIDGE_NAME="opencode"; python main.py
$env:BRIDGE_NAME="claude"; python main.py

# Linux / macOS
BRIDGE_NAME=opencode python main.py &
BRIDGE_NAME=claude python main.py &
```

### 配置说明

`.env` 中不带前缀的配置作为默认值（即 opencode）。另一个桥接通过前缀覆盖：

```ini
# 默认（opencode）
FEISHU_APP_ID=cli_xxx
CLI_TYPE=opencode

# claude 桥接（BRIDGE_NAME=claude 时优先读取）
CLAUDE_FEISHU_APP_ID=cli_yyy
CLAUDE_CLI_TYPE=claude
CLAUDE_CLI_WORK_DIR=D:/project
```

规则：`BRIDGE_NAME=claude` → 优先读 `CLAUDE_FEISHU_APP_ID`，未设置则回退读 `FEISHU_APP_ID`。

## 项目结构

```
lark-cli-bridge/
├── main.py              # 主入口：WebSocket 连接、消息路由、看门狗、PID 锁
├── cli_runner.py        # CLI 子进程管理，封装 opencode / claude 调用与流式解析
├── feishu_client.py     # 飞书 API 客户端：消息收发、卡片构建、图片下载
├── bot_config.py        # 配置管理，从 .env 读取，支持 BRIDGE_NAME 前缀
├── session_store.py     # 会话持久化，用户级 session 映射
├── run_control.py       # 任务运行控制，管理活跃 CLI 进程的启停
├── start_bridges.ps1    # Windows 双服务启动脚本
├── stop_bridges.ps1     # Windows 双服务停止脚本
├── start_bridges.sh     # Linux/macOS 双服务启动脚本
├── stop_bridges.sh      # Linux/macOS 双服务停止脚本
├── deploy/
│   ├── install_service.ps1   # NSSM 单服务一键安装（交互式）
│   └── install_services.ps1  # NSSM 双服务快速安装（自动设 BRIDGE_NAME）
├── .env.example         # 配置文件模板
├── LICENSE              # MIT License
└── requirements.txt     # Python 依赖
```

## 部署为 Windows 服务

使用 NSSM 将桥接注册为 Windows 服务，支持开机自启、崩溃自动重启。

### 单实例部署

以管理员身份运行：

```powershell
.\deploy\install_service.ps1
```

### 双实例部署（opencode + claude 同时运行）

```powershell
.\deploy\install_services.ps1
```

脚本会自动通过 `AppEnvironmentExtra` 为每个服务设置 `BRIDGE_NAME`。安装后启动：

```powershell
nssm start CLILarkBridge-OpenCode
nssm start CLILarkBridge-Claude
```

### 后台运行（免服务）

**Windows:**

```powershell
.\start_bridges.ps1    # 启动 opencode + claude 后台进程
.\stop_bridges.ps1     # 停止所有后台进程
```

**Linux / macOS:**

```bash
./start_bridges.sh     # 启动 opencode + claude 后台进程
./stop_bridges.sh      # 停止所有后台进程
```

日志输出到 `logs/` 目录。

## 消息命令

| 命令 | 作用 |
|------|------|
| `/new` | 开启新会话，清空对话上下文 |
| `/stop` | 终止当前正在执行的 CLI 任务 |
| 图片消息 | 下载后传给 CLI 分析 |
| 文本消息 | 作为 prompt 发送给 CLI，流式返回结果 |

## 开发说明

本项目基于 [joewongjc/feishu-claude-code](https://github.com/joewongjc/feishu-claude-code)（MIT 协议）修改而来。

**借用模块：**
- `session_store.py` — 会话持久化骨架
- `cli_runner.py` — Claude stream-json 流式解析逻辑
- `run_control.py` — 任务中断与进程控制

**精简模块（未保留）：**
- 群聊支持、斜杠命令菜单、模型切换、按钮交互
- CLI handover、ngrok 回调

**新增模块：**
- opencode CLI 适配（serve 模式 + 传统模式）
- PID 锁防多实例并发
- 自适应看门狗（空闲检测 + 定时重启）
- 已读表情回执（替代文本消息）
- NSSM Windows 服务部署脚本
- BRIDGE_NAME 多桥接前缀机制
- Linux 启动脚本

## 技术细节

- **飞书 SDK** — 使用 `lark-oapi` WebSocket 长连接，3 秒内必须返回 HTTP 200 否则重推，实际处理在独立 asyncio 事件循环中异步完成
- **流式输出** — claude 模式解析 `stream-json` 逐行输出；opencode 模式读取完整 stdout
- **卡片协议** — 飞书消息卡片（`interactive` 类型），通过 `patch` API 实时更新内容实现打字机效果
- **子进程健康** — 静默 5 分钟检测子进程存活，无活动则终止防挂死
- **看门狗** — 每 5 分钟检查，仅在运行超 4 小时且空闲超 30 分钟时主动退出（让 NSSM 拉起新进程）
