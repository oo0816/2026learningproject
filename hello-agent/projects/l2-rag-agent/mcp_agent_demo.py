"""
L2 Agent + 真实 MCP 工具（只读版）

这个文件不改 L2 的原有代码，只在启动 L2 Agent 前：
1. 启动真实 filesystem MCP Server
2. 动态发现 MCP tools
3. 只把只读工具注册进 tools.TOOL_REGISTRY
4. 运行 L2 的 run_agent，让模型自己决定是否调用 MCP 工具

第一版故意不注册 write_file / edit_file / move_file，避免 Agent 误写文件。
"""

import sys
from pathlib import Path

# ------------------------------------------------------------
# 路径准备
# ------------------------------------------------------------
L2_DIR = Path(__file__).resolve().parent
PROJECTS_DIR = L2_DIR.parent
MCP_DIR = PROJECTS_DIR / "l4-skills-mcp" / "real_mcp"

sys.path.insert(0, str(L2_DIR))
sys.path.insert(0, str(MCP_DIR))

# ------------------------------------------------------------
# 导入 L2 和 MCP 模块
# ------------------------------------------------------------
from real_mcp_client import MCPClient
from mcp_tool_bridge import mcp_tool_to_openai_schema

import tools
import main as l2_main


# 第一版只注册只读工具；read_file 已弃用，不注册
READ_ONLY_MCP_TOOLS = {
    "read_text_file",
    "read_multiple_files",
    "list_directory",
    "list_directory_with_sizes",
    "directory_tree",
    "search_files",
    "get_file_info",
    "list_allowed_directories",
}


def make_mcp_func(client: MCPClient, tool_name: str):
    """把一次 MCP tools/call 包装成本地函数，供 L2 execute_tool 调用。"""

    def func(**kwargs) -> str:
        return client.call_tool(tool_name, kwargs)

    return func


def register_read_only_mcp_tools(client: MCPClient) -> list[str]:
    """发现 MCP 工具，并把只读工具注册到 L2 的 TOOL_REGISTRY。"""
    registered = []

    for tool in client.list_tools():
        name = tool["name"]
        if name not in READ_ONLY_MCP_TOOLS:
            continue

        tools.TOOL_REGISTRY[name] = {
            "name": name,
            "func": make_mcp_func(client, name),
            "risk_level": "safe",
            "schema": mcp_tool_to_openai_schema(tool),
        }
        registered.append(name)

    return registered


def main():
    client = MCPClient()

    try:
        print("=" * 60)
        print("启动真实 MCP Server")
        print("=" * 60)
        client.initialize()

        print("\n" + "=" * 60)
        print("注册只读 MCP 工具到 L2 TOOL_REGISTRY")
        print("=" * 60)
        registered = register_read_only_mcp_tools(client)
        for name in registered:
            print(f"- {name}")

        test_data = MCP_DIR / "test_data"
        default_query = (
            f"请调用 list_directory 工具列出目录 {test_data} 中的文件，"
            f"然后调用 read_text_file 读取 {test_data / 'hello.txt'}，"
            "最后用中文总结这个文件的内容。"
        )

        query = sys.argv[1] if len(sys.argv) > 1 else default_query

        print("\n" + "=" * 60)
        print("L2 Agent 开始运行")
        print("=" * 60)
        print(f"用户请求：{query}\n")

        answer = l2_main.run_agent(query, verbose=True)
        print("\n" + "=" * 60)
        print("最终回答")
        print("=" * 60)
        print(answer)

    finally:
        client.close()


if __name__ == "__main__":
    main()
