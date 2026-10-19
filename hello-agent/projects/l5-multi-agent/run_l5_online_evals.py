"""
L5 在线评测：用真实模型跑正常流程，并自动记录指标。

在 VS Code 终端运行：
  python run_l5_online_evals.py --limit 1 --yes
  python run_l5_online_evals.py --start 2 --limit 2 --yes

产物：
  online_results.md
  online_results.json
  online_reports/01.md ...
  online_traces/01.json ...
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

BASE_DIR = Path(__file__).resolve().parent
REPORTS_DIR = BASE_DIR / "online_reports"
TRACES_DIR = BASE_DIR / "online_traces"

TASKS = [
    "帮我研究一下量子计算的最新进展，写一份 500 字报告",
    "对比 Python 和 Go 在后端开发中的优劣",
    "介绍一下 Docker 和 K8s 的关系",
]


def check_environment() -> bool:
    ok = True

    print("=" * 60)
    print("环境检查")
    print("=" * 60)

    try:
        import openai
        print(f"openai: OK ({openai.__version__})")
    except ImportError:
        print("openai: MISSING")
        print("请先在 VS Code 终端运行：")
        print("  python -m pip install openai")
        ok = False

    try:
        from main import _resolve_env_key
        deepseek = _resolve_env_key("DEEPSEEK_API_KEY")
        bocha = _resolve_env_key("BOCHA_API_KEY")
    except Exception as e:
        print(f"读取配置失败：{type(e).__name__}: {e}")
        return False

    print(f"DEEPSEEK_API_KEY: {'OK' if deepseek else 'MISSING'}")
    print(f"BOCHA_API_KEY: {'OK' if bocha else 'MISSING'}")

    if not deepseek:
        print("缺少 DeepSeek Key，无法运行在线评测。")
        print("可设置：$env:DEEPSEEK_API_KEY = 'sk-...'")
        ok = False

    if not bocha:
        print("缺少 Bocha Key，Researcher 会走无搜索结果降级，不算完整在线评测。")
        print("可设置：$env:BOCHA_API_KEY = 'sk-...'")
        ok = False

    return ok


def write_json(path: Path, data) -> None:
    path.parent.mkdir(exist_ok=True)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def main():
    parser = argparse.ArgumentParser(description="L5 在线评测")
    parser.add_argument("--limit", type=int, default=len(TASKS), help="最多跑 N 个任务")
    parser.add_argument("--start", type=int, default=1, help="从第几个任务开始（1-based）")
    parser.add_argument("--yes", action="store_true", help="跳过确认")
    parser.add_argument("--timeout", type=int, default=240, help="单任务总超时秒数")
    parser.add_argument("--max-loops", type=int, default=3, help="Reviewer 最多让 Writer 修改次数")
    parser.add_argument("--check-only", action="store_true", help="只检查环境，不调用模型")
    args = parser.parse_args()

    if not check_environment():
        sys.exit(1)

    if args.check_only:
        print("\n环境检查通过。未调用模型。")
        return

    start = max(1, min(args.start, len(TASKS)))
    end = min(len(TASKS), start + max(0, args.limit) - 1)
    tasks = TASKS[start - 1:end]

    print("\n" + "=" * 60)
    print(f"即将运行 {len(tasks)} 个在线任务")
    print("=" * 60)
    for i, task in enumerate(tasks, 1):
        print(f"{i}. {task}")

    if not args.yes:
        answer = input("\n确认开始？[y/N] ").strip().lower()
        if answer not in ("y", "yes"):
            print("已取消。")
            return

    from main import Supervisor

    # 自动评测时模拟“人工同意交付”，这样能记录正常交付路径。
    # 拒绝对话的路径已经由离线测试覆盖。
    supervisor = Supervisor(
        max_review_loops=args.max_loops,
        total_timeout=args.timeout,
        ask_human=lambda q: True,
    )

    rows = []
    raw_results = []
    REPORTS_DIR.mkdir(exist_ok=True)
    TRACES_DIR.mkdir(exist_ok=True)

    for i, task in enumerate(tasks, 1):
        global_id = start + i - 1
        print("\n" + "=" * 60)
        print(f"[{i}/{len(tasks)}] {task}")
        print("=" * 60)

        started = time.time()
        try:
            result = supervisor.run(task)

            # 自动评测脚本使用的是自动同意，不是真人确认。
            # 不能沿用主程序里“已人工确认”的文案，否则会误导阅读者。
            if result.get("gate_approved"):
                result["final_report"] = result["final_report"].replace(
                    "✅ 已人工确认并交付。",
                    "🧪 自动评测批准：未经人工确认。"
                )

            row = {
                "approval_mode": "auto",
                "id": global_id,
                "task": task,
                "status": result.get("status"),
                "reason": result.get("reason"),
                "review_loops": result.get("review_loops"),
                "total_time": result.get("total_time"),
                "total_tokens": result.get("total_tokens"),
                "gate_approved": result.get("gate_approved"),
                "report_chars": len(result.get("final_report", "")),
                "error": "",
            }

            (REPORTS_DIR / f"{global_id:02d}.md").write_text(
                result.get("final_report", ""),
                encoding="utf-8",
            )
            write_json(TRACES_DIR / f"{global_id:02d}.json", result.get("trace", []))

            print(f"状态：{row['status']}")
            print(f"结束原因：{row['reason']}")
            print(f"评审修改轮数：{row['review_loops']}")
            print(f"耗时：{row['total_time']}s")
            print(f"Token：{row['total_tokens']}")
            print(f"报告长度：{row['report_chars']} 字")

        except Exception as e:
            elapsed = round(time.time() - started, 2)
            row = {
                "id": global_id,
                "task": task,
                "status": "error",
                "reason": "",
                "review_loops": 0,
                "total_time": elapsed,
                "total_tokens": 0,
                "gate_approved": False,
                "report_chars": 0,
                "error": f"{type(e).__name__}: {e}",
            }
            print(f"运行失败：{row['error']}")

        rows.append(row)
        raw_results.append(row)

        if i < len(tasks):
            time.sleep(2)

    # 合并历史结果，避免 --start 2 时覆盖任务 1 的记录
    existing_path = BASE_DIR / "online_results.json"
    merged_by_id = {}
    if existing_path.exists():
        try:
            for item in json.loads(existing_path.read_text(encoding="utf-8")):
                if isinstance(item, dict) and "id" in item:
                    merged_by_id[item["id"]] = item
        except Exception as e:
            print(f"警告：历史 online_results.json 无法读取，将重新生成。{e}")

    for row in raw_results:
        merged_by_id[row["id"]] = row

    rows_for_output = [merged_by_id[k] for k in sorted(merged_by_id)]
    print(f"\n本次新增 {len(raw_results)} 条，累计记录 {len(rows_for_output)} 条。")

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines = [
        "# L5 在线评测结果",
        "",
        f"- 运行时间：{now}",
        f"- Python：{sys.version.split()[0]}",
        f"- 任务数：{len(rows_for_output)}",
        f"- max_review_loops：{args.max_loops}",
        f"- total_timeout：{args.timeout}s",
        "",
        "| # | 任务 | 状态 | 原因 | 修改轮数 | 耗时(s) | Token | 报告字数 | 错误 |",
        "|---|---|---|---|---:|---:|---:|---:|---|",
    ]

    for row in rows_for_output:
        task = row["task"].replace("|", "\\|")
        error = row["error"].replace("|", "\\|")
        lines.append(
            f"| {row['id']} | {task} | {row['status']} | {row['reason']} | "
            f"{row['review_loops']} | {row['total_time']} | {row['total_tokens']} | "
            f"{row['report_chars']} | {error} |"
        )

    normal_pass = sum(
        1 for row in rows_for_output
        if row.get("reason") == "passed" and "(draft)" not in str(row.get("status", ""))
    )
    degraded = sum(
        1 for row in rows_for_output
        if row.get("reason") in {"max_loops_force_pass", "stuck_force_pass", "timeout"}
        or "(draft)" in str(row.get("status", ""))
    )
    hard_fail = len(rows_for_output) - normal_pass - degraded

    # 兼容旧变量名（下面的平均耗时代码不使用 passed）
    passed = normal_pass
    lines += [
        "",
        "## 汇总",
        "",
        f"- 正常通过：{normal_pass}",
        f"- 降级交付：{degraded}",
        f"- 硬失败：{hard_fail}",
        f"- 平均耗时：{round(sum(r['total_time'] for r in rows_for_output) / len(rows_for_output), 2) if rows_for_output else 0}s",
        f"- 平均 Token：{round(sum(r['total_tokens'] for r in rows_for_output) / len(rows_for_output), 1) if rows_for_output else 0}",
        "",
        "> 详细报告见 `online_reports/`，完整 trace 见 `online_traces/`。",
        "",
    ]

    (BASE_DIR / "online_results.md").write_text("\n".join(lines), encoding="utf-8")
    write_json(BASE_DIR / "online_results.json", rows_for_output)

    print("\n" + "=" * 60)
    print("在线评测完成")
    print("=" * 60)
    print(f"结果汇总：{BASE_DIR / 'online_results.md'}")
    print(f"JSON 指标：{BASE_DIR / 'online_results.json'}")
    print(f"报告目录：{REPORTS_DIR}")
    print(f"Trace 目录：{TRACES_DIR}")


if __name__ == "__main__":
    main()








