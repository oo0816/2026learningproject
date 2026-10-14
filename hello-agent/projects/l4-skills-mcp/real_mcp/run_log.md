# 真实 MCP Server 接入记录

- 日期：2026-10-14
- Server：`@modelcontextprotocol/server-filesystem`
- Server 名称：`secure-filesystem-server`
- Server 版本：`1.0.0`
- 协议版本：`2025-06-18`
- 传输方式：stdio
- 安全目录：`real_mcp/test_data`

## 1. initialize

握手成功，Server 返回：

- `protocolVersion`: `2025-06-18`
- `capabilities.tools.listChanged`: `true`
- `serverInfo.name`: `secure-filesystem-server`
- `serverInfo.version`: `1.0.0`

## 2. tools/list

Client 运行时动态发现了文件系统工具，包括：

- `read_file`（已弃用）
- `read_text_file`
- `read_media_file`
- `read_multiple_files`
- `write_file`
- `edit_file`
- `create_directory`
- `list_directory`
- `list_directory_with_sizes`
- `directory_tree`
- `move_file`
- `search_files`
- `get_file_info`
- `list_allowed_directories`

## 3. tools/call: list_directory

调用参数：

- `path`: `real_mcp/test_data`

返回：

```text
[FILE] hello.txt
```

## 4. tools/call: read_file

调用参数：

- `path`: `real_mcp/test_data/hello.txt`

返回：

```text
你好，这是 MCP 文件系统测试。
```

## 观察到的问题

1. `read_file` 已被 Server 标记为 deprecated，下一次应改用 `read_text_file`。
2. Client 尚未声明 MCP Roots 能力，Server 因此回退使用启动参数里的 allowed directories。
3. Server 的 `tools.listChanged = true`，说明工具列表可以动态变化，Agent 设计时要考虑重新发现工具。
4. npm 提示有新版本可用，但不影响本次 MCP 功能。

## 本阶段结论

真实 MCP Server 的最小闭环已经跑通：

```text
Client 启动 Server
-> initialize 握手
-> notifications/initialized
-> tools/list 动态发现工具
-> tools/call 调用 list_directory
-> tools/call 调用 read_file
-> 收到真实文件内容
```
