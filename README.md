# 2026 学习工作区：徒手造一个 Agent

我是王敏乐，大连理工软件工程 2024 级。2026 年 8 月底，我给自己定了一条路线：**不套框架，把 Agent 的每一层都自己实现一遍**——从最小循环，到工具、记忆、harness，再到能交付给别人用的 skill。

这个仓库就是这条路线的工作区，核心内容都在 [`hello-agent/`](hello-agent/) 里。

---

## 这 7 周我做了什么

**① 先让一个循环转起来（L0 → L1）**
读 hello-agents 的前几章打底，然后手写最小 Agent Loop：observe → think → act，190 行，配了测试用例。读完的总结在 [`notes/l0-reading-summary.md`](hello-agent/notes/l0-reading-summary.md)，代码在 [`projects/l1-mini-agent/`](hello-agent/projects/l1-mini-agent/)。

**② 给它装上工具、记忆和 RAG（L2）**
398 行主流程；记忆单独拆出来做了三层（271 行），检索 325 行，工具层 316 行。笔记在 [`notes/l2-note.md`](hello-agent/notes/l2-note.md) 和 [`l2-rag-memory-card.md`](hello-agent/notes/l2-rag-memory-card.md)。

**③ 拆真实 harness，然后自己造一个（L3）**
先把 learn-claude-code 的 s01–s17 顺着读了一遍，再用自己的写法实现了一个 nano harness：tool registry、权限闸门、会话存储、上下文压缩，1294 行，另配自己的测试。读完答了一份「五问必答」架构笔记（268 行）：[`notes/l3-harness-anatomy.md`](hello-agent/notes/l3-harness-anatomy.md)、追问记录 [`l3-nano-harness-qna.md`](hello-agent/notes/l3-nano-harness-qna.md)。

