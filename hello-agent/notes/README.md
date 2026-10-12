# Agent 学习路线图 · B+C 工程+产品双线

> 核心理念：既要能拆开轮子看懂怎么造的（B 工程线），也要能熟练驾驶（C 产品线）。
> 每个阶段必须完成产出物才能打勾进入下一阶段。

---

## 总览

```
L0  Agent 认知        ████████████████████ 100%  ✅ 内容完成，C线场景待补留痕
L1  最小 Agent Loop    ████████████████████ 100%  ✅ 第一个里程碑
L2  工具+记忆+RAG      █████████████████░░░  85%  ✅ 主体完成，测试/C线待补
L3  Harness 源码拆解   ███████████████████░  95%  ✅ 核心阶段完成，claw0未选读
L4  Skills + 协议      ████████████████░░░░  80%  🔵 Skill完成，真实MCP待接
L5  多Agent + 评测     █████████░░░░░░░░░░░  45%  🔵 主流程完成，eval待跑
L6  交付真实项目       █░░░░░░░░░░░░░░░░░░░   5%  ⬜ 仅脚手架
```

---

## Level 0：Agent 认知（1-2天）

### 学习目标
区分 chatbot / workflow / agent / multi-agent，掌握基本循环，知道何时不用 agent。

### 必读材料
- [x] [Anthropic: Building effective agents](https://www.anthropic.com/engineering/building-effective-agents)
- [x] [OpenAI: A practical guide to building agents](https://openai.com/business/guides-and-resources/a-practical-guide-to-building-ai-agents/)

### 产出物（缺一不可）
- [x] `notes/l0-reading-summary.md` — 已覆盖三个核心问题：
  1. 我的什么场景需要 agent 而不是 workflow？
  2. Agent 的基本循环每一步在做什么？
  3. 什么时候绝对不该用 agent？（列 3 个你实际遇到的场景）

### B线验证
- [x] 能口头解释 agent loop 的 4 个阶段，不需要看笔记

### C线验证
- [x] 找出 Claude Code 里你日常用的 3 个场景（待单独记录），判断它们分别是 workflow 还是 agent

---

## Level 1：最小 Agent Loop（2-3天）🔴 第一个里程碑

### 学习目标
用 Python 从零写一个能选择工具、调用工具、根据结果继续决策的最小 agent，不超过 200 行。

### 具体步骤
- [x] 调通一个 LLM API（推荐 OpenAI 兼容接口或 Anthropic）
- [x] 让模型输出结构化 JSON（function calling）
- [x] 定义 2-3 个工具函数（calculator / get_weather / search）
- [x] 解析模型的 tool call，执行工具，把结果喂回模型
- [x] 加最大步数限制 + 超时 + 错误处理
- [x] 跑通 3 个测试用例，记录每次的 tool 调用链

### 产出物
- [x] `projects/l1-mini-agent/main.py` — 完整可运行
- [x] `projects/l1-mini-agent/README.md` — 怎么运行、依赖、示例输出
- [x] `projects/l1-mini-agent/test_cases.md` — 3 个测试用例及输出截图

### B线验证
- [x] agent loop 是 while True 还是 for 循环？为什么？
- [x] 如果工具返回错误，你的 agent 怎么处理？
- [x] 如果模型没有调用工具直接回答了，你的代码会怎么做？

### C线验证
- [x] 对比你自己的 agent 和 Claude Code 的工具调用流程，列 2 个相同点和 2 个不同点

---

## Level 2：工具调用 + 记忆 + RAG（4-5天）

### 学习目标
让 agent 具备长期记忆、能检索外部知识、能处理多种类型的工具，并正确区分记忆层级。

### 具体步骤
- [x] 给 agent 接入搜索工具（SerpAPI 或 Tavily）
- [x] 实现简单 RAG：文档分块 → embedding → 向量检索 → 带引用回答
- [x] 区分三层记忆：对话上下文（messages） / 会话记忆（session store） / 长期记忆（persistent）
- [x] 处理工具异常：空结果、超时、格式错误、重复调用
- [x] 给 agent 的输出加引用来源

### 产出物
- [x] `projects/l2-rag-agent/main.py` — 带记忆和 RAG 的 agent
- [x] `projects/l2-rag-agent/README.md`
- [x] `notes/l2-memory-model.md` — 画一张图，说明三层记忆的区别和实现方式

### B线验证
- [x] 对话上下文和长期记忆的实现方式有什么本质不同？
- [x] 向量检索返回了不相关的结果，agent 应该怎么处理？

### C线验证
- [ ] 读一个你现有的 SKILL.md（模板已留，验证未完成），分析它的"记忆依赖"——哪些信息假设 agent 已经记住了？

---

## Level 3：Harness 源码拆解（5-7天）🔴 核心阶段

### 学习目标
深入拆解一个现代 agent harness 的架构，理解 agent loop、tool registry、permission gate、session store、context compaction 各模块的职责和交互。

### 主线材料
- [x] learn-claude-code 仓库 — 跟一遍，跑通最小示例
- [ ] claw0 仓库（尚未选读） — 选读 Chapter 1-5（agent loop → session → gateway → memory）

### 必答问题（边读边记）
- [x] agent loop 在哪个文件？核心逻辑多少行？
- [x] 工具是怎么注册的？tool schema 包含哪些字段？
- [x] 权限控制在哪里？每次调工具都要确认还是分级别？
- [x] session 是怎么存、怎么恢复的？
- [x] 上下文太长时怎么压缩？触发条件是什么？

### 产出物
- [x] `notes/l3-harness-anatomy.md` — 回答上面 5 个问题，每问不少于 200 字
- [x] `projects/l3-nano-harness/main.py` — 从 Level 1 的 agent 升级，加入：
  - tool registry（注册/查找/校验 schema）
  - permission gate（分 safe / needs_approval / blocked 三级）
  - session store（保存/恢复对话）
  - 最大步数 + 超时 + 错误分类日志

### B线验证
- [x] 你的 nano harness 和 learn-claude-code 的差异在哪？列 3 点
- [x] 如果要在你的 harness 上加一个 subagent，架构上需要改哪里？

### C线验证
- [x] 用 darwin-skill 给你自己写的某个 SKILL.md 打分，记录初始分数
- [x] 根据评分报告改一版，再打分，记录涨幅

---

## Level 4：Skills + MCP + 能力打包（3-4天）

### 学习目标
理解 skill / tool / MCP / A2A / ACP 的区别和协作关系，能写出高质量的可复用 skill。

### 具体步骤
- [x] 阅读 Claude Code Skills 官方文档 + 触发机制
- [ ] 阅读 OpenClaw Skills 的加载、作用域和安全边界（未完成）
- [x] 理解：Skill 是流程知识包，Tool 是可调用接口，MCP 连接外部数据源
- [x] 亲手写一个完整 SKILL.md：触发条件、步骤、脚本、模板、smoke test
- [ ] 接一个真实 MCP server（当前只有手写协议 demo）（比如 filesystem 或 postgres）
- [x] 用 darwin-skill 跑 4 轮优化，75.7 → 82.7，记录分数变化

### 产出物
- [x] `skills/japanese-exam-review/SKILL.md` — 第一个完整 skill（自选主题：日语 CS 复习 PDF 生成器），含触发条件/双通路/脚本/模板/smoke test
- [x] `skills/japanese-exam-review/` 下含脚本 + 模板 + smoke_test + test-prompts
- [x] `projects/l4-skills-mcp/l4-skills-vs-tools.md` — Skill vs Tool vs MCP vs A2A 的对比表（原产出位置，笔记路径见 notes/l4-skill-mcp-qna.md）
- [x] `projects/l4-skills-mcp/l4-skill-optimization-log.md` — darwin-skill 优化记录（75.7→82.7，4 轮全 keep）

### B线验证
- [x] 一个 SKILL.md 被 agent 加载后，agent 的 system prompt 里多了什么？
- [x] MCP 和普通 API 调用的区别是什么？为什么 agent 需要 MCP？

### C线验证
- [x] 你写的 skill 被 darwin-skill 评了多少分？最低的 2 个维度是什么？你怎么改的？

---

## Level 5：多 Agent + 评测体系（5-7天）

### 学习目标
理解多 agent 是协调问题而非魔法，掌握基本的评测方法和安全边界设置。

### 具体步骤
- [ ] 理解 planner / executor / reviewer / critic / router 角色（Researcher/Writer/Reviewer 已落地，其余待深入）
- [x] 用 supervisor 模式实现 2-3 个 agent 协作
- [ ] 建一套 eval：至少 15 个测试用例（表格已建，结果全部未跑），记录成功/失败/成本/延迟
- [x] 给危险操作加人工确认闸门
- [x] 学会看 trace，定位失败发生在哪个环节

### 产出物
- [x] `projects/l5-multi-agent/main.py` — 2-3 个 agent 协作（如 research → write → review）
- [ ] `projects/l5-multi-agent/evals.md`（15 条骨架已建，实测结果待填） — 15+ 测试用例表格
- [ ] `notes/l5-agent-eval-framework.md`（尚未创建） — 总结经验：eval 该测什么？怎么设计 bad case？

### B线验证
- [x] 多 agent 之间怎么通信？你的实现用了什么方式？
- [x] 如果 reviewer 一直不满意，你的系统怎么防止无限循环？

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

## 进度总览（手动维护）

> 最后同步：2026-10-11

| Level | 主题 | 状态 | 开始日期 | 完成日期 | 分数/评价 |
|-------|------|------|---------|---------|----------|
| L0 | Agent 认知 | ✅ 完成 | 2026-07-02 | 2026-07-02 | 两篇核心文章总结；C线场景未单独留痕 |
| L1 | 最小 Agent Loop | ✅ 完成 | 2026-07-02 | 2026-07-03 | 5 个测试用例有记录，基础 3 条路径通过 |
| L2 | 工具+记忆+RAG | ✅ 完成（验收待补） | 2026-08-27 | 2026-08-29 | 代码和三层记忆笔记完成；测试结果与 C 线验证未回填 |
| L3 | Harness 源码拆解 | ✅ 完成 | 2026-09-02 | 2026-09-05 | 五问必答 + nano harness + 对比笔记；claw0 未选读 |
| L4 | Skills + MCP | 🔵 进行中 | 2026-09-07 | - | Skill 82.7；概念与优化闭环；真实 MCP server 未接 |
| L5 | 多Agent + 评测 | 🔵 进行中 | 2026-09-08 | - | Supervisor/Trace/Web Search/护栏已有；15 项 eval 与总结笔记未完成 |
| L6 | 交付真实项目 | ⬜ 未开始 | - | - | 当前仅有脚手架占位 |

### 总计
- 总阶段：7 个
- 主体完成：L0-L3（4 个；其中 L2 的测试记录和 C 线验证待补）
- 进行中：L4、L5
- 未开始：L6
- 按阶段权重估算：约 71%
- 当前最优先事项：接真实 MCP server → 跑 L5 的 15 项 eval → 写 L5 评测总结

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
