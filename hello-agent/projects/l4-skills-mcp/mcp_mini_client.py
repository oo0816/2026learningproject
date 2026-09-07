"""
L4 · MCP Mini Client（纯标准库，零依赖）
=======================================

对应 mcp_mini_server.py 的 Client 端。演示一个 MCP 会话从握手到调工具的完整过程，
并把每一行 JSON-RPC 2.0 报文原样打印出来——让你亲眼看到 Q3 笔记里的那些消息。

MCP 三种消息类型（复习 Q3）：
  ① 请求   有 id，期待 result 回应
  ② 通知   没有 id，server 不回应（如 notifications/initialized）
  ③ 回应   和请求共用同一个 id，让一问一答能对上

运行：
  python mcp_mini_client.py
会自己启动 mcp_mini_server.py 作为子进程（stdio 通道）。
"""

import json
import subprocess
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

SERVER = Path(__file__).parent / "mcp_mini_server.py"


class MiniMCPClient:
    """把 MCP server 当子进程拉起来，通过 stdin/stdout 说 JSON-RPC。"""

    def __init__(self):
        # text=True + encoding 让管道收发的是字符串而不是 bytes
        self.proc = subprocess.Popen(
            [sys.executable, str(SERVER)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            text=True,
            encoding="utf-8",
        )
        self.next_id = 1

    def _send_raw(self, raw: str):
        """把一行原始 JSON 写进 server 的 stdin。"""
        print(f"\n  ┌─ Client → Server 发送：\n  │ {raw}")
        self.proc.stdin.write(raw + "\n")
        self.proc.stdin.flush()

    def _recv_raw(self) -> str:
        """从 server 的 stdout 读一行回应。"""
        line = self.proc.stdout.readline()
        print(f"  └─ Server → Client 回应：\n    {line.strip()}")
        return line

    # ── 高层封装：三种 MCP 消息 ──────────────────────────────

    def request(self, method: str, params: dict | None = None) -> dict:
        """① 请求：带自增 id，等 result。"""
        msg = {
            "jsonrpc": "2.0",
            "id": self.next_id,
            "method": method,
            "params": params or {},
        }
        self.next_id += 1
        raw = json.dumps(msg, ensure_ascii=False)
        self._send_raw(raw)
        resp = json.loads(self._recv_raw())
        return resp.get("result", resp)

    def notify(self, method: str, params: dict | None = None):
        """② 通知：没有 id，发完就走，不等回应。"""
        msg = {"jsonrpc": "2.0", "method": method, "params": params or {}}
        self._send_raw(json.dumps(msg, ensure_ascii=False))

    def close(self):
        self.proc.stdin.close()
        self.proc.wait(timeout=5)


def main():
    client = MiniMCPClient()
    print("=" * 60)
    print("MCP 最小会话演示：Client ⇄ 手写 Server (JSON-RPC 2.0 over stdio)")
    print("=" * 60)

    # ① 握手：client 先问 server 是谁、协议版本、有哪些能力
    print("\n【步骤 1/4】initialize —— 双方握手，确认协议版本与能力")
    client.request("initialize")

    # ② 通知：client 告诉 server"我初始化完了"。没 id，server 不回。
    print("\n【步骤 2/4】notifications/initialized —— 通知（无 id，server 不回应）")
    client.notify("notifications/initialized")

    # ③ tools/list：问 server 提供哪些工具（含 JSON Schema 说明书）
    print("\n【步骤 3/4】tools/list —— 运行时动态发现工具")
    result = client.request("tools/list")
    tools = result.get("tools", [])
    print(f"\n  → 发现 {len(tools)} 个工具：")
    for t in tools:
        print(f"      · {t['name']}: {t['description']}")
        print(f"        参数: {json.dumps(t['inputSchema'], ensure_ascii=False)}")

    # ④ tools/call：真正调用 get_weather，server 返回 content 数组
    print("\n【步骤 4/4】tools/call —— 调用 get_weather(city=北京)")
    resp = client.request("tools/call", {
        "name": "get_weather",
        "arguments": {"city": "北京"},
    })
    text = resp["content"][0]["text"]
    print(f"\n  → 工具返回: {text}")

    print("\n" + "=" * 60)
    print("会话结束。对照笔记：这是 Q3 那 4 条消息的实机版。")
    print("真正的业务逻辑（假天气库）藏在 server 里，协议层看不到——")
    print("这就是 MCP Server 只是'接线员'的含义。")
    print("=" * 60)
    client.close()


if __name__ == "__main__":
    main()
