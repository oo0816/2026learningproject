"""
L4 · Skills + MCP 实战
=======================

## 你这关要搞懂两件事

### 1. 写一个高质量的 SKILL.md
位置：skills/my-first-skill/SKILL.md
要求：触发条件 + 步骤 + 脚本 + 模板 + smoke test
用 darwin-skill 跑 2 轮优化，记录分数变化

### 2. 接一个 MCP Server
MCP = Model Context Protocol。本质是一个标准化协议，让 agent 能连接外部数据源。

传统方式：每个数据源写一个专用工具 → 工具越来越多 → 难维护
MCP 方式：数据源提供 MCP server → agent 通过 MCP client 连接 → 自动发现可用能力

### MCP 怎么工作的？

```
Agent ⇄ MCP Client ⇄ MCP Server ⇄ 外部数据源
                          │
                    (本地进程或远程服务)
                          │
                    暴露 Tools / Resources / Prompts
```

MCP Server 暴露三种能力：
- **Tools**：agent 可以调用的函数（类似你的 TOOL_REGISTRY）
- **Resources**：agent 可以读取的数据（文件、数据库记录等）
- **Prompts**：预定义的提示模板

### 你要做什么

选一个最简单的 MCP server 接入你的 L2 agent：

推荐入门：**filesystem MCP server**
- 功能：让 agent 能读写指定目录下的文件
- 安装：`pip install mcp-server-filesystem`
- 配置：指定一个安全目录（agent 只能访问这个目录下的文件）

或者选 **sqlite MCP server**：
- 功能：让 agent 能查询 SQLite 数据库
- 安装：`pip install mcp-server-sqlite`

参考文档：https://modelcontextprotocol.io
"""

import os
import sys
import json
import subprocess
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")


# ══════════════════════════════════════════════════════════════
# 任务 1：手动启动一个 MCP server 并理解它暴露了什么
# ══════════════════════════════════════════════════════════════

def explore_mcp_server():
    """
    目标：不写代码，先用命令行理解 MCP server 是什么。

    步骤（在终端执行）：
    1. pip install mcp-server-filesystem
    2. 查看它的帮助：
       python -m mcp_server_filesystem --help
    3. 启动 server（指定一个安全目录）：
       python -m mcp_server_filesystem ./test_data/

    观察：server 启动后会等待 stdin 输入 JSON-RPC 消息。
    这就是 MCP 协议——通过标准输入输出通信。

    思考：
    - 为什么 MCP 用 stdio 而不是 HTTP？
      → 本地进程间通信，stdio 比 HTTP 更简单、更安全、零网络配置。
    - 这和你的 TOOL_REGISTRY 有什么本质区别？
      → MCP server 自己声明自己有什么工具，agent 运行时动态发现。
        你的 TOOL_REGISTRY 是写死的——加工具要改代码。
    """
    print("MCP 探索指南：")
    print("1. pip install mcp-server-filesystem")
    print("2. mkdir test_data")
    print("3. 在终端运行: python -m mcp_server_filesystem ./test_data/")
    print("4. 用 MCP Inspector 查看: npx @modelcontextprotocol/inspector")
    print()
    print("参考: https://modelcontextprotocol.io/quickstart/user")


# ══════════════════════════════════════════════════════════════
# 任务 2：写一个简单的 MCP Client（可选，理解原理用）
# ══════════════════════════════════════════════════════════════

