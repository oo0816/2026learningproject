# 2026 Agent 工程学习工作区

> 大连理工 985 · 软件工程 2024 级（2028 届）｜ GPA 86 ｜ CET-6 538
> 目标岗位：AI Agent 开发工程师（主线）／ AI 产品经理（Agent 方向）
> 求职窗口：2027.07–08 暑期实习 → 2027.09–11 秋招

本仓库记录一条 Agent 工程学习路线的完整过程：**不使用 LangGraph / AutoGen 等现成框架**，按 L0 → L6 逐层实现 Agent 的核心部件——循环、工具、记忆、harness、skill 封装、MCP、多 Agent 协作——每一层都留下可运行、可复现的产出物。核心内容位于 [`hello-agent/`](hello-agent/)。

---

## 路线与产出（L0 → L6）

### L0 · Agent 认知
读 hello-agents 前几章，产出读书总结。
产出：[`notes/l0-reading-summary.md`](hello-agent/notes/l0-reading-summary.md)

### L1 · 最小 Agent Loop
手写 observe → think → act 循环，190 行，含测试用例。
产出：[`projects/l1-mini-agent/`](hello-agent/projects/l1-mini-agent/)

### L2 · 工具调用 + 记忆 + RAG
主流程 398 行；记忆（271 行，三层结构）、检索（325 行）、工具层（316 行）分别实现。
产出：[`projects/l2-rag-agent/`](hello-agent/projects/l2-rag-agent/)、笔记 [`notes/l2-note.md`](hello-agent/notes/l2-note.md) 与 [`l2-rag-memory-card.md`](hello-agent/notes/l2-rag-memory-card.md)

### L3 · Harness 拆解与自建
精读 learn-claude-code 的 s01–s17 后，自建 nano harness：tool registry、权限闸门、会话存储、上下文压缩，共 1294 行，含独立测试。
产出：[`projects/l3-nano-harness/`](hello-agent/projects/l3-nano-harness/)、架构笔记（268 行「五问必答」）[`notes/l3-harness-anatomy.md`](hello-agent/notes/l3-harness-anatomy.md) 与 [`l3-nano-harness-qna.md`](hello-agent/notes/l3-nano-harness-qna.md)

### L4 · Skill 封装 + 手写 MCP
- 完整交付一个可复用 skill，见下节「作品」。
- 不使用任何 SDK，手写 MCP server + client（121 + 140 行）跑通协议。
产出：[`projects/l4-skills-mcp/`](hello-agent/projects/l4-skills-mcp/)、概念梳理 [`notes/l4-skill-mcp-qna.md`](hello-agent/notes/l4-skill-mcp-qna.md)

### L5 · 多 Agent 协作 + 评测设计
1652 行实现多 Agent 流程：supervisor 调度、Reviewer 修改循环、修改次数上限、超时保护、敏感操作人工确认闸门、全链路 trace；检索接入博查 Web Search API。
评测：已设计 15 条用例，覆盖正常流程 / 修改循环 / 超时保护 / 边界 / 工具异常 / 多轮对话（尚未跑分）。
产出：[`projects/l5-multi-agent/`](hello-agent/projects/l5-multi-agent/)（含 `evals.md`）

### L6 · 交付真实项目
脚手架已建，尚未开始。
产出：[`projects/l6-final-agent/`](hello-agent/projects/l6-final-agent/)

---

## 作品：japanese-exam-review

