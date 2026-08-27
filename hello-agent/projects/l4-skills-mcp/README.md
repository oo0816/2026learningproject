# L4 · Skills + MCP 实战

## 学习目标

1. 理解 Skill / Tool / MCP / A2A 的区别和协作关系
2. 写出一个高质量、可复用的 SKILL.md（含脚本、模板、smoke test）
3. 接一个 MCP server，理解协议原理

## 产出物

- `skills/my-first-skill/SKILL.md` — 自选主题的 skill
- `skills/my-first-skill/run_review.py` — 配套脚本
- `skills/my-first-skill/template_output.md` — 输出模板
- `notes/l4-skills-vs-tools.md` — 概念对比表
- `notes/l4-skill-optimization-log.md` — darwin-skill 优化记录

## 运行

```bash
# 1. 接入 MCP server（先手动体验）
pip install mcp-server-filesystem
mkdir test_data
python -m mcp_server_filesystem ./test_data/

# 2. 用 MCP Inspector 可视化查看
npx @modelcontextprotocol/inspector
```

## B 线验证

- [ ] 一个 SKILL.md 被 agent 加载后，agent 的 system prompt 里多了什么？
- [ ] MCP 和普通 API 调用的区别是什么？为什么 agent 需要 MCP？

## C 线验证

- [ ] 用 darwin-skill 给自己写的 SKILL.md 打分，记录初始分数
- [ ] 根据评分报告改一版，再打分，记录涨幅
