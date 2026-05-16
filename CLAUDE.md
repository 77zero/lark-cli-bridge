# CLAUDE.md

**输出语言：所有回复、代码注释、commit message、文档均使用中文。**

> 2026-05-16 v1.1 — 从全局准则升级为项目特化行为约束，新增架构约束/反模式/工作流规则。
> 方法论参考：[[agent-behavior-preparation|Agent 行为准备五层模型]]

## 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them - don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

## 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

## 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it - don't delete it.

When your changes create orphans:
- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: Every changed line should trace directly to the user's request.

## 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:
- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:
```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

**本项目的验证特殊性**：
- 涉及飞书 API → 无法自动化验证，必须说明手动测试步骤
- 涉及 CLI 子进程 → 必须给出手动验证命令
- 涉及多桥接 → 必须分别验证 opencode 和 claude 模式

---

## 5. Hard Blocks（绝对禁止）

以下规则在任何情况下不得违反：

- **绝不直接修改 `.env` 文件** — 只能通过 `.env.example` 告知用户需要改什么
- **绝不硬编码飞书凭证或 CLI 路径** — 所有配置通过 `bot_config.py` 从环境变量读取
- **绝不删除或重命名现有模块文件** — `main.py` / `cli_runner.py` / `feishu_client.py` / `bot_config.py` / `session_store.py` / `run_control.py` 除非用户明确要求
- **绝不修改 `deploy/` 目录下的安装脚本** — 除非用户明确要求
- **绝不绕过 PID 锁机制添加并发入口**
- **绝不提交 `.env` / `.env.bak` / `logs/` 目录内容**

## 6. Anti-Patterns（阻断违规）

以下行为触发时必须立即自纠：

- **不要在 `cli_runner.py` 中添加新 CLI 类型** — 先检查 `openCodeRunner` / `ClaudeRunner` 适配模式是否可复用
- **不要用 `print()` 替代日志** — 所有日志必须用 Python `logging` 模块输出到 `logs/` 目录
- **不要假设 opencode 和 claude 的参数相同** — 每个 CLI 类型必须独立验证
- **不要在卡片更新的异步循环中添加同步阻塞操作** — 卡片流式推送必须在 400ms 间隔内完成
- **不要让看门狗在活跃对话中触发重启** — 修改看门狗逻辑时必须检查 30min 空闲检测

## 7. 架构约束

本项目采用 **6 模块架构**，各模块职责边界不可逾越：

| 模块 | 职责 | 禁止 |
|------|------|------|
| `main.py` | WebSocket 连接、消息路由、看门狗、PID 锁 | 不写 CLI 调用逻辑 |
| `cli_runner.py` | CLI 子进程管理、流式解析 | 不直接操作飞书 API |
| `feishu_client.py` | 飞书 API 客户端 | 不写 CLI 逻辑 |
| `bot_config.py` | 配置读取、BRIDGE_NAME 前缀 | 不写业务逻辑 |
| `session_store.py` | 会话持久化 | 不写 IO 操作 |
| `run_control.py` | 任务启停控制 | 不写消息处理 |

新增功能时：
1. 先判断属于哪个模块边界
2. 如果不属于任一模块 → 创建新文件，不塞进已有模块
3. CLI 类型新增 → **必须同时适配** `cli_runner.py` 和 `bot_config.py` 两个模块

## 8. 工作流规则

### 开发新功能
1. 先读 `README.md` 理解项目架构
2. 确定功能属于哪个模块（见架构约束表）
3. 实现 → 本地 `python main.py` 验证 → 提交

### 新增 CLI 支持
1. `cli_runner.py` 添加适配子类
2. `bot_config.py` 添加 `{CLI_TYPE}_` 前缀配置项
3. `.env.example` 更新配置模板
4. `README.md` 更新环境要求表格
5. 本地分别测试 opencode 和 claude 模式

### 部署前检查
- PID 锁机制未被绕过
- 看门狗参数未被改变（4h 运行 / 30min 空闲阈值）
- `.env.example` 与实际 `bot_config.py` 读取的变量一致
- `deploy/` 脚本中的 NSSM 服务名称未被修改

## 9. 测试要求

- 新增模块 → 必须包含单元测试
- 修改 `cli_runner.py` 流式解析逻辑 → 必须有回归测试
- 修改飞书 API 调用 → 必须先 mock 验证
- 修改看门狗/PID 锁 → 必须本地运行 `main.py` 不报错

---

## 10. Git 管理准则

- 每完成一个独立功能或修复 → 立即 commit，不等攒多了再交
- Commit message 用中文，描述做了什么、为什么（不描述怎么做的）
- 新建文件、删除文件、修改文件 → 都用 `git add <具体文件>`，不用 `git add -A` 或 `git add .`
- 如果 commit 后发现有遗漏 → 新建一个 commit 修正，不 amend 已推送的 commit
- 不改动 `.gitignore` 或 git 配置，除非用户明确要求
- 不执行 force push、`git reset --hard`、`git checkout --` 等破坏性操作，除非用户明确要求