独立仓库：[oo0816/-japanese-exam-review-skill](https://github.com/oo0816/-japanese-exam-review-skill)

**用途**：面向中日合办项目的学生——专业课用日语授课，课件与历年真题均为日文。该 skill 把日语课件（PDF / PPTX）与试卷转换为中日对照的复习文档 PDF。

**实现要点**

- **统一版式引擎** `guide_style.py`（251 行，单字体 + 3 组强调色）；提供两条制作通路（直接写代码 / 写内容 JSON），两者产出版式逐页一致，避免同类文档风格漂移。
- **两种内容模式**：仅有课件时按讲义顺序逐章梳理（复习模式）；有真题时先抽取考点库，再以考点为主线组织文档（考点模式）。
- **可复现性**：`smoke_test.py` 冒烟测试（依赖 / 字体 / 语法 / 结构 / 覆盖率 / 两条通路渲染）与 `check_coverage.py` 覆盖率检查，一条命令完成回归验证。
- **优化记录**：经 darwin-skill 4 轮自动优化，评分 75.7 → 82.7（4 轮改动全部保留）；基线与各轮记录见仓库内 `EVALUATION-*.md`。

该 skill 原位于本仓库 `hello-agent/skills/` 下，现已独立成仓库；本仓库保留一个[指向它的链接](hello-agent/skills/japanese-exam-review)。

---

## 当前进度

| Level | 主题 | 状态 | 产出物 |
|---|---|---|---|
| L0 | Agent 认知 | ✅ 完成 | [`notes/l0-reading-summary.md`](hello-agent/notes/l0-reading-summary.md) |
| L1 | 最小 Agent Loop | ✅ 完成 | [`projects/l1-mini-agent/`](hello-agent/projects/l1-mini-agent/) |
| L2 | 工具 + 记忆 + RAG | ✅ 完成 | [`projects/l2-rag-agent/`](hello-agent/projects/l2-rag-agent/) + [`notes/l2-note.md`](hello-agent/notes/l2-note.md) |
| L3 | Harness 源码拆解 | ✅ 完成 | [`projects/l3-nano-harness/`](hello-agent/projects/l3-nano-harness/) + [`notes/l3-harness-anatomy.md`](hello-agent/notes/l3-harness-anatomy.md) |
| L4 | Skills + MCP + 能力打包 | 🔵 进行中 | [japanese-exam-review](https://github.com/oo0816/-japanese-exam-review-skill) + [`projects/l4-skills-mcp/`](hello-agent/projects/l4-skills-mcp/) |
| L5 | 多 Agent + 评测 | 🔵 进行中 | [`projects/l5-multi-agent/`](hello-agent/projects/l5-multi-agent/)（supervisor + 护栏 + trace + Web Search，评测待跑） |
| L6 | 交付真实项目 | ⬜ 未开始 | [`projects/l6-final-agent/`](hello-agent/projects/l6-final-agent/) |

整体进度约 **74%**。**下一阶段（90 天）**：

1. 接入一个真实 MCP server，收尾 L4；
2. 跑完 L5 的 15 条评测用例并输出总结；
3. 将 L2 / L5 从练习代码升级为可部署、可演示的成品，并补齐产品侧文档（PRD / 竞品分析 / 原型）——对应 [`求职目录/03`](求职目录/03-项目与作品集.md) 的规划。

---

## 仓库结构

```
2026learningproject/
├── hello-agent/                  ← ★ 学习核心：L0→L6 路线图 + 产出物 + skill
│   ├── notes/                    ← 学习笔记：路线图、架构拆解、概念问答
│   ├── projects/                 ← 每关一个可运行项目（l1 → l6）
│   ├── skills/japanese-exam-review/   ← 指向独立仓库的链接（技能已独立成仓库）
│   └── README.md                 ← Agent Learning Hub 外部参考整理
├── 求职目录/                     ← 求职规划 6 份：现状诊断 / 路线图 / 作品集 / 资源 / 时间线
├── learn-claude-code/            ← 精读教材：s01–s17 从 0 复刻 Claude Code harness
├── note/                         ← 速查：Git 实战、AI 实习岗位清单、开源项目学习顺序
└── README.md                     ← 本文件
```

---

## 更新节奏

- **每日**：至少一次提交，当天产出物当天入库。
- **每周日晚**：复盘并更新路线图进度。
- **每月末**：对照 [`求职目录/02-学习路线图.md`](求职目录/02-学习路线图.md) 检查里程碑。

自 2026-08-26 起累计 29 次提交，提交内容多为具体产出（笔记、代码、重构），无空提交。

---

## 相关文档

求职规划（双线策略、学习路线图、作品集、资源清单、时间线）见 [`求职目录/`](求职目录/00-README.md)。


