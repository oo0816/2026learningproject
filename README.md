# 🗂️ 2026 学习工作区 — AI Agent × 产品经理 双线学习仓库

> **作者**：王敏乐（大连理工 · 软件工程 2024 级 · GPA 86）
> **目标岗位**：AI Agent 开发工程师（主线备选）／ AI 产品经理（Agent 方向）
> **求职时间窗**：2027.07-08 暑期实习 → 2027.09-11 秋招（2028 届）

这个仓库是一个 **AI Agent 双线学习工作区**：左手把 Agent 工程从零一路徒手做到真实项目（B 工程线），右手同步沉淀产品视角（C 产品线），求职规划文档单独维护。**核心学习内容在 [`hello-agent/`](hello-agent/) 下。**

---

## 📂 这个文件夹里有什么

| 路径 | 是什么 | 当前状态 |
|---|---|---|
| [`hello-agent/`](hello-agent/) | **Agent 学习核心**：L0→L6 路线图 + 产出物 + skill | 🔵 L4 进行中（见下） |
| [`learn-claude-code/`](learn-claude-code/) | 独立克隆的 [learn-claude-code](https://github.com/shareAI-lab/learn-claude-code) 课程仓库（s01–s17 从 0 复刻 Claude Code harness），L3/L4 精读用 | 📖 参考教材 |
| [`求职目录/`](求职目录/00-README.md) | 求职规划全套：双线策略、学习路线、项目规划、资源、时间线（00–05） | 🎯 求职主文档 |
| [`note/`](note/) | 散装速查与清单：Git 速查、pi 快捷指令、AI 实习岗位清单 | 📝 日常记录 |

### hello-agent 内部

```
hello-agent/
├── notes/                      ← 学习笔记（正式产出物）
│   ├── README.md               ← ★ L0→L6 学习路线图（打勾清单 + 进度）
│   ├── l0-reading-summary.md   · l2-note.md（三层记忆/RAG）
│   ├── l3-harness-anatomy.md   · l3-nano-harness-qna.md   （L3 五问必答）
│   └── l4-skill-mcp-qna.md     ← L4 概念问答（Skill/Tool/MCP/A2A，今天新增）
├── projects/                   ← 每关一个可运行代码项目
│   ├── l1-mini-agent/          · l2-rag-agent/
│   ├── l3-nano-harness/        （tool registry + permission gate + session store + 上下文压缩）
│   ├── l4-skills-mcp/          （l4-skills-vs-tools.md 对比表 + 优化日志）
│   └── l5-multi-agent/ · l6-final-agent/   （脚手架占位，待做）
├── skills/
│   ├── japanese-exam-review/   ← ★ 主打 skill：日语 CS 复习 PDF 生成器
│   └── my-first-skill/         （入门练习 skill）
├── agent-notes.md              ← 学习日记
├── HELLOAGENT.md               ← Agent Learning Hub（外部参考整理）
└── scripts/progress.py         ← 进度仪表盘
```

> 说明：早年根目录的 `00-README.md`~`05-*.md` 六份求职规划文档，现全部在 [`求职目录/`](求职目录/)，根 README 只做导航，不再重复内容。

---

## 📈 最近在忙什么（2026.09）

按 git 历史从近到远：

- **09.07 · L4 概念笔记（今天）**：把和 Claude 的一轮追问整理成 [`notes/l4-skill-mcp-qna.md`](hello-agent/notes/l4-skill-mcp-qna.md)（Skill/Tool/MCP/A2A 四层关系、MCP Server 与协议线格式、MCP vs API、skill 加载机制），并填完 [`l4-skills-vs-tools.md`](hello-agent/projects/l4-skills-mcp/l4-skills-vs-tools.md) 的三道空白题（正好覆盖路线图 L4 的 B 线验证）。
- **09.07 · 主打 skill 重建 + darwin 优化**：把 [`japanese-exam-review`](hello-agent/skills/japanese-exam-review/) 从 reportlab 数据驱动**整个重建**为"统一版式引擎 `guide_style.py` + 通路A直写/通路B JSON + 复习/考点双模式"，随后 darwin-skill 2.0 跑 4 轮优化 **75.7 → 82.7**（Δ+7.0，全部 keep），并补了 3 场景 test-prompts 与 EVALUATION 运行记录。
- **09.03–09.05 · L3 完成**：读透 learn-claude-code 与自建 nano harness，产出 [`l3-harness-anatomy.md`](hello-agent/notes/l3-harness-anatomy.md)（五问必答）+ 对比差异笔记。

> 完整提交历史见本仓库 `git log`；具体进度以 [`hello-agent/notes/README.md`](hello-agent/notes/README.md) 打勾清单为准。

---

## 🧭 学习路径（hello-agent L0→L6）

路线 = **B 工程线（拆轮子造轮子）+ C 产品线（当用户驾驶）**，每关必须完成产出物才放行：

| Level | 主题 | 状态 | 产出物落点 |
|---|---|---|---|
| L0 | Agent 认知 | ✅ 完成 | `notes/l0-reading-summary.md` |
| L1 | 最小 Agent Loop（第一个里程碑） | ✅ 完成 | `projects/l1-mini-agent/` |
| L2 | 工具 + 记忆 + RAG | ✅ 完成 | `projects/l2-rag-agent/` + `notes/l2-note.md` |
| L3 | Harness 源码拆解（核心阶段） | ✅ 完成 | `projects/l3-nano-harness/` + `notes/l3-harness-anatomy.md` |
| L4 | Skills + MCP + 能力打包 | 🔵 **进行中** | `skills/japanese-exam-review/` + L4 概念笔记（今日） |
| L5 | 多 Agent + 评测 | ⬜ 未开始 | `projects/l5-multi-agent/` |
| L6 | 交付真实项目（最终产出） | ⬜ 未开始 | `projects/l6-final-agent/` |

**当前聚焦 L4**：skill 已重建并优化到 82.7，概念（Skill/Tool/MCP/A2A）已闭环；下一步是 **接一个 MCP server 跑通协议 + 把 japanese-exam-review 的考点库用真实试卷实装**。

> 每日进度可在 hello-agent 下用 `python scripts/progress.py` 查看仪表盘。

---

## 🚀 怎么用这份工作区

1. **想复习学习进度** → 看 [`hello-agent/notes/README.md`](hello-agent/notes/README.md) 的路线图打勾清单。
2. **想回顾某关产出** → 按上面表格去对应 `notes/` 或 `projects/`。
3. **求职规划**（双线策略/简历/时间线）→ 进 [`求职目录/00-README.md`](求职目录/00-README.md)。
4. **随时查命令/清单** → [`note/`](note/) 下的速查文件。

---

## ⚙️ 维护规则

- **每日最小投入**：至少 1 次 git commit；产出物文件当天更新。
- **每周日晚**：周复盘 + 更新路线图打勾与进度。
- **每月末**：对照 `求职目录/02-学习路线图.md` 里程碑检查表。
