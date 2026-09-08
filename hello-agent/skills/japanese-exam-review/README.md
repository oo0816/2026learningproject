# 日语CS专业课复习文档生成器 (japanese-exam-review)

[![Agent Skills Standard](https://img.shields.io/badge/Agent%20Skills-Standard-6C4DF6)](https://skills.sh)
[![Multi-Runtime](https://img.shields.io/badge/Multi-Runtime-ready-3EA639)](https://skills.sh)

根据**日语授课的 CS 专业课课件**（PDF 讲义 / PPTX）和**历年试卷**，生成中日对照的复习文档 PDF。支持 PDF 讲义和 PPTX 两种源文件。

**核心：全 Skill 只有一套统一版式（`scripts/guide_style.py`），两条制作通路产出完全一致。**

- **通路 A — 直写**：现写 `build_*.py` 按阅读顺序调用引擎方法（自由，适合单份/小课件）。
- **通路 B — JSON**：写一份极简内容 JSON，由 `scripts/path_b_render.py` 渲染（适合大课件/批量/覆盖率迭代）。

## 统一版式（一个原则）

引擎只提供屈指可数的几个版式元件（见 `SKILL.md`），单字体 SimSun、三组配色（藏青=标题/关键句、红=考点+图注专用、灰=次要）。**红色只给【試験】考点和 ▲图注。** 复习文档、考点解析、附录索引一律用它，不许另起风格。

风格样张（已逐页核对一致）：

- `output/sample_a.pdf` ← 直写版（`scripts/build_sample_a.py`）
- `output/sample_b.pdf` ← JSON 版（`examples/content_b_example.json`）

## 适用场景

- 仅课件 → 复习文档（术语表 + 概念正文 + 对比表 + 精选原图 + 红字考点）
- 课件 + 试卷 → **考点复习（考点模式）**：试卷不挑格式与来源——`exams/` 的 PDF、同学分享的照片 / 回忆题均可；先抽考点库，再以考点为主线排文档（真实红字 ★、附用語索引 / 試験対策）

## 项目结构

```
japanese-exam-review/
├── SKILL.md                    ← Skill 定义：触发/统一版式/写作规范/两通路/JSON schema
├── README.md
├── test-prompts.json           ← 3 个 agent 端到端场景（复习/考点回忆版/无材料防幻觉）
├── scripts/
│   ├── parse_pdf_lecture.py    ← PDF 讲义 → output/parsed_ppt.json + images
│   ├── parse_ppt.py            ← PPTX 课件 → 同上
│   ├── parse_pdf.py            ← PDF 试卷 → 考点原始数据
│   ├── guide_style.py          ← ★ 排版引擎（统一版式唯一来源）
│   ├── path_b_render.py        ← 通路B：内容 JSON → PDF（复用引擎）
│   ├── build_sample_a.py       ← 通路A 示例（直写）
│   ├── check_coverage.py       ← 覆盖率检查（parsed vs content JSON）
│   └── smoke_test.py           ← ★ 快速冒烟：一条命令回归依赖/字体/schema/覆盖率/A+B渲染
├── examples/
│   ├── content_b_example.json  ← 通路B 完整示例输入
│   └── README.md
├── fonts/                      ← simsun（引擎自动：extracted.ttf → simsun.ttc 回退）
├── ppt/                        ← 放课件（.pdf / .pptx，.pptx 不入库）
├── exams/                      ← 放历年试卷（可选，不入库）
└── requirements.txt
```

## 安装

```bash
# 1. 放进本机/项目的 skills 目录（个人版 `~/.claude/skills`、项目版 `.claude/skills`；或在 skills 工程内直接使用）
git clone <repo> .claude/skills/japanese-exam-review

# 2. 依赖
pip install -r requirements.txt

# 3. 字体 fonts/simsun（Windows 系统字体，未入库）
#    复制 C:\Windows\Fonts\simsun.ttc 到 fonts/，引擎可自动提取 .ttf

# 4. 目录
mkdir ppt exams
```

## 使用

对支持 agent skills 的 AI 助手（Claude Code / Codex / Cursor 等）输入**日语相关 + CS 专业课**的请求：

```
> 帮我把日语的计算机网络PPT整理成复习文档
> 日本老师的数据库课件和历年试卷，帮我做考点复习
```

Skill 确认范围与通路 → 解析课件 →（可选）解析试卷/建考点清单 → 通路 A 直写或通路 B JSON →（B）覆盖率核查 → 目验 PDF。

## 冒烟测试（改了脚本/依赖/字体后必跑）

两种验证，别混：

| | 命令 | 验证什么 | 成本 |
|---|---|---|---|
| **快速冒烟**（推荐每次改完跑） | `python scripts/smoke_test.py` | skill 的确定性部件：依赖/字体/脚本语法/解析产物/内容 JSON schema/覆盖率/通路 A+B 渲染出 PDF | 秒级、零 token |
| agent 端到端 | 用 `test-prompts.json` 的 3 场景请真子 agent 带 SKILL 跑 | 复习 / 考点回忆版 / 无材料防幻觉的完整行为 | 烧 token（darwin full_test 这类） |

```
python scripts/smoke_test.py                          # 回归默认示例，覆盖率下限 85%
python scripts/smoke_test.py <你的content.json>        # 换成新做的真实内容做回归
python scripts/smoke_test.py --cov-min 90             # 收紧覆盖率下限
```

冒烟**只**验确定性部件；图的取舍、考点库、是否编造等质量项仍要靠端到端与目验。

## 内容块（就这 5 种，B JSON 与 A 方法一一对应）

| 块 | 用途 |
|----|------|
| `para` (cn/jp/note) | 中文正文 / 日文关键句【中】 / 灰色次要说明 |
| `heading` | 章内小节标题 |
| `table` | 术语对照表 / 概念对比表（单元格 `日文\n【中】中文`） |
| `figure` | 讲义原图 + 红▲图注 + 灰细说明 |
| `exam` | 考点红字（自动加【試験】前缀） |

## 依赖

- Python ≥ 3.10
- PyMuPDF（解析）、fpdf2（排版）、python-pptx（PPTX）、Pillow

> reportlab 已退役移除。旧引擎 `generate_pdf.py` 不再存在。
