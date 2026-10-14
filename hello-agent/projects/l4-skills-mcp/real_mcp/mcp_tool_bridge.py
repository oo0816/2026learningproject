"""
MCP -> Agent Tool Schema 桥接层（第一版）

目标：
1. 启动真实 filesystem MCP Server
2. 动态发现 MCP tools
3. 把 MCP inputSchema 转成 OpenAI function calling schema
4. 给每个 MCP 工具分配 risk_level
5. 实际调用一次 read_text_file，证明桥接可用

暂不接入 L2 Agent。先把桥接层单独跑通。
"""

import json
import sys

sys.stdout.reconfigure(encoding="utf-8")

from real_mcp_client import HELLO_FILE, MCPClient


SAFE_TOOLS = {
    "read_file",
    "read_text_file",
    "read_media_file",
    "read_multiple_files",
    "list_directory",
    "list_directory_with_sizes",
    "directory_tree",
    "search_files",
    "get_file_info",
    "list_allowed_directories",
}

APPROVAL_TOOLS = {
    "write_file",
    "edit_file",
    "create_directory",
    "move_file",
}


def risk_level_for(tool_name: str) -> str:
    if tool_name in SAFE_TOOLS:
        return "safe"
    if tool_name in APPROVAL_TOOLS:
        return "needs_approval"
    return "needs_approval"


def mcp_tool_to_openai_schema(tool: dict) -> dict:
    """MCP tool -> OpenAI function calling tool schema。"""
    parameters = dict(tool.get("inputSchema", {
        "type": "object",
        "properties": {},
    }))

    # MCP inputSchema 带 JSON Schema 元数据，Agent function calling 通常不需要
    parameters.pop("$schema", None)

    return {
        "type": "function",
        "function": {
            "name": tool["name"],
            "description": tool.get("description", ""),
            "parameters": parameters,
        },
    }


def main():
    client = MCPClient()

    try:
        print("=" * 60)
        print("初始化真实 MCP Server")
        print("=" * 60)
        init = client.initialize()
        print(json.dumps(init, ensure_ascii=False, indent=2))

        print("\n" + "=" * 60)
        print("发现并转换工具")
        print("=" * 60)
        tools = client.list_tools()
        print(f"共发现 {len(tools)} 个 MCP 工具\n")

        converted = []
        for tool in tools:
            schema = mcp_tool_to_openai_schema(tool)
            risk = risk_level_for(tool["name"])
            converted.append({
                "name": tool["name"],
                "risk_level": risk,
                "schema": schema,
            })

            required = schema["function"]["parameters"].get("required", [])
            print(f"- {tool['name']} [{risk}] required={required}")

        print("\n" + "=" * 60)
        print("调用 read_text_file")
        print("=" * 60)
        content = client.call_tool("read_text_file", {
            "path": str(HELLO_FILE),
        })
        print(content)

        print("\n桥接验证成功。下一步才把这些工具注册到 Agent。")

    finally:
        client.close()


if __name__ == "__main__":
    main()

