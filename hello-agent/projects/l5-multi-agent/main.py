"""
L5 · 多 Agent 协作
==================

## 核心概念：多 Agent 不是魔法

多 Agent 本质上就是"多个 agent loop 在跑，通过某种方式传递信息"。
它不是让一个 agent 更聪明，而是让多个 agent 各司其职。

### 为什么需要多 Agent？

单 Agent 的问题：
- 一个 system prompt 要塞下所有指令 → 越来越长、越来越模糊
- 一个 agent 既要做研究又要写报告 → 上下文切换成本高
- 没有制衡机制 → agent 可能一条路走到黑

多 Agent 的优势：
- 每个 agent 职责单一，system prompt 短且精准
- 可以并行工作（research agent 搜资料的同时，writer agent 开始写大纲）
- 有检查机制（reviewer agent 审核 writer 的输出）

### 三种经典协作模式

```
模式 1：Supervisor（主管模式）
┌─────────────┐
│  Supervisor │ ← 分配任务、汇总结果
└──┬──┬──┬───┘
   │  │  │
   ▼  ▼  ▼
  R  W  Rv     ← Researcher / Writer / Reviewer

模式 2：Pipeline（流水线模式）
Research → Write → Review → （不通过则循环）

模式 3：Peer-to-Peer（对等协商）
Agent A ←→ Agent B  各自有专长，互相提问
```

L5 先用 Supervisor 模式——最简单、最可控。

### Agent 之间怎么通信？

三种方式，由简到繁：
1. **共享消息队列**：所有 agent 往同一个 messages list 写，L5 用这个
2. **结构化交接**：上一个 agent 的输出是下一个的输入（Pipeline 模式）
3. **消息总线**：每个 agent 订阅自己关心的消息（复杂但灵活）

## 你的任务

实现一个 Supervisor 模式的 3-agent 协作系统：
- **Researcher**：搜索 + 汇总资料
- **Writer**：根据研究结果写报告
- **Reviewer**：审核报告，给通过/修改意见

额外的硬性要求：
- 最大循环次数限制（防止 reviewer 一直不满意导致死循环）
- 每次循环后检查是否超预算/超时
- 完整的调用链 trace
"""

import os
import sys
import json
import time
from openai import OpenAI

sys.stdout.reconfigure(encoding="utf-8")

# ── API 连接（沿用 L1/L2 的方式）──
# TODO: 初始化 OpenAI client

# ══════════════════════════════════════════════════════════════
# 任务 1：定义 Agent 角色
# ══════════════════════════════════════════════════════════════

class BaseAgent:
    """
    所有 agent 的基类。

    每个 agent 有：
    - 名字（用于日志和 trace）
    - 角色描述（注入 system prompt）
    - 可用工具（不是所有 agent 都需要所有工具）
    - 独立的 messages 历史（也可以共享一个消息总线）

    思考：不同 agent 用不同模型行不行？
    → 可以！Researcher 用便宜的模型、Reviewer 用最强的模型——成本优化。
    """

    def __init__(self, name: str, role: str, tools: list = None):
        # TODO
        pass

    def think(self, task: str, context: str = "") -> str:
        """
        Agent 执行一次"思考→行动"。

        参数:
            task: 当前要完成的任务描述
            context: 上下文信息（如 Researcher 的输出给 Writer）

        返回: agent 的输出文本
        """
        # TODO
        pass


# ══════════════════════════════════════════════════════════════
# 任务 2：实现 Supervisor 编排
# ══════════════════════════════════════════════════════════════

