"""
学习进度仪表盘 — 一眼看清 Agent 学习路线走到了哪里。
用法：python scripts/progress.py
"""

import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROGRESS_FILE = ROOT / "progress.json"

# 每个 Level 的产出物清单（来自 README）
DELIVERABLES = {
    "L0": [
        "notes/l0-reading-summary.md — 回答三个核心问题",
        "B线：口头解释 agent loop 的 4 个阶段",
        "C线：找出 Claude Code 里 3 个 workflow vs agent 场景",
    ],
    "L1": [
        "projects/l1-mini-agent/main.py",
        "projects/l1-mini-agent/README.md",
        "projects/l1-mini-agent/test_cases.md",
        "B线：while True vs for？工具报错处理？",
        "C线：对比自己的 agent 和 Claude Code 的异同",
    ],
    "L2": [
        "projects/l2-rag-agent/main.py",
        "projects/l2-rag-agent/README.md",
        "projects/l2-rag-agent/tools.py",
        "projects/l2-rag-agent/memory.py",
        "projects/l2-rag-agent/rag.py",
        "projects/l2-rag-agent/test_cases.md",
        "notes/l2-memory-model.md — 三层记忆对比图",
        "B线：对话上下文 vs 长期记忆的本质区别？向量检索不相关怎么办？",
        "C线：分析一个 SKILL.md 的记忆依赖",
    ],
    "L3": [
        "notes/l3-harness-anatomy.md — 回答 5 个必答问题",
        "projects/l3-nano-harness/main.py — tool registry + permission gate + session store",
        "B线：nano harness vs learn-claude-code 差异 3 点",
        "C线：用 darwin-skill 给自己写的 SKILL.md 打分",
    ],
    "L4": [
        "skills/my-first-skill/SKILL.md",
        "skills/my-first-skill/ 下至少 1 个脚本 + 1 个模板",
        "notes/l4-skills-vs-tools.md — Skill vs Tool vs MCP vs A2A 对比表",
        "notes/l4-skill-optimization-log.md — darwin-skill 优化记录",
        "B线：SKILL.md 加载后 system prompt 多了什么？MCP 和普通 API 的区别？",
        "C线：darwin-skill 评分 + 优化记录",
    ],
    "L5": [
        "projects/l5-multi-agent/main.py — 2-3 agent 协作",
        "projects/l5-multi-agent/evals.md — 15+ 测试用例",
        "notes/l5-agent-eval-framework.md — eval 该测什么",
        "B线：多 agent 怎么通信？reviewer 不满意怎么防无限循环？",
        "C线：darwin-skill 回归评测 + Skill 质量报告",
    ],
    "L6": [
        "projects/l6-final-agent/main.py",
        "projects/l6-final-agent/README.md",
        "projects/l6-final-agent/tests/ — 至少 5 个测试用例",
        "projects/l6-final-agent/eval_report.md — 20 测试用例",
        "projects/l6-final-agent/SKILL.md",
        "B线：agent loop 架构图 + 权限边界说明",
        "C线：darwin-skill 评分 ≥ 70 + 真实用户反馈",
    ],
}

STATUS_ICONS = {
    "done": "✅",
    "in_progress": "🔵",
    "pending": "⬜",
}

STATUS_LABELS = {
    "done": "完成",
    "in_progress": "进行中",
    "pending": "未开始",
}


def load_progress():
    if PROGRESS_FILE.exists():
        with open(PROGRESS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"levels": {}, "weekly_reviews": []}


def main():
    data = load_progress()
    levels = data["levels"]

    print()
    print("╔══════════════════════════════════════════════════╗")
    print("║      Agent 学习路线图 · 进度仪表盘               ║")
    print("╚══════════════════════════════════════════════════╝")
    print()

    done_count = 0
    total = len(levels)

    for key in sorted(levels.keys()):
        lv = levels[key]
        status = lv["status"]
        icon = STATUS_ICONS.get(status, "  ")
        label = STATUS_LABELS.get(status, status)

        date_info = ""
        if lv.get("start"):
            date_info = f" {lv['start']}"
            if lv.get("end"):
                date_info += f" → {lv['end']}"

        print(f"  {icon} {key}  {lv['theme']:<20} {label:<6}{date_info}")

        if status == "done":
            done_count += 1

    # 进度条
    pct = done_count / total * 100 if total > 0 else 0
    bar_len = 30
    filled = int(bar_len * done_count / total)
    bar = "█" * filled + "░" * (bar_len - filled)
    print(f"\n  总进度：{done_count}/{total} ({pct:.0f}%)")
    print(f"  [{bar}]")
    print()

    # 当前关卡
    current = next((k for k in sorted(levels.keys()) if levels[k]["status"] == "in_progress"), None)
    if current:
        lv = levels[current]
        print(f"  🔥 当前关卡：{current} · {lv['theme']}")
        print(f"  ─────────────────────────────────────")
        print(f"  产出物清单：")
        for item in DELIVERABLES.get(current, []):
            print(f"    - [ ] {item}")
        print()
    elif done_count == total:
        print("  🎉 全部完成！恭喜！")
        print()

    # 下一关预览
    next_level = next((k for k in sorted(levels.keys()) if levels[k]["status"] == "pending"), None)
    if next_level:
        lv = levels[next_level]
        print(f"  📋 下一关：{next_level} · {lv['theme']}")
        print()

    # 周回顾
    reviews = data.get("weekly_reviews", [])
    if reviews:
        print(f"  📝 周回顾记录：{len(reviews)} 篇")
        latest = reviews[-1]
        print(f"  最近一篇：{latest.get('date', '?')}")
        print(f"  {latest.get('summary', '')[:80]}...")
        print()


if __name__ == "__main__":
    main()
