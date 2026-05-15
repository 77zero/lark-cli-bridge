# Changelog

## v0.1.0 (2026-05-16)

首个版本，基于 [feishu-claude-code](https://github.com/nicepkg/feishu-claude-code) 架构简化改造。

### 双 CLI 支持
- 兼容 opencode 1.15.0 和 Claude Code 2.1.142，通过 `CLI_TYPE` 切换
- 多桥接并发：同一份代码可同时运行 opencode + claude 两个实例（各自独立飞书应用）

### 飞书集成
- WebSocket 长连接接收私聊消息
- 流式卡片实时推送 CLI 响应（支持文本 + 工具调用进度）
- 支持图片消息（下载后传给 CLI 分析）
- `/new` 开启新会话、`/stop` 终止当前任务
- 上线通知卡片

### 会话管理
- opencode：`--session` 跨消息保持对话上下文
- claude：`--resume` 恢复会话，stream-json 流式解析
- 会话按 CLI 类型隔离存储

### 服务化
- Windows NSSM 服务一键部署脚本
- Linux/macOS nohup 后台启动脚本
- PowerShell + Bash 双启动/停止脚本
- PID 锁防多实例并发
- 自适应看门狗（空闲 30 分钟后 4 小时自动重启）

### 配置
- `.env` 三块结构：必填 → 可选 → 多桥接覆盖
- `BRIDGE_NAME` 前缀机制支持多桥接实例独立配置
- opencode serve 模式自动拉起（地址由端口拼出）