class Supervisor:
    """
    主管 Agent：负责分配任务、协调流程、判断是否完成。

    工作流程：
    1. 接收用户需求
    2. 派发给 Researcher → 收集资料
    3. Researcher 的输出 → 交给 Writer → 生成报告
    4. Writer 的输出 → 交给 Reviewer → 审核
    5. Reviewer 通过 → 返回最终报告
    6. Reviewer 不通过 → 把修改意见给 Writer → 回到步骤 4

    关键保护：
    - max_review_loops: Reviewer 最多让 Writer 改 N 次，超过则强制通过并标记
    - total_timeout: 整个流程的总超时
    - trace_log: 记录每一步的输入/输出/耗时，便于调试
    """

    def __init__(self, max_review_loops: int = 3, total_timeout: int = 120):
        # TODO: 创建 Researcher、Writer、Reviewer 三个 agent
        self.researcher = None
        self.writer = None
        self.reviewer = None
        self.max_review_loops = max_review_loops
        self.total_timeout = total_timeout
        self.trace_log = []

    def run(self, user_request: str) -> dict:
        """
        执行一次完整的多 agent 协作。

        返回:
        {
            "final_report": "最终报告内容",
            "review_loops": 2,           # Reviewer 让 Writer 改了几次
            "trace": [...],              # 完整的调用链
            "total_time": 45.2,          # 总耗时
            "total_tokens": 12000,       # 总 token 消耗（如果可以获取）
        }
        """
        # TODO: 实现 Supervisor 编排逻辑
        # 1. Research 阶段
        # 2. Write 阶段
        # 3. Review 阶段（可能循环）
        # 4. 返回最终结果 + trace
        pass


# ══════════════════════════════════════════════════════════════
# 任务 3：Trace 日志
# ══════════════════════════════════════════════════════════════

class TraceLogger:
    """
    调用链追踪：可以看到每个 agent 在什么时间做了什么。

    trace 的每一项：
    {
        "timestamp": "14:30:01.234",
        "agent": "Researcher",
        "action": "tool_call",
        "detail": "web_search('量子计算最新进展')",
        "result_preview": "找到 3 条结果...",
        "elapsed_ms": 2340
    }
    """

    def __init__(self):
        self.traces = []

    def log(self, agent: str, action: str, detail: str, result_preview: str = "", elapsed_ms: float = 0):
        # TODO
        pass

    def report(self) -> str:
        """生成人类可读的 trace 报告"""
        # TODO
        pass


# ══════════════════════════════════════════════════════════════
# CLI 入口
# ══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("=" * 55)
    print("L5 · 多 Agent 协作（待实现）")
    print("=" * 55)
    print()
    print("实现顺序：")
    print("  1. BaseAgent 类（定义角色、工具、think 方法）")
    print("  2. Researcher / Writer / Reviewer（继承 BaseAgent）")
    print("  3. TraceLogger（记录每一步的输入输出）")
    print("  4. Supervisor（编排三个 agent + 循环控制）")
    print("  5. 写 15+ 测试用例到 evals.md")
    print()
    print("测试场景建议：")
    print("  - 正常流程：研究→写报告→审核通过")
    print("  - Reviewer 不满意 1 次：研究→写→审（改）→改写→审（通过）")
    print("  - Reviewer 不满意达到上限：强制通过并标记")
    print("  - 超时保护：整个流程超过 total_timeout 时优雅终止")
    print("  - 空输入、超长输入、特殊字符输入")


# ══════════════════════════════════════════════════════════════
# 常见坑
# ══════════════════════════════════════════════════════════════
#
# 坑 1：把多 Agent 当万能药
#   → 多 Agent 增加延迟和成本。如果一个 agent 就能干好的活，不要拆。
#   → L5 是学习"怎么协调"，不是学习"怎么拆得越细越好"。
#
# 坑 2：Reviewer 永远不满意 → 死循环
#   → 这是多 agent 系统最经典的问题。
#   → 解决方案：max_review_loops + 每次循环记录修改了什么 + 防止反复横跳。
#   → 思考：如果在 Reviewer 的 prompt 里加一句"你最多只能要求修改 3 次"，有用吗？
#
# 坑 3：Agent 之间传递的信息丢失
#   → Researcher 搜到了 5 个链接，Writer 只用了其中 2 个——其他 3 个丢了。
#   → 用结构化格式传递（dict/JSON），而不是自由文本。
#
# 坑 4：所有 agent 共用一个 messages list → 混乱
#   → Researcher 的 tool 调用结果出现在 Writer 的上下文中，Writer 会困惑。
#   → 每个 agent 保持独立的 messages，Supervisor 负责"翻译"传递。
#
# 坑 5：Trace 日志太简略，出问题时无法定位
#   → 至少记录：哪个 agent → 什么操作 → 输入是什么 → 输出是什么 → 耗时多少。
#   → 如果 Reviewer 一直 reject，你需要在 trace 里看到它每次 reject 的理由。
