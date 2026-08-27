"""
L3 · Nano Harness — 从 Agent 到 Harness
=========================================

## 什么是 Harness？

你写的 L1/L2 agent 是一个"裸奔"的 agent loop——工具调用、记忆管理、消息收发
全部揉在一起。这在 demo 阶段够用，但加功能时会越来越乱。

Harness 就是"把 agent loop 拆成可替换的模块"。一个现代 agent harness 通常有：

```
┌──────────────────────────────────────────┐
│               Harness 架构               │
│                                          │
│  ┌──────────┐  ┌──────────┐  ┌────────┐ │
│  │  Agent   │  │  Tool    │  │Permission│ │
│  │  Loop    │──│  Registry│──│  Gate   │ │
│  └──────────┘  └──────────┘  └────────┘ │
│       │              │            │      │
│  ┌──────────┐  ┌──────────┐  ┌────────┐ │
│  │ Session  │  │  Context │  │  Error  │ │
│  │  Store   │  │ Compactor│  │ Logger  │ │
│  └──────────┘  └──────────┘  └────────┘ │
└──────────────────────────────────────────┘
```

L3 的目标：把你的 L1 agent 升级成一个模块化的 nano harness。

## L3 对比 L1/L2

| 模块 | L1 | L2 | L3 |
|------|----|----|-----|
| Agent Loop | 写死在 main.py | 写死在 main.py | 独立的 Agent 类 |
| 工具管理 | dict 散落 | TOOL_REGISTRY | ToolRegistry 类（注册/查找/校验） |
| 权限 | 无 | risk_level 标记 | PermissionGate（safe/needs_approval/blocked） |
| 会话存储 | 无 | SessionMemory | SessionStore（保存/恢复/多会话） |
| 上下文管理 | 无 | manage_context_window() | ContextCompactor（压缩策略可配置） |
| 错误日志 | print() | print() | 分级日志（INFO/WARN/ERROR）+ 调用链追踪 |

## 你要实现什么

不要求从零写。以你 L1 的 main.py 为起点，逐步模块化：

1. **ToolRegistry 类**：替代 TOOLS_MAP dict
   - register(tool): 注册工具，校验 schema 必填字段
   - get(name): 按名称查找
   - get_schemas(): 返回所有 schema
   - list(): 列出所有已注册工具

2. **PermissionGate 类**：替代 risk_level 字符串
   - 三级：SAFE（自动）/ NEEDS_APPROVAL（需确认）/ BLOCKED（拒绝）
   - check(tool_name): 返回是否允许执行
   - 可配置规则（如：所有文件删除操作 = BLOCKED）

3. **SessionStore 类**：替代 SessionMemory
   - save(session_id, messages): 保存对话到 JSON 文件
   - load(session_id): 恢复对话
   - list_sessions(): 列出所有已保存的会话

4. **结构化日志**：
   - 每条日志包含：时间戳、级别、模块名、消息
   - 记录每次工具调用的：工具名、参数、结果（前 100 字）、耗时

## 必答问题（边写边想）

- agent loop 在哪个文件？核心逻辑多少行？（对比 learn-claude-code 或 claw0）
- 工具是怎么注册的？tool schema 包含哪些字段？
- 权限控制在哪里？每次调工具都要确认还是分级别？
- session 是怎么存、怎么恢复的？
- 上下文太长时怎么压缩？触发条件是什么？
"""

import os
import sys
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional
from openai import OpenAI

sys.stdout.reconfigure(encoding="utf-8")

# ══════════════════════════════════════════════════════════════
# 模块 1：ToolRegistry — 工具注册表
# ══════════════════════════════════════════════════════════════

class ToolRegistry:
    """
    工具注册表：注册、查找、校验、导出 schema。

    比 L2 的 TOOL_REGISTRY dict 多了什么？
    - schema 校验：注册时检查必填字段（name, description, parameters）
    - 防重复注册：同名工具注册两次时警告或拒绝
    - 分类管理：按 risk_level 或功能分组

    设计思考：
    - 为什么注册时校验而不在调用时校验？
      → 尽早暴露配置错误。工具注册是启动阶段，调用是运行阶段——前者出错更好排查。
    """

    def __init__(self):
        # TODO: 初始化存储结构
        pass

    def register(self, name: str, func: Callable, schema: dict,
                 risk_level: str = "safe") -> bool:
        """
        注册一个工具。

        校验项：
        - schema 必须有 "function" 键
        - function 内必须有 name, description, parameters
        - parameters.type 必须是 "object"
        - 不能和已有工具重名

        返回 True 表示注册成功，False 表示失败。
        """
        # TODO
        pass

    def get(self, name: str):
        """按名称查找工具，找不到返回 None"""
        # TODO
        pass

    def get_schemas(self) -> list[dict]:
        """返回所有工具的 OpenAI function calling schema"""
        # TODO
        pass

    def execute(self, name: str, args: dict) -> str:
        """执行工具，带错误处理"""
        # TODO
        pass

    def list_tools(self) -> list[str]:
        """列出所有已注册的工具名"""
        # TODO
        pass


# ══════════════════════════════════════════════════════════════
# 模块 2：PermissionGate — 权限控制
# ══════════════════════════════════════════════════════════════

