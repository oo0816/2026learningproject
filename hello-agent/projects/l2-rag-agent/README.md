# L2 · 工具调用 + 记忆 + RAG Agent

在 L1 最小 Agent Loop 上升级：搜索工具 / 三层记忆 / RAG 检索 / 错误分类处理。

## 学习目标

写完这个项目后，你应该能回答：
1. 对话上下文（messages）和长期记忆（JSON 文件）的实现方式有什么本质不同？
2. 向量检索返回了不相关的结果，agent 应该怎么处理？
3. 工具出错时，agent 怎么优雅地恢复而不是崩溃？

## 写代码顺序（重要！）

```
1. tools.py   → 工具注册表 + web_search
2. memory.py  → SessionMemory + LongTermMemory + manage_context_window
3. rag.py     → split_text + SimpleRAG（先写代码，可以不装模型先跑通结构）
4. main.py    → 组装上面三个模块，写 agent loop
```

每个文件开头有详细的原理说明，读完再写。

## 依赖

```bash
pip install openai duckduckgo_search sentence-transformers
```

如果 sentence-transformers 下载慢，可以先跳过——rag.py 的代码结构可以先写完，最后再装模型跑通。

## 配置

```bash
$env:DEEPSEEK_API_KEY = "sk-你的key"
```

## 运行

```bash
# 加载文档（可选）
python main.py --load ./docs/

# 交互模式
python main.py

# 单次查询
python main.py "今天北京天气怎么样"

# 查看 RAG 状态
python main.py --rag-stats

# 查看长期记忆
python main.py --memory
```

## 验证清单

完成后对照 README.md 的 L2 章节逐项打勾：
- [ ] main.py 可运行，能交互对话
- [ ] web_search 工具能正常搜索并返回结果
- [ ] 记忆能跨轮次保留（在同一次会话中）
- [ ] 长期记忆写入 JSON 文件，重启后还在
- [ ] RAG 能加载文档、检索相关内容
- [ ] 工具出错时 agent 不会崩溃

## 和 L1 的对比

| 维度 | L1 | L2 |
|------|----|----|
| 文件数 | 1（main.py） | 4（main + tools + memory + rag） |
| 工具 | 2 个 | 3+ 个 |
| 工具管理 | 散落在 main.py | 注册表模式 |
| 记忆 | 无（只有 messages） | 三层记忆 |
| 外部知识 | 无 | RAG |
| 错误处理 | try/except | 分类处理 |
| 代码行数 | ~150 | ~400（你的实现） |
