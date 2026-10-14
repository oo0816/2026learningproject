"""
L5 离线评测：不调用真实模型，用假模型跑确定性流程。

运行：
  D:/anaconda/python.exe test_l5_offline.py

覆盖：
  1. Reviewer 第一次就通过
  2. Reviewer 先拒绝，再通过
  3. 改满 max_review_loops 后强制放行
  4. 连续两轮同一问题 -> stuck_force_pass
  5. 总超时 -> timeout
  6. 人工闸门拒绝 -> draft
  7. 空输入 -> bad_input
"""

import json
import sys
import time
import unittest

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent))

from main import Supervisor


def reply(content: str, tokens: int = 100) -> dict:
    return {
        "content": content,
        "tool_calls": [],
        "tokens": tokens,
    }


def verdict(value: str, issue_type: str = "none", comments: str = "") -> dict:
    return reply(json.dumps({
        "verdict": value,
        "score": 9 if value == "pass" else 5,
        "issue_type": issue_type,
        "comments": comments,
    }, ensure_ascii=False))


class FakeModel:
    def __init__(self, script: list[dict], delay: float = 0.0):
        self.script = list(script)
        self.delay = delay
        self.calls = 0

    def __call__(self, messages, schemas):
        self.calls += 1
        if self.delay:
            time.sleep(self.delay)
        if not self.script:
            raise RuntimeError(f"假模型脚本耗尽，第 {self.calls} 次调用没有返回内容")
        return self.script.pop(0)


class L5OfflineTests(unittest.TestCase):
    def test_01_reviewer_pass_first_time(self):
        fake = FakeModel([
            reply("研究摘要：量子计算的关键进展。"),
            reply("报告：这是一份正常报告。"),
            verdict("pass"),
        ])
        sup = Supervisor(model_fn=fake, ask_human=lambda q: True)
        result = sup.run("研究量子计算，写 200 字")

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["reason"], "passed")
        self.assertEqual(result["review_loops"], 0)
        self.assertTrue(result["gate_approved"])
        self.assertEqual(fake.calls, 3)

    def test_02_revise_then_pass(self):
        fake = FakeModel([
            reply("研究摘要：量子计算的关键进展。"),
            reply("报告 V1：结构较乱。"),
            verdict("revise", issue_type="structure", comments="请分节。"),
            reply("报告 V2：已按意见分节。"),
            verdict("pass"),
        ])
        sup = Supervisor(model_fn=fake, ask_human=lambda q: True)
        result = sup.run("研究量子计算，写 200 字")

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["reason"], "passed")
        self.assertEqual(result["review_loops"], 1)
        self.assertTrue(result["gate_approved"])
        self.assertEqual(fake.calls, 5)

    def test_03_max_loops_force_pass(self):
        fake = FakeModel([
            reply("研究摘要"),
            reply("报告 V1"),
            verdict("revise", issue_type="structure"),
            reply("报告 V2"),
            verdict("revise", issue_type="accuracy"),
            reply("报告 V3"),
        ])
        sup = Supervisor(
            max_review_loops=2,
            model_fn=fake,
            ask_human=lambda q: True,
        )
        result = sup.run("研究量子计算")

        self.assertEqual(result["reason"], "max_loops_force_pass")
        self.assertEqual(result["status"], "ok(max_loops_force_pass)")
        self.assertEqual(result["review_loops"], 2)
        self.assertTrue(result["gate_approved"])
        self.assertEqual(fake.calls, 6)

    def test_04_stuck_force_pass(self):
        fake = FakeModel([
            reply("研究摘要"),
            reply("报告 V1"),
            verdict("revise", issue_type="length"),
            reply("报告 V2"),
            verdict("revise", issue_type="length"),
        ])
        sup = Supervisor(model_fn=fake, ask_human=lambda q: True)
        result = sup.run("写 100 字介绍微服务")

        self.assertEqual(result["reason"], "stuck_force_pass")
        self.assertEqual(result["status"], "ok(stuck_force_pass)")
        self.assertEqual(result["review_loops"], 1)
        self.assertTrue(result["gate_approved"])
        self.assertEqual(fake.calls, 5)

    def test_05_timeout(self):
        fake = FakeModel([
            reply("研究摘要"),
            reply("报告 V1"),
        ], delay=0.01)
        sup = Supervisor(
            total_timeout=0.001,
            model_fn=fake,
            ask_human=lambda q: True,
        )
        result = sup.run("研究量子计算")

        self.assertEqual(result["status"], "timeout")
        self.assertEqual(result["reason"], "timeout")
        self.assertFalse(result["gate_approved"])
        self.assertEqual(result["review_loops"], 0)
        self.assertIn("超时", result["final_report"])
        self.assertIn("Research", result["final_report"])
        self.assertEqual(fake.calls, 1)

    def test_06_human_gate_reject(self):
        fake = FakeModel([
            reply("研究摘要"),
            reply("报告 V1"),
            verdict("pass"),
        ])
        sup = Supervisor(model_fn=fake, ask_human=lambda q: False)
        result = sup.run("研究量子计算")

        self.assertEqual(result["reason"], "passed")
        self.assertEqual(result["status"], "ok(draft)")
        self.assertFalse(result["gate_approved"])
        self.assertIn("未获人工确认", result["final_report"])
        self.assertEqual(fake.calls, 3)

    def test_07_bad_input_empty(self):
        fake = FakeModel([])
        sup = Supervisor(model_fn=fake, ask_human=lambda q: True)
        result = sup.run("   ")

        self.assertEqual(result["status"], "bad_input")
        self.assertEqual(result["reason"], "bad_input")
        self.assertFalse(result["gate_approved"])
        self.assertEqual(result["total_tokens"], 0)
        self.assertEqual(fake.calls, 0)

    def test_08_trace_has_review_round(self):
        fake = FakeModel([
            reply("研究摘要"),
            reply("报告 V1"),
            verdict("pass"),
        ])
        sup = Supervisor(model_fn=fake, ask_human=lambda q: True)
        result = sup.run("研究量子计算")

        actions = [item["action"] for item in result["trace"]]
        self.assertIn("review/round", actions)
        self.assertIn("gate/result", actions)


if __name__ == "__main__":
    unittest.main(verbosity=2)


