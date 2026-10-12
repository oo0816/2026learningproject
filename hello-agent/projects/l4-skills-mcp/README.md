# L4 · Skills + MCP 实战

## 学习目标

1. 理解 Skill / Tool / MCP / A2A 的区别和协作关系
2. 写出一个高质量、可复用的 SKILL.md（含脚本、模板、smoke test）
3. 接一个 MCP server，理解协议原理

## 产出物

- `skills/japanese-exam-review/SKILL.md` — 第一个完整 skill（自选主题：日语 CS 复习 PDF 生成器）✅
- `skills/japanese-exam-review/scripts/` — 配套脚本（guide_style 版式引擎 / 双通路渲染 / check_coverage）
- `skills/japanese-exam-review/examples/` — 输出模板/示例 JSON
- 🔗 该技能已独立成仓库：<https://github.com/oo0816/-japanese-exam-review-skill>（本地 `skills/japanese-exam-review/` 是指向该仓库的链接）
- `projects/l4-skills-mcp/l4-skills-vs-tools.md` — 概念对比表
- `projects/l4-skills-mcp/l4-skill-optimization-log.md` — darwin-skill 优化记录（75.7→82.7）

## ⬜ 待做：接一个真实 MCP server

> 当前进度：skill 部分 ✅ 已完成；**MCP 部分还没接真实 server**（只有下面的手写协议 demo，不算完成"接 MCP server"这一步）。
> 下一步：实机接一个 filesystem/sqlite MCP server 并调用其工具，然后回来更新本段。

```bash
# 1. 接入 MCP server（先手动体验）
pip install mcp-server-filesystem
mkdir test_data
python -m mcp_server_filesystem ./test_data/

# 2. 用 MCP Inspector 可视化查看
npx @modelcontextprotocol/inspector
```

## 手写最小 MCP Server（纯标准库，零依赖）

配套文件（2026-09-07 亲手写的协议 demo）：

| 文件 | 作用 |
|---|---|
| `mcp_mini_server.py` | MCP Server 端：JSON-RPC 2.0 over stdio，实现 initialize / tools/list / tools/call，暴露一个假天气工具 |
| `mcp_mini_client.py` | MCP Client 端：把 server 当子进程拉起，走完四步握手并把每条报文原样打印 |

```bash
python mcp_mini_client.py
```

跑完会看到 Q3 笔记那 4 条消息的实机版——这就是"protocol 长什么样"的答案落地。

## B 线验证

- [x] 一个 SKILL.md 被 agent 加载后，agent 的 system prompt 里多了什么？（答案见 `notes/l4-skill-mcp-qna.md` Q5）
- [x] MCP 和普通 API 调用的区别是什么？为什么 agent 需要 MCP？（答案见 `notes/l4-skill-mcp-qna.md` Q4 + `l4-skills-vs-tools.md` Q2）

## C 线验证

- [x] 用 darwin-skill 给自己写的 SKILL.md 打分，记录初始分数
- [x] 根据评分报告改一版，再打分，记录涨幅
