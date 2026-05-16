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

### v1.1 (2026-05-16) — CLAUDE.md 升级

基于 [Agent 行为准备五层模型](https://github.com/77zero/lark-cli-bridge/blob/main/CLAUDE.md) 方法论，将 CLAUDE.md 从全局准则拷贝升级为项目特化 Agent 行为约束：

- **新增 Hard Blocks**（6 条）：禁止硬编码凭证、禁止绕过 PID 锁、禁止直接修改 .env 等
- **新增 Anti-Patterns**（5 条）：print() 替代日志、async 循环同步阻塞、假设 CLI 参数相同 等
- **新增架构约束**：6 模块职责边界表 + 跨模块变更规则
- **新增工作流规则**：新功能开发 / 新增 CLI 支持 / 部署前检查 三套流程
- **新增测试要求**：回归测试、mock 验证、部署前本地运行
- **细节补充**：飞书/CLI 子进程/多桥接三种场景的验证特殊性
- 行数：81 → 130，覆盖从 2 层（软准则+Git）扩展为完整五层