class SimpleMCPClient:
    """
    最简 MCP Client——理解 MCP 通信原理。

    MCP 协议基于 JSON-RPC 2.0，消息格式：
    请求:  {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}
    响应:  {"jsonrpc": "2.0", "id": 1, "result": {"tools": [...]}}

    核心方法：
    - initialize: 握手，获取 server 信息
    - tools/list: 列出可用工具
    - tools/call: 调用工具
    - resources/list: 列出可用资源
    - resources/read: 读取资源

    通信方式：启动 MCP server 作为子进程，通过 stdin/stdout 收发 JSON。

    注意：这个实现是学习用的。生产环境请用官方 mcp Python SDK。
    """

    def __init__(self, server_command: list[str]):
        """
        启动 MCP server 子进程。

        参数:
            server_command: 启动命令，如 ["python", "-m", "mcp_server_filesystem", "./data"]
        """
        # TODO: 用 subprocess.Popen 启动子进程
        # stdin=PIPE, stdout=PIPE, text=True
        self.process = None

    def send(self, method: str, params: dict = None) -> dict:
        """
        发送 JSON-RPC 请求并等待响应。

        1. 构造 JSON-RPC 请求: {"jsonrpc": "2.0", "id": N, "method": ..., "params": ...}
        2. 写入 self.process.stdin
        3. 从 self.process.stdout 读取一行 JSON
        4. 返回解析后的 dict
        """
        # TODO
        pass

    def list_tools(self) -> list[dict]:
        """调用 tools/list，返回可用工具列表"""
        # TODO
        pass

    def call_tool(self, name: str, arguments: dict) -> str:
        """调用 tools/call，返回工具执行结果"""
        # TODO
        pass

    def close(self):
        """关闭 MCP server 子进程"""
        # TODO
        pass


# ══════════════════════════════════════════════════════════════
# 任务 3：把 MCP 工具接入你的 L2 Agent
# ══════════════════════════════════════════════════════════════

def bridge_mcp_to_agent(mcp_client, tool_registry):
    """
    把 MCP server 暴露的工具注册到你的 agent 的 TOOL_REGISTRY 中。

    步骤：
    1. 调用 mcp_client.list_tools() 获取 MCP server 的工具列表
    2. 把每个 MCP 工具包装成你的 TOOL_REGISTRY 能用的格式
    3. 注册到 TOOL_REGISTRY

    关键：MCP 工具的 schema 和 OpenAI function calling 的 schema 不是同一种格式！
    需要做转换——
    MCP schema:
      {"name": "read_file", "inputSchema": {"type": "object", "properties": {...}}}
    OpenAI schema:
      {"type": "function", "function": {"name": "read_file", "parameters": {...}}}

    思考：
    - 如果 MCP server 重启了，已注册的工具怎么办？
    - 如果 MCP server 新增了工具，agent 怎么知道？
    """
    # TODO
    pass


# ══════════════════════════════════════════════════════════════
# CLI
# ══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("=" * 55)
    print("L4 · Skills + MCP 实战")
    print("=" * 55)
    print()
    print("两件事要完成：")
    print("  1. 写完 skills/my-first-skill/SKILL.md")
    print("     - 配套脚本: skills/my-first-skill/run_review.py")
    print("     - 输出模板: skills/my-first-skill/template_output.md")
    print("     - 用 darwin-skill 评分 + 迭代优化")
    print()
    print("  2. 接一个 MCP server")
    print("     - 推荐: filesystem 或 sqlite")
    print("     - 写出 SimpleMCPClient（理解协议原理）")
    print("     - 把 MCP 工具桥接到你的 L2 agent")
    print()
    print("  3. 写笔记:")
    print("     - notes/l4-skills-vs-tools.md（对比表）")
    print("     - notes/l4-skill-optimization-log.md（优化记录）")
    print()
    explore_mcp_server()


# ══════════════════════════════════════════════════════════════
# 常见坑
# ══════════════════════════════════════════════════════════════
#
# 坑 1：把 Skill 当 Tool 用
#   → Skill = "怎么做"，Tool = "能做什么"。不能混。
#   → 一个 Skill 里调多个 Tool 很正常；一个 Tool 被多个 Skill 用也很正常。
#
# 坑 2：MCP server 进程管理
#   → 启动子进程后要记得关（close/terminate）。
#   → 如果 MCP server 崩溃了，agent 应该能检测到并降级处理（告诉用户"XX 功能不可用"）。
#
# 坑 3：Schema 转换出错
#   → MCP 的 inputSchema 和 OpenAI 的 function.parameters 字段名一样但嵌套结构不同。
#   → 不要假设它们能直接套用，必须做字段映射。
#
# 坑 4：Skill 写得太长太泛
#   → "帮助用户写代码"这种 skill 太泛了，agent 不知道什么时候该用它。
#   → 触发条件要具体到："当用户说 'review'/'审查'/'CR' 且当前有 git diff 时"。
#
# 坑 5：所有东西都放一个 SKILL.md
#   → 长脚本、大模板应该独立文件，SKILL.md 只引用文件路径。
#   → SKILL.md 超过 500 行就该拆了。