**④ 把能力打包成一个真有人用的 skill（L4）**
挑了件自己真需要的事：中日合办项目里专业课用日语上，课件和历年真题都是日文，复习很费劲。于是做了 [japanese-exam-review](https://github.com/oo0816/-japanese-exam-review-skill)，把日语课件和试卷变成中日对照的复习文档 PDF——细节见下面「作品」一节。
同一阶段**没用任何 SDK，手写了一个 MCP server + client**（121 + 140 行）把协议跑通：代码在 [`projects/l4-skills-mcp/`](hello-agent/projects/l4-skills-mcp/)，概念梳理在 [`notes/l4-skill-mcp-qna.md`](hello-agent/notes/l4-skill-mcp-qna.md)。

**⑤ 多 Agent 协作，以及怎么验证它（L5）**
1652 行写了一个多 Agent 流程：supervisor 派活、Reviewer 不过就退回改、改满次数强制收口、超时优雅终止、敏感动作走人工确认闸门，全程留 trace；检索接的是真实 Web Search（博查 API）。同时把「怎么证明它行」也设计了——15 条评测用例，覆盖正常流程 / 修改循环 / 超时保护 / 边界 / 工具异常 / 多轮对话。代码在 [`projects/l5-multi-agent/`](hello-agent/projects/l5-multi-agent/)，用例表在同目录 `evals.md`。

**⑥ 交付真实项目（L6）**
刚起了脚手架 [`projects/l6-final-agent/`](hello-agent/projects/l6-final-agent/)，还没开始写。

---

## 🚀 作品：japanese-exam-review

独立仓库：[oo0816/-japanese-exam-review-skill](https://github.com/oo0816/-japanese-exam-review-skill)

解决的问题很具体：中日合办项目里，专业课用日语上，课件和真题都是日文。我把「日语课件 + 历年试卷 → 中日对照的复习 PDF」做成了一个可复用的 skill。做的时候比较较真的几处：

- **版式**：不想每次生成都长得不一样，所以写了个统一版式引擎 `guide_style.py`（251 行，单字体 + 3 组强调色），并留了两条制作通路（直接写代码 / 写内容 JSON），两条通路产出逐页一致。
- **两种用法**：只有课件时，按讲义顺序逐章梳理（复习模式）；手里有真题时，先抽成考点库、再以考点为主线组织（考点模式）。
- **能不能复跑**：补了 `smoke_test.py` 冒烟测试（依赖 / 字体 / 语法 / 结构 / 覆盖率 / 两条通路渲染）和覆盖率检查 `check_coverage.py`，让别人——也包括三个月后的我——一条命令就能验证它没坏。
- **优化记录**：用 darwin-skill 跑了 4 轮自动优化，评分 **75.7 → 82.7**，4 轮改动全部保留；基线和每轮记录（`EVALUATION-*.md`）都留在仓库里。

它原来放在本仓库 `hello-agent/skills/` 下，后来独立成了仓库；本仓库里保留了 [一个指向它的链接](hello-agent/skills/japanese-exam-review)。

---

## 现在在哪

| Level | 主题 | 状态 | 产出物 |
|---|---|---|---|
| L0 | Agent 认知 | ✅ 完成 | [`notes/l0-reading-summary.md`](hello-agent/notes/l0-reading-summary.md) |
| L1 | 最小 Agent Loop | ✅ 完成 | [`projects/l1-mini-agent/`](hello-agent/projects/l1-mini-agent/) |
| L2 | 工具 + 记忆 + RAG | ✅ 完成 | [`projects/l2-rag-agent/`](hello-agent/projects/l2-rag-agent/) + [`notes/l2-note.md`](hello-agent/notes/l2-note.md) |
| L3 | Harness 源码拆解 | ✅ 完成 | [`projects/l3-nano-harness/`](hello-agent/projects/l3-nano-harness/) + [`notes/l3-harness-anatomy.md`](hello-agent/notes/l3-harness-anatomy.md) |
| L4 | Skills + MCP + 能力打包 | 🔵 进行中 | [japanese-exam-review](https://github.com/oo0816/-japanese-exam-review-skill) + [`projects/l4-skills-mcp/`](hello-agent/projects/l4-skills-mcp/) |
| L5 | 多 Agent + 评测 | 🔵 进行中 | [`projects/l5-multi-agent/`](hello-agent/projects/l5-multi-agent/)（supervisor + 护栏 + trace + Web Search，评测待跑） |
| L6 | 交付真实项目 | ⬜ 未开始 | [`projects/l6-final-agent/`](hello-agent/projects/l6-final-agent/) |

整体进度约 **71%**。**接下来 90 天**：① 接一个真实 MCP server，把 L4 收尾；② 跑完 L5 那 15 条评测并写总结；③ 把 L2 / L5 从"练习"打磨成"能点开、能演示"的成品，并补上产品侧文档——这条正好是 [`求职目录/03`](求职目录/03-项目与作品集.md) 里规划的路线。

---

## 📂 仓库结构

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

## 更新的习惯

- **每天**：至少一次提交，产出物当天落到仓库里，不攒着。
- **每周日**：复盘一周，更新路线图的打勾和进度。
- **每月末**：对着 [`求职目录/02-学习路线图.md`](求职目录/02-学习路线图.md) 过一遍里程碑。

从 8/26 开工到现在，累计 29 次提交；提交基本都对应具体产出（笔记、代码或一次重构），不是打卡式空提交。

---

## 关于我

大连理工 985 · 软件工程 2024 级 · GPA 86 ｜ CET-6 538 —— Agent 生态的文档和论文基本都是英文，习惯直接读一手资料。

求职方向：AI Agent 开发工程师（主线）／ AI 产品经理（Agent 方向）
时间窗：2027.07–08 暑期实习 → 2027.09–11 秋招（2028 届）

规划与自我诊断（双线策略、路线图、作品集、时间线）都在 [`求职目录/`](求职目录/00-README.md) 里。