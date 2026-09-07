# japanese-exam-review — 基线评估（darwin-skill）

- **日期**: 2026-09-04
- **评估对象**: 全局版 `D:\claudecode\.claude\skills\japanese-exam-review\`
- **评估方式**: dry_run（读 SKILL.md 推演，未跑真实课件）；`eval_mode=dry_run`
- **测试 prompt**: 模式一 happy path（jp_first）、模式二（课件+试卷考点分析）各 1 个
- **决策**: 只评估，未做任何改动

## 评分卡（9 维加权，满分约 100）

| 维度 | 权重 | 得分/10 | 加权 | 一句话理由 |
|------|-----|--------|------|-----------|
| 1 Frontmatter 质量 | 7 | 8 | 5.6 | name/description 规范，含「做什么+何时用+触发词」无空话尾巴；缺能力边界（两种输出/考点） |
| 2 工作流清晰度 | 12 | 8 | 9.6 | 分模式编号步骤、命令与 I/O 明确；少数输出隐含（解析得 0 页怎么办） |
| 3 失败模式编码 | 12 | 6 | 7.2 | 有分支（exams 空→模式一、无图→跳过、模式二降级），但无系统性「X失败→Y」兜底表 |
| 4 检查点设计 | 6 | 7 | 4.2 | 前置强制三问是真 gate；但全篇仅此一处，筛图清单只输出不设确认点，无 🔴/🛑 视觉标记 |
| 5 可执行具体性 | 17 | 8 | 13.6 | 极具体（色值/字号/JSON schema/≥85%）；但引擎自相矛盾削弱可执行性 |
| 6 资源整合度 | 4 | 6 | 2.4 | 5 脚本+examples 在且路径对；SKILL 引用的 `make_cn_json.py`/`fix_all_annos.py` 缺失，字体靠外挂 |
| 7 整体架构 | 12 | 7 | 8.4 | 分层清晰、深度足；重复/不一致处多，agent 手册与渲染 spec 混排，无速查 |
| 8 实测表现(dry_run) | 23 | 6 | 13.8 | 模式一可走通；模式二 SKILL 未定义考点分析 JSON schema，执行会靠 agent 即兴 |
| 9 反例与黑名单 | 6 | 7 | 4.2 | 零散「禁止」不少（禁单 `\n`、禁机械翻译、禁编造…），但无独立红灯章节 |
| **合计** | 99 | — | **≈69** | |

## 关键短板（按影响排序）

1. **模式二欠规范（dim8）**: SKILL 只给 6 行流程草稿，内容 JSON 规范只定义了 4 种块类型，`exam_stat`/考点分析结构没 schema → 考点文档输出不稳定。
2. **引擎硬伤（dim3/dim5）**: SKILL 说 reportlab+`_ps2tt_map`、要求 `<b>`/`<font name>`，但 requirements 是 fpdf2、README 也是 fpdf2；被点名要用的 `make_cn_json.py`/`fix_all_annos.py` 不在 scripts/ 里。
3. **资源缺失（dim6）**: `assets/`、字体未随包；examples/ 没被 SKILL 引用为 smoke test。

## 附: runtime gate 扫描（独立于 9 维）

- SKILL.md 用「使用 AskUserQuestion 工具」、README 钉 `Claude Code Skill` 徽章 → **红灯命中**。对个人 Claude Code 使用影响小；若后续跑 darwin 优化会被列为 P0。

## 预计修复收益

模式二 schema 缺失 + 引擎矛盾两处优先修，预计 +8~12。
