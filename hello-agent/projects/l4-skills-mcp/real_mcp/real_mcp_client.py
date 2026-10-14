"""
真实 MCP Client 第一版
目标：连接 @modelcontextprotocol/server-filesystem
跑通：initialize → tools/list → list_directory → read_file
"""

import json
import shutil
import subprocess
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

BASE_DIR = Path(__file__).resolve().parent
SAFE_DIR = BASE_DIR / "test_data"
HELLO_FILE = SAFE_DIR / "hello.txt"

SAFE_DIR.mkdir(exist_ok=True)
if not HELLO_FILE.exists():
    HELLO_FILE.write_text("你好，这是 MCP 文件系统测试。\n", encoding="utf-8")

# Windows 下优先找 npx.cmd，避免 .ps1 执行策略问题
NPX = shutil.which("npx.cmd") or shutil.which("npx") or "npx.cmd"


class MCPClient:
    def __init__(self):
        command = [
            NPX,
            "-y",
            "@modelcontextprotocol/server-filesystem",
            str(SAFE_DIR),
        ]
        print("启动 MCP Server：")
        print(" ", " ".join(command))
        print()

        self.proc = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            text=True,
            encoding="utf-8",
        )
        self.next_id = 1

    def initialize(self):
        """完成 initialize 握手和 initialized 通知，返回 Server 信息。"""
        result = self.request("initialize", {
            "protocolVersion": "2025-06-18",
            "capabilities": {},
            "clientInfo": {
                "name": "real-mcp-client",
                "version": "0.1.0",
            },
        })
        self.notify("notifications/initialized")
        return result

    def list_tools(self) -> list[dict]:
        """动态发现 Server 提供的工具。"""
        result = self.request("tools/list", {})
        return result.get("tools", [])

    def call_tool(self, name: str, arguments: dict) -> str:
        """调用 MCP 工具，并把返回的 content 拼成普通文本。"""
        result = self.request("tools/call", {
            "name": name,
            "arguments": arguments,
        })
        return mcp_text(result)
    def _send(self, msg: dict):
        raw = json.dumps(msg, ensure_ascii=False)
        print(f"\nClient → Server: {raw}")
        self.proc.stdin.write(raw + "\n")
        self.proc.stdin.flush()

    def _read(self) -> dict:
        line = self.proc.stdout.readline()
        if not line:
            raise RuntimeError("MCP Server 已关闭输出通道")
        print(f"Server → Client: {line.strip()}")
        return json.loads(line)

    def request(self, method: str, params: dict | None = None) -> dict:
        rid = self.next_id
        self.next_id += 1

        msg = {
            "jsonrpc": "2.0",
            "id": rid,
            "method": method,
        }
        if params is not None:
            msg["params"] = params

        self._send(msg)

        # 真实 Server 可能先发通知。必须等到 id 对得上的回应。
        while True:
            resp = self._read()

            if "id" not in resp:
                print("[通知，跳过]", resp)
                continue

            if resp["id"] != rid:
                print("[其它回应，跳过]", resp)
                continue

            if "error" in resp:
                raise RuntimeError(f"MCP 错误：{resp['error']}")

            return resp.get("result", {})

    def notify(self, method: str, params: dict | None = None):
        msg = {
            "jsonrpc": "2.0",
            "method": method,
        }
        if params is not None:
            msg["params"] = params
        self._send(msg)

    def close(self):
        try:
            self.proc.stdin.close()
            self.proc.wait(timeout=5)
        except Exception:
            self.proc.terminate()


def mcp_text(result: dict) -> str:
    parts = []
    for item in result.get("content", []):
        if item.get("type") == "text":
            parts.append(item.get("text", ""))
    return "\n".join(parts)


def main():
    client = MCPClient()

    try:
        print("=" * 60)
        print("1. initialize 握手")
        print("=" * 60)
        init = client.request("initialize", {
            "protocolVersion": "2025-06-18",
            "capabilities": {},
            "clientInfo": {
                "name": "real-mcp-client",
                "version": "0.1.0",
            },
        })
        print("initialize 结果：", json.dumps(init, ensure_ascii=False, indent=2))

        client.notify("notifications/initialized")

        print("\n" + "=" * 60)
        print("2. tools/list 动态发现工具")
        print("=" * 60)
        tools = client.request("tools/list", {})
        tool_list = tools.get("tools", [])
        for t in tool_list:
            print(f"- {t['name']}: {t.get('description', '')}")

        print("\n" + "=" * 60)
        print("3. 调用 list_directory")
        print("=" * 60)
        listing = client.request("tools/call", {
            "name": "list_directory",
            "arguments": {"path": str(SAFE_DIR)},
        })
        print(mcp_text(listing))

        print("\n" + "=" * 60)
        print("4. 调用 read_file")
        print("=" * 60)
        file_result = client.request("tools/call", {
            "name": "read_text_file",
            "arguments": {"path": str(HELLO_FILE)},
        })
        print(mcp_text(file_result))

    finally:
        client.close()

    print("\n完成。")


if __name__ == "__main__":
    main()