class PermissionGate:
    """
    权限控制闸门。

    三级权限：
    - ALLOW: 自动执行（读操作、计算）
    - ASK: 需要用户确认（发邮件、修改文件）
    - DENY: 完全禁止（rm -rf、drop table）

    两种实现方式（L3 先做 A，L5 升级到 B）：
    A) 规则匹配：按工具名/关键词/risk_level 匹配
    B) 动态策略：每次调用时根据上下文决定（参数内容、调用历史等）
    """

    ALLOW = "allow"
    ASK = "ask"
    DENY = "deny"

    def __init__(self):
        # TODO: 初始化规则列表
        # 规则格式：{"pattern": "web_search", "action": "allow"}
        # pattern 支持通配符，如 "file_delete*"
        self.rules = []

    def add_rule(self, pattern: str, action: str):
        """添加一条权限规则"""
        # TODO
        pass

    def check(self, tool_name: str) -> str:
        """
        检查工具是否可以执行。
        返回 "allow" | "ask" | "deny"

        匹配逻辑：遍历规则列表，第一个匹配的规则生效。
        没有匹配的规则时，默认行为是什么？
        → 安全优先：默认 DENY（白名单模式）
          还是方便优先：默认 ALLOW（黑名单模式）？
          这是一个重要的设计选择。
        """
        # TODO
        pass

    def request_approval(self, tool_name: str, args: dict) -> bool:
        """
        ASK 级别的工具需要用户确认。
        L3 简化实现：打印工具名和参数，等待用户输入 y/n。
        """
        # TODO
        pass


# ══════════════════════════════════════════════════════════════
# 模块 3：SessionStore — 会话存储
# ══════════════════════════════════════════════════════════════

class SessionStore:
    """
    会话存储：把对话历史存到磁盘，下次启动能恢复。

    存储目录：./sessions/
    每个会话一个 JSON 文件：sessions/{session_id}.json

    文件结构：
    {
      "session_id": "20260720-143000",
      "created_at": "2026-07-20T14:30:00",
      "updated_at": "2026-07-20T15:00:00",
      "messages": [
        {"role": "user", "content": "你好"},
        {"role": "assistant", "content": "你好！有什么可以帮助你的？"},
        ...
      ],
      "metadata": {
        "tool_call_count": 5,
        "user_name": "张三"  // 从 session memory 提取的
      }
    }

    关键设计决策：
    - 什么时候保存？每次对话轮次后自动保存？还是用户手动 /save？
    - 如果 messages 有 500 条（几万 token），每次保存都写整个文件会不会太慢？
    - 多个会话同时存在时，怎么区分？
    """
    # TODO: 实现 SessionStore
    pass


# ══════════════════════════════════════════════════════════════
# 模块 4：结构化日志
# ══════════════════════════════════════════════════════════════

class Logger:
    """简单的分级日志"""

    def __init__(self, log_file: str = None):
        # TODO
        pass

    def info(self, msg: str):
        # TODO: [2026-07-20 14:30:01] [INFO] msg
        pass

    def warn(self, msg: str):
        # TODO
        pass

    def error(self, msg: str):
        # TODO
        pass

    def tool_call(self, name: str, args: dict, result: str, elapsed: float):
        """记录一次工具调用"""
        # TODO
        pass


# ══════════════════════════════════════════════════════════════
# 模块 5：Agent 类 — 把所有模块组装起来
# ══════════════════════════════════════════════════════════════

class Agent:
    """
    模块化的 Agent。

    和 L1 的 run_agent() 函数有什么区别？
    - L1：一个函数干了所有事
    - L3：Agent 类持有 ToolRegistry、PermissionGate、SessionStore、Logger
    - Agent 类负责协调，具体工作交给各个模块

    这符合"单一职责原则"：每个类只做一件事，Agent 类负责编排。
    """

    def __init__(self, client: OpenAI, model: str = "deepseek-chat"):
        # TODO: 初始化所有模块
        self.tool_registry = ToolRegistry()
        self.permission_gate = PermissionGate()
        self.session_store = SessionStore()
        self.logger = Logger()

    def run(self, user_query: str, session_id: str = None) -> str:
        """执行一次 agent 对话"""
        # TODO: 实现 agent loop
        # 和 L1 结构类似，但：
        # - 工具执行前走 PermissionGate.check()
        # - 每步记录 Logger
        # - 会话保存/恢复通过 SessionStore
        pass


# ══════════════════════════════════════════════════════════════
# CLI 入口
# ══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("=" * 55)
    print("L3 · Nano Harness（待实现）")
    print("=" * 55)
    print()
    print("路线图：")
    print("  1. 实现 ToolRegistry（注册/查找/校验/导出）")
    print("  2. 实现 PermissionGate（三级权限 + 规则匹配）")
    print("  3. 实现 SessionStore（保存/恢复/多会话）")
    print("  4. 实现 Logger（分级日志 + 工具调用追踪）")
    print("  5. 用 Agent 类组装，跑通 L1 的 3 个测试用例")
    print()
    print("参考：")
    print("  - L1 代码：projects/l1-mini-agent/main.py")
    print("  - L2 代码：projects/l2-rag-agent/*.py")
    print("  - 必读仓库：learn-claude-code / claw0")


# ══════════════════════════════════════════════════════════════
# 常见坑
# ══════════════════════════════════════════════════════════════
#
# 坑 1：过度设计
#   → L3 只需要 5 个模块。不要一开始就搞 20 个类。
#   → 先写一个能跑的 Agent 类，再慢慢把功能抽成独立模块。
#
# 坑 2：PermissionGate 和 ToolRegistry 的职责边界模糊
#   → Registry 只管"这个工具存在吗？怎么调用？"
#   → Gate 只管"这个工具现在能调吗？"
#   → 它们是独立的模块，不要互相调用。
#
# 坑 3：SessionStore 存太多东西
#   → 只存 messages 和必要的 metadata。
#   → 不要尝试把整个 Agent 状态序列化（太复杂且难以维护）。
#
# 坑 4：忘记对比 learn-claude-code 的架构
#   → L3 的核心目标是"理解一个真正的 harness 怎么设计"。
#   → 写完自己的 nano harness 后，一定要去读 learn-claude-code 的 agent loop，
#     对比差异（README 要求列 3 点）。
