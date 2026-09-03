# -*- coding: utf-8 -*-
"""
L3 在线冒烟测试：跑 L1 的 3 条路径（需要 DEEPSEEK_API_KEY）。

运行：python test_agent.py

覆盖：
  1. 单工具调用（calculator）
  2. 多工具并行（get_weather × 2）
  3. 零工具直接回答

每次调用 agent.run() 不传 session_id → 一次性对话，互不污染。
"""
import sys
import main


def run_case(title, query):
    print(f"\n{'=' * 30}\n{title}\n{'=' * 30}")
    agent = main.create_agent()
    print(agent.run(query))


if __name__ == "__main__":
    run_case("测试1：单工具调用 — 计算器", "1加2乘以3等于多少？请用计算器工具算一下")
    run_case("测试2：多工具并行 — 天气", "北京和深圳今天天气怎么样？")
    run_case("测试3：零工具直接回答", "你好，请用一句话介绍下Python语言")
    sys.exit(0)
