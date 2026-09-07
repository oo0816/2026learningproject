"""
L4 · 手写最小 MCP Server（纯标准库，零依赖）
============================================

目的：不看 SDK，把 MCP 协议线格式亲手跑一遍——证明它底层就是 JSON-RPC 2.0 走 stdin/stdout。

这个文件 = MCP 协议的"Server"端：
- 用 stdio（标准输入输出）和 Client 说话
- 每行一条 JSON-RPC 2.0 消息（读 stdin 一行 → 处理 → 写一行回 stdout）
- 实现了 MCP 最小会话的 3 个方法：
    initialize           握手（Client 先问：你是谁、协议版本、有哪些能力）
    tools/list           列出本 server 提供的工具（含 JSON Schema）
    tools/call           真正调用一个工具，返回结果

真正干活的工具：get_weather(城市名) —— 假装查天气，实际返回假数据。
这就是"server 只是个接线员"的体现：协议只负责听懂 tools/call，
具体的业务逻辑（这里是个假天气函数）藏在里面，协议层根本看不见。

运行：直接 python mcp_mini_server.py 它会等 stdin；配合 mcp_mini_client.py 一起看。
"""

import json
import sys
import time

# Windows 下确保 stdout 用 UTF-8，否则中文写出去会乱码/报错
sys.stdout.reconfigure(encoding="utf-8")


# ══════════════════════════════════════════════════════════════
# 工具区：真正干活的地方（协议层之下）
# ══════════════════════════════════════════════════════════════

# 工具清单：给 client 的 tools/list 用的"说明书"
# name/description/inputSchema 三项——inputSchema 就是 JSON Schema
TOOLS = [
    {
        "name": "get_weather",
        "description": "查询指定城市的实时天气（演示用假数据）",
        "inputSchema": {
            "type": "object",
            "properties": {
                "city": {"type": "string", "description": "城市名，如 北京"}
            },
            "required": ["city"],
        },
    }
]

# 假天气库：真实系统这里会是 HTTP 调第三方天气 API
FAKE_WEATHER = {
    "北京": ("晴", 26),
    "上海": ("多云", 28),
    "东京": ("小雨", 22),
}


def run_get_weather(city: str) -> str:
    """工具的真实实现。这里假装联网查天气。"""
    if city in FAKE_WEATHER:
        cond, temp = FAKE_WEATHER[city]
        return f"{city}：{cond}，{temp}°C"
    return f"抱歉，没有 {city} 的天气数据（演示库只有 北京/上海/东京）"


# 方法名 → (需要解析的字段, 处理函数) 的分发表
# 以后加方法/加工具，只改这里，主循环不用动——数据驱动
DISPATCH = {
    # MCP 核心方法
    "initialize": lambda p: {
        "protocolVersion": "2024-11-05",
        "capabilities": {"tools": {}},
        "serverInfo": {"name": "mcp-mini-server", "version": "0.1.0"},
    },
    "tools/list": lambda p: {"tools": TOOLS},
    "ping": lambda p: {},
    # 本 server 自己的工具调用
    "tools/call": lambda p: handle_call(p),
}


def handle_call(params: dict) -> dict:
    """执行 tools/call。params = {"name": 工具名, "arguments": {...}}"""
    name = params.get("name")
    args = params.get("arguments", {})
    if name == "get_weather":
        text = run_get_weather(args.get("city", ""))
        return {"content": [{"type": "text", "text": text}], "isError": False}
    return {
        "content": [{"type": "text", "text": f"未知工具: {name}"}],
        "isError": True,
    }


# ══════════════════════════════════════════════════════════════
# 协议主循环
# ══════════════════════════════════════════════════════════════

def serve():
    """一次 server 会话：反复 读一行 → 回一行，直到 stdin 关闭。"""
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError as e:
            # 收到的不是合法 JSON：回一个协议错误
            respond({"jsonrpc": "2.0", "id": None,
                     "error": {"code": -32700, "message": f"Parse error: {e}"}})
            continue

        method = msg.get("method")
        handler = DISPATCH.get(method)

        # 通知（没有 id）：不需要回任何东西，比如 notifications/initialized
        if "id" not in msg:
            continue

        if handler is None:
            respond({"jsonrpc": "2.0", "id": msg["id"],
                     "error": {"code": -32601, "message": f"Method not found: {method}"}})
            continue

        try:
            result = handler(msg.get("params") or {})
            respond({"jsonrpc": "2.0", "id": msg["id"], "result": result})
        except Exception as e:
            respond({"jsonrpc": "2.0", "id": msg["id"],
                     "error": {"code": -32603, "message": f"Internal error: {e}"}})


def respond(obj: dict):
    """把一条 JSON 写一行到 stdout，并立刻 flush（否则 client 等不到）。"""
    sys.stdout.write(json.dumps(obj, ensure_ascii=False) + "\n")
    sys.stdout.flush()


if __name__ == "__main__":
    serve()
