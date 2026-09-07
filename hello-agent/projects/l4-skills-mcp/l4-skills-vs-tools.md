# L4 · Skill vs Tool vs MCP vs A2A 对比表

> L4 核心产出物：搞清楚这四个概念的区别和协作关系。

---

## 一、概念对比

| 维度 | Skill | Tool | MCP | A2A |
|------|-------|------|-----|-----|
| **中文叫法** | 技能/工作手册 | 工具 | 模型上下文协议 | Agent-to-Agent |
| **本质是什么** | 流程知识包（markdown 文档） | 可调用的函数/API | 连接外部数据源的协议标准 | Agent 之间通信的协议 |
| **谁在用** | Agent 读取后按步骤执行 | Agent 调用它来完成具体操作 | Agent 通过 MCP server 访问外部资源 | Agent A 和 Agent B 之间对话 |
| **类比** | 员工培训手册 | 螺丝刀、计算器 | 公司的数据库/文件服务器 | 两个同事开会讨论 |
| **形式** | SKILL.md 文件 | Python 函数 / REST API | MCP Server（独立进程） | 结构化消息（JSON） |
| **触发方式** | Agent 遇到匹配场景时加载 | Agent 决定调用（function calling） | Agent 通过 MCP client 连接 | Agent 之间主动或被动通信 |
| **例子** | "当用户要求 code review 时，按以下步骤..." | calculator("3+5") | 接 Google Drive 查文件 | "Researcher 把资料交给 Writer" |

---

## 二、它们怎么协作？

```
用户: "帮我审查最近的代码变更，然后发邮件给团队"

1. Agent 识别到 "审查代码" → 加载 code-review SKILL.md
2. SKILL.md 步骤 1: 用 git diff 工具获取变更
3. Agent 调用了 Tool: git_diff()
4. SKILL.md 步骤 2: 检查代码规范
5. Agent 通过 MCP 连接公司的代码规范文档
6. SKILL.md 步骤 3: 生成审查报告
7. SKILL.md 步骤 4: 发邮件
8. Agent 调用了 Tool: send_email()
```

Skill 是"导演"，Tool 和 MCP 是导演手里的"演员和道具"。

---

## 三、关键区分题（自己答）

### Q1: 一个 Skill 可以调多个 Tool 吗？一个 Tool 可以被多个 Skill 调用吗？

**答**：都可以。

- **一个 Skill 调多个 Tool**：Skill 本身不执行任何东西，它是注入的"操作规程"；正文里会指挥模型按步骤调用若干 Tool。例：`japanese-exam-review` 正文里既让模型跑 `python scripts/parse_ppt.py`（Bash 工具）、又按需 Read `guide_style.py` 看方法签名。
- **一个 Tool 被多个 Skill 复用**：Tool 是最底层能力，Skill 在它之上抽象。同一套内置工具（Read/Edit/Bash）是所有 skill 共同的"手"。Tool 不认 skill——谁加载了就听谁指挥。

**记忆点**：Skill 是"章法/导演"，Tool 是"手/演员"，所以多对多是常态。

### Q2: MCP 和普通 API 调用的区别是什么？为什么 agent 需要 MCP？

**答**：区别不在"有没有 HTTP 请求"（MCP 底层也是 JSON-RPC 2.0），而在**谁去适配谁**。

| 维度 | 直接调 API | MCP |
|---|---|---|
| 接口 | 每个服务自定义（URL/鉴权/字段都不同） | 固定方法：`tools/list`、`tools/call`… |
| 谁做适配 | agent 代码为每服务各写一份 handler | server 自适配，client 只认协议 |
| 工具发现 | 写死在代码里 | 运行时 `tools/list` 动态发现（含 JSON Schema） |
| 复用性 | N 服务 × M 客户端 = N×M 份代码 | N+M：接一次所有客户端通用 |
| 传输 | 基本远程 HTTP | 可本地 stdio（私密数据不出本机，key 不交给厂商） |

**为什么需要 MCP**：① 接多个服务时代码量从"每服务一份"降为"每服务一个配置"；② 生态一次接入到处复用；③ stdio 模式让 agent 安全地碰本地私密数据/数据库。**代价**是协议握手/包装比直连 REST 啰嗦——单次简单接入直接写函数调 API 更干净。

**类比**：MCP ≈ JDBC/ODBC 之于数据库——定统一接口，各服务自己写驱动。

### Q3: A2A 和 L5 的 Supervisor 模式有什么关系？A2A 是唯一的 Agent 间通信方式吗？

**答**：不是一个层面的东西。

- **Supervisor 模式（L5）**是**编排架构**：一个中央 supervisor agent 派任务给 worker，靠的是"父 agent 代码里写死的委派逻辑"（L3 学过：subagent 可以是父 agent 的一个普通工具）。
- **A2A 是通信协议**：管"两个独立 agent 怎么发现对方能力、委派任务、跟踪进度取结果"，配套 `agent-card` JSON 描述身份/能力/接口。
- **关系**：一个团队内部用 Supervisor 编排，跨团队/跨系统/跨厂商协作才需要 A2A 这种标准协议把不认识的 agent 接起来。
- **A2A 不是唯一方式**：同一 harness 内的 agent 可以共享进程内通信（直接函数调用/消息队列）、走 Supervisor；同厂商生态还有各自私有协议。A2A 的价值在**异构、互不认识的 agent 之间**。

---

## 四、画一张关系图

（用 ASCII 或文字描述 Skill / Tool / MCP / A2A 之间的关系）

```
（在此画图）
```
