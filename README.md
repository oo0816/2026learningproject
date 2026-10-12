# 王敏乐 · AI Agent 工程学习仓库（2026）

**大连理工 985 · 软件工程 2024 级 · GPA 86** ｜ 目标岗位：**AI Agent 开发工程师**（主线）／ **AI 产品经理**（Agent 方向）
**求职窗口**：2027.07–08 暑期实习 → 2027.09–11 秋招（2028 届）

![Python](https://img.shields.io/badge/Python-3.13-3776AB?logo=python&logoColor=white)
![Agent](https://img.shields.io/badge/AI_Agent-全链路手写-6C4DF6)
![Skill](https://img.shields.io/badge/Skill_交付-75.7→82.7-2ea44f)

> 核心内容全在 [`hello-agent/`](hello-agent/)；旗舰作品是独立仓库 [japanese-exam-review](https://github.com/oo0816/-japanese-exam-review-skill)。

---

## 一句话

**近 7 周，从"只会 Python 语法"到徒手跑通 Agent 全链路：**

`Agent Loop → 工具调用 → 记忆 / RAG → Harness（权限闸门 · 会话 · 上下文压缩） → Skill 封装 → 手写 MCP → 多 Agent 协作`

**没套框架**——全程零 LangGraph / AutoGen，直接调 LLM API 自己实现；每一层都留下能点开验证的产出物。

---

## 我的优势（每条都有证据）

| # | 优势 | 能点开的证据 |
|---|---|---|
| 1 | **造轮子，不只调 API** | 手写最小 Agent Loop（190 行）；自建 nano harness **1294 行**：tool registry + 权限闸门 + 会话存储 + 上下文压缩 |
| 2 | **能拆真实系统的架构** | 精读并复刻 `learn-claude-code` s01–s17，产出 268 行「harness 五问必答」架构笔记 |
| 3 | **工程化 + 量化意识** | 旗舰 skill 经 4 轮自动优化 **75.7 → 82.7**（4 轮全部保留）；配冒烟测试 / 覆盖率检查 / 3 场景回归提示词 |
| 4 | **协议层吃透过** | 零 SDK 手写 MCP server + client（261 行）跑通协议，而不是装个包调一下 |
| 5 | **接真实外部工具** | 多 Agent 项目接入博查 Web Search API，带 supervisor 调度、人工确认闸门、全链路 trace（**1652 行**） |
| 6 | **英语一手资料** | CET-6 538；Agent 生态文档几乎全英文，能直接读论文与官方文档，不吃二手翻译 |
| 7 | **工程 × 产品双线产出** | 每个项目同时交代码与产品文档：竞品分析 / PRD / 原型 / 评测指标（见 [`求职目录/03`](求职目录/03-项目与作品集.md)） |
| 8 | **持续交付** | 近 7 周 29 次提交、12 个活跃日；本项目自有 Python **5300+ 行**、笔记 **1600+ 行**、求职规划 6 份 |

**差异化背景**：大创项目（UNet 系列 · 医学图像分割 / 三维重建 / 点云配准流程）｜ SQL Server 课程设计 ｜ 团支书（组织 30+ 场活动）

---

## 🚀 旗舰作品：japanese-exam-review

**日语 CS 复习文档生成器** — 已独立成仓库：[oo0816/-japanese-exam-review-skill](https://github.com/oo0816/-japanese-exam-review-skill)

- **面向真实痛点**：中日合办项目的学生用日语学 CS 专业课。把日语课件（PDF / PPTX）与历年试卷，生成中日对照的复习文档 PDF。
- **技术上的做法**
  - 自建**统一版式引擎** `guide_style.py`（251 行，单字体 + 3 组强调色），**两条制作通路**（直写 A / JSON B）产出逐页一致的版式；
  - **两种内容模式**：讲义驱动的复习模式、试卷驱动的考点模式（先抽考点库，再以考点为主线组织文档）；
  - **可回归交付**：`smoke_test.py` 冒烟测试（依赖 / 字体 / 语法 / schema / 覆盖率 / 双通路渲染）、`check_coverage.py` 覆盖率检查、3 场景端到端测试提示词。
- **量化结果**：darwin-skill 2.0 评分 **75.7 → 82.7**（Δ+7.0，4 轮优化全部保留）；基线与优化记录见仓库内 `EVALUATION-*.md`。

---

## 🧭 学习路线与进度（L0→L6 · 诚实版）

路线 = **B 工程线（拆轮子造轮子）+ C 产品线（当用户驾驶）**，每关交产出物才放行：

| Level | 主题 | 状态 | 产出物 |
|---|---|---|---|
| L0 | Agent 认知 | ✅ 完成 | [`notes/l0-reading-summary.md`](hello-agent/notes/l0-reading-summary.md) |
| L1 | 最小 Agent Loop | ✅ 完成 | [`projects/l1-mini-agent/`](hello-agent/projects/l1-mini-agent/) |
| L2 | 工具 + 记忆 + RAG | ✅ 完成 | [`projects/l2-rag-agent/`](hello-agent/projects/l2-rag-agent/) + [`notes/l2-note.md`](hello-agent/notes/l2-note.md) |
| L3 | Harness 源码拆解 | ✅ 完成 | [`projects/l3-nano-harness/`](hello-agent/projects/l3-nano-harness/) + [`notes/l3-harness-anatomy.md`](hello-agent/notes/l3-harness-anatomy.md) |
| L4 | Skills + MCP + 能力打包 | 🔵 进行中 | [japanese-exam-review](https://github.com/oo0816/-japanese-exam-review-skill) + [`projects/l4-skills-mcp/`](hello-agent/projects/l4-skills-mcp/) + [概念问答](hello-agent/notes/l4-skill-mcp-qna.md) |
| L5 | 多 Agent + 评测 | 🔵 进行中 | [`projects/l5-multi-agent/`](hello-agent/projects/l5-multi-agent/)（supervisor + 护栏 + trace + Web Search） |
| L6 | 交付真实项目 | ⬜ 未开始 | [`projects/l6-final-agent/`](hello-agent/projects/l6-final-agent/) |

当前整体进度约 **71%**。**接下来 90 天**：
① 接一个真实 MCP server，收尾 L4；② 跑完 L5 的 15 条评测用例（正常流程 / 修改循环 / 超时保护 / 边界 / 工具异常 / 多轮对话）并写评测总结；③ 把 L2 / L5 升级成"可点开、可演示"的成品项目，同步补产品文档。

---

## 📂 仓库结构

```
2026learningproject/
├── hello-agent/                  ← ★ 学习核心：L0→L6 路线图 + 产出物 + skill
│   ├── notes/                    ← 学习笔记 1600+ 行：路线图、架构拆解、概念问答
│   ├── projects/                 ← 每关一个可运行项目（l1 → l6）
│   ├── skills/japanese-exam-review/   ← 指向独立仓库的链接（技能已独立成仓库）
│   └── README.md                 ← Agent Learning Hub 外部参考整理
├── 求职目录/                     ← 求职规划 6 份：现状诊断 / 路线图 / 作品集 / 资源 / 时间线
├── learn-claude-code/            ← 精读教材：s01–s17 从 0 复刻 Claude Code harness
├── note/                         ← 速查：Git 实战、AI 实习岗位清单、开源项目学习顺序
└── README.md                     ← 本文件（仓库门面）
```

---

## 📬 更新节奏

- **每日**：至少 1 次提交，产出物当天更新。
- **每周日**：复盘 + 更新路线图打勾与进度。
- **每月末**：对照 [`求职目录/02-学习路线图.md`](求职目录/02-学习路线图.md) 检查里程碑。

> 更完整也更诚实的自我诊断（含真实差距与补齐计划）在 [`求职目录/01-现状诊断与目标定位.md`](求职目录/01-现状诊断与目标定位.md)。