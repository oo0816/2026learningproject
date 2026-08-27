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

**答**：

### Q2: MCP 和普通 API 调用的区别是什么？为什么 agent 需要 MCP？

**答**：

### Q3: A2A 和 L5 的 Supervisor 模式有什么关系？A2A 是唯一的 Agent 间通信方式吗？

**答**：

---

## 四、画一张关系图

（用 ASCII 或文字描述 Skill / Tool / MCP / A2A 之间的关系）

```
（在此画图）
```
