# Agent 学习路线图 · B+C 工程+产品双线

> 核心理念：既要能拆开轮子看懂怎么造的（B 工程线），也要能熟练驾驶（C 产品线）。
> 每个阶段必须完成产出物才能打勾进入下一阶段。

---

## 总览

```
L0  Agent 认知        ████░░░░░░░░░░░░░░░░  10%
L1  最小 Agent Loop    ████░░░░░░░░░░░░░░░░  10%  ← 第一个里程碑
L2  工具+记忆+RAG      ████████░░░░░░░░░░░░  15%
L3  Harness 源码拆解   ████████████░░░░░░░░  20%  ← 核心阶段
L4  Skills + 协议      ████████████████░░░░  15%
L5  多Agent + 评测     ██████████████████░░  15%
L6  交付真实项目       ████████████████████  15%  ← 最终产出
```

---

## Level 0：Agent 认知（1-2天）

### 学习目标
区分 chatbot / workflow / agent / multi-agent，掌握基本循环，知道何时不用 agent。

### 必读材料
- [ ] [Anthropic: Building effective agents](https://www.anthropic.com/engineering/building-effective-agents)
- [ ] [OpenAI: A practical guide to building agents](https://openai.com/business/guides-and-resources/a-practical-guide-to-building-ai-agents/)

### 产出物（缺一不可）
- [ ] `notes/l0-agent-basics.md` — 回答三个问题：
  1. 我的什么场景需要 agent 而不是 workflow？
  2. Agent 的基本循环每一步在做什么？
  3. 什么时候绝对不该用 agent？（列 3 个你实际遇到的场景）

### B线验证
- [ ] 能口头解释 agent loop 的 4 个阶段，不需要看笔记

### C线验证
- [ ] 找出 Claude Code 里你日常用的 3 个场景，判断它们分别是 workflow 还是 agent

---

## Level 1：最小 Agent Loop（2-3天）🔴 第一个里程碑

### 学习目标
用 Python 从零写一个能选择工具、调用工具、根据结果继续决策的最小 agent，不超过 200 行。

### 具体步骤
- [ ] 调通一个 LLM API（推荐 OpenAI 兼容接口或 Anthropic）
- [ ] 让模型输出结构化 JSON（function calling）
- [ ] 定义 2-3 个工具函数（calculator / get_weather / search）
- [ ] 解析模型的 tool call，执行工具，把结果喂回模型
- [ ] 加最大步数限制 + 超时 + 错误处理
- [ ] 跑通 3 个测试用例，记录每次的 tool 调用链

### 产出物
- [ ] `projects/l1-mini-agent/main.py` — 完整可运行
- [ ] `projects/l1-mini-agent/README.md` — 怎么运行、依赖、示例输出
- [ ] `projects/l1-mini-agent/test_cases.md` — 3 个测试用例及输出截图

### B线验证
- [ ] agent loop 是 while True 还是 for 循环？为什么？
- [ ] 如果工具返回错误，你的 agent 怎么处理？
- [ ] 如果模型没有调用工具直接回答了，你的代码会怎么做？

### C线验证
- [ ] 对比你自己的 agent 和 Claude Code 的工具调用流程，列 2 个相同点和 2 个不同点

---

## Level 2：工具调用 + 记忆 + RAG（4-5天）

### 学习目标
让 agent 具备长期记忆、能检索外部知识、能处理多种类型的工具，并正确区分记忆层级。

### 具体步骤
- [ ] 给 agent 接入搜索工具（SerpAPI 或 Tavily）
- [ ] 实现简单 RAG：文档分块 → embedding → 向量检索 → 带引用回答
- [ ] 区分三层记忆：对话上下文（messages） / 会话记忆（session store） / 长期记忆（persistent）
- [ ] 处理工具异常：空结果、超时、格式错误、重复调用
- [ ] 给 agent 的输出加引用来源

### 产出物
- [ ] `projects/l2-rag-agent/main.py` — 带记忆和 RAG 的 agent
- [ ] `projects/l2-rag-agent/README.md`
- [ ] `notes/l2-memory-model.md` — 画一张图，说明三层记忆的区别和实现方式

### B线验证
- [ ] 对话上下文和长期记忆的实现方式有什么本质不同？
- [ ] 向量检索返回了不相关的结果，agent 应该怎么处理？

### C线验证
- [ ] 读一个你现有的 SKILL.md，分析它的"记忆依赖"——哪些信息假设 agent 已经记住了？

---

## Level 3：Harness 源码拆解（5-7天）🔴 核心阶段

### 学习目标
深入拆解一个现代 agent harness 的架构，理解 agent loop、tool registry、permission gate、session store、context compaction 各模块的职责和交互。

### 主线材料
- [ ] learn-claude-code 仓库 — 跟一遍，跑通最小示例
- [ ] claw0 仓库 — 选读 Chapter 1-5（agent loop → session → gateway → memory）

### 必答问题（边读边记）
- [ ] agent loop 在哪个文件？核心逻辑多少行？
- [ ] 工具是怎么注册的？tool schema 包含哪些字段？
- [ ] 权限控制在哪里？每次调工具都要确认还是分级别？
- [ ] session 是怎么存、怎么恢复的？
- [ ] 上下文太长时怎么压缩？触发条件是什么？

### 产出物
- [ ] `notes/l3-harness-anatomy.md` — 回答上面 5 个问题，每问不少于 200 字
- [ ] `projects/l3-nano-harness/main.py` — 从 Level 1 的 agent 升级，加入：
  - tool registry（注册/查找/校验 schema）
  - permission gate（分 safe / needs_approval / blocked 三级）
  - session store（保存/恢复对话）
  - 最大步数 + 超时 + 错误分类日志

### B线验证
- [ ] 你的 nano harness 和 learn-claude-code 的差异在哪？列 3 点
- [ ] 如果要在你的 harness 上加一个 subagent，架构上需要改哪里？

### C线验证
- [ ] 用 darwin-skill 给你自己写的某个 SKILL.md 打分，记录初始分数
- [ ] 根据评分报告改一版，再打分，记录涨幅

---

## Level 4：Skills + MCP + 能力打包（3-4天）

### 学习目标
理解 skill / tool / MCP / A2A / ACP 的区别和协作关系，能写出高质量的可复用 skill。

### 具体步骤
- [ ] 阅读 Claude Code Skills 官方文档 + OpenClaw Skills 设计文档
- [ ] 理解：Skill 是流程知识包，Tool 是可调用接口，MCP 连接外部数据源
- [ ] 亲手写一个完整 SKILL.md：触发条件、步骤、脚本、模板、smoke test
- [ ] 接一个 MCP server（比如 filesystem 或 postgres）
- [ ] 用 darwin-skill 跑 2 轮优化，记录分数变化

### 产出物
- [ ] `skills/my-first-skill/SKILL.md` — 自选主题（如 code-review / release-note / api-doc-gen）
- [ ] `skills/my-first-skill/` 下至少有 1 个脚本 + 1 个模板
- [ ] `notes/l4-skills-vs-tools.md` — Skill vs Tool vs MCP vs A2A 的对比表
- [ ] `notes/l4-skill-optimization-log.md` — darwin-skill 优化记录，含每一轮的分数和改动

### B线验证
- [ ] 一个 SKILL.md 被 agent 加载后，agent 的 system prompt 里多了什么？
- [ ] MCP 和普通 API 调用的区别是什么？为什么 agent 需要 MCP？

### C线验证
- [ ] 你写的 skill 被 darwin-skill 评了多少分？最低的 2 个维度是什么？你怎么改的？

---

## Level 5：多 Agent + 评测体系（5-7天）

### 学习目标
理解多 agent 是协调问题而非魔法，掌握基本的评测方法和安全边界设置。

### 具体步骤
- [ ] 理解 planner / executor / reviewer / critic / router 角色
- [ ] 用 supervisor 模式实现 2-3 个 agent 协作
- [ ] 建一套 eval：至少 15 个测试用例，记录成功/失败/成本/延迟
- [ ] 给危险操作加人工确认闸门
- [ ] 学会看 trace，定位失败发生在哪个环节

### 产出物
- [ ] `projects/l5-multi-agent/main.py` — 2-3 个 agent 协作（如 research → write → review）
- [ ] `projects/l5-multi-agent/evals.md` — 15+ 测试用例表格
- [ ] `notes/l5-agent-eval-framework.md` — 总结经验：eval 该测什么？怎么设计 bad case？

### B线验证
- [ ] 多 agent 之间怎么通信？你的实现用了什么方式？
- [ ] 如果 reviewer 一直不满意，你的系统怎么防止无限循环？

### C线验证
- [ ] 用 darwin-skill 跑你所有 skill 的回归评测
- [ ] 整理一份 "我的 Skill 质量报告"

---

## Level 6：交付真实 Agent 项目（1-2周）🔴 最终产出

### 学习目标
做一个别人能 clone 下来跑的真实 agent 项目，具备完整的日志、trace、权限、README。

### 选题方向（三选一）
- **膝关节导航术前报告 Agent**：输入影像分析结果 → 自动生成结构化术前报告 → 医生审核
- **简历智能匹配 Agent**：输入简历 + 岗位 JD → 分析匹配度 → 给出改进建议
- **个人知识助手 Agent**：接你的笔记/文档 → 用 RAG 检索 → 回答问题并引用来源

### 产出物
- [ ] `projects/l6-final-agent/` — 完整项目
  - [ ] `main.py` — 可运行
  - [ ] `README.md` — 怎么跑、怎么配 key、怎么扩展工具、有哪些限制
  - [ ] `tests/` — 至少 5 个测试用例
  - [ ] `eval_report.md` — 20 个测试用例的成功率、失败分类
  - [ ] `SKILL.md` — 项目本身打包成一个可复用 skill

### B线验证
- [ ] 项目的 agent loop 架构图
- [ ] 权限边界说明：什么操作要确认、什么自动执行、什么完全禁止

### C线验证
- [ ] 最终 darwin-skill 评分 ≥ 70 分
- [ ] 至少一个真实用户跑过你的项目并给出反馈

---

## 学习规则

### 进入下一阶段的前提
1. 当前阶段所有 checkbox 打勾
2. 产出物文件存在且内容完整
3. B线验证问题能口头回答
4. C线验证任务完成

### 每日最小投入
- 至少 1 次 git commit（记录当日进度）
- 产出物文件必须当天更新（不拖到第二天）

### 每周回顾
- 每周日写 3 句话：本周学会了什么 / 哪个概念最模糊 / 下周重点

---

## 进度仪表盘

| Level | 主题 | 状态 | 开始日期 | 完成日期 | 分数/评价 |
|-------|------|------|---------|---------|----------|
| L0 | Agent 认知 | ✅ 完成 | 2026-07-02 | 2026-07-02 | — |
| L1 | 最小 Agent Loop | ✅ 完成 | 2026-07-02 | 2026-07-03 | 三个测试全过 |
| L2 | 工具+记忆+RAG | ⬜ 未开始 | - | - | - |
| L3 | Harness 源码拆解 | ⬜ 未开始 | - | - | - |
| L4 | Skills+MCP | ⬜ 未开始 | - | - | - |
| L5 | 多Agent+评测 | ⬜ 未开始 | - | - | - |
| L6 | 交付真实项目 | ⬜ 未开始 | - | - | - |

### 总计
- 总阶段：7 个
- 已完成：2
- 总预计时间：4-6 周（全职） / 8-12 周（业余）
- 总产出物：7 个项目目录 + 6 篇笔记 + 2+ 个 skill + 最终项目

---

## 参考资料地图

| Level | B线资源 | C线资源 |
|-------|---------|---------|
| L0 | Anthropic/OpenAI 官方指南 | — |
| L1 | OpenAI Function Calling 文档 | Claude Code 工具调用流程 |
| L2 | LlamaIndex / mem0 / Letta | 你现有的 SKILL.md 分析 |
| L3 | learn-claude-code / claw0 | Claude Code 官方文档 |
| L4 | MCP 官方文档 / OpenClaw Skills | darwin-skill |
| L5 | LangGraph / AgentBench | darwin-skill 回归评测 |
| L6 | 自选项目方向 | darwin-skill 评分 ≥ 70 |
