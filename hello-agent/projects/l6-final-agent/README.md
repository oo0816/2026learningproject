# L6 · 最终 Agent 项目

## 选题

（A / B / C 选一个，删掉其他两个）

### 选项 A：膝关节导航术前报告 Agent
输入影像分析结果 → 自动生成结构化术前报告 → 医生审核确认

### 选项 B：简历智能匹配 Agent
输入简历 + 岗位 JD → 分析匹配度 → 给出改进建议

### 选项 C：个人知识助手 Agent
接笔记/文档 → RAG 检索 → 回答问题并引用来源

---

## 项目结构

```
l6-final-agent/
├── main.py          ← 入口 + agent loop
├── tools.py         ← 专用工具
├── memory.py        ← 记忆系统（从 L2 改造）
├── rag.py           ← RAG 检索（从 L2 改造）
├── permissions.py   ← 权限控制（从 L3 改造）
├── config.py        ← 配置管理
├── SKILL.md         ← 项目打包成可复用 skill
├── tests/
│   ├── test_agent.py
│   └── test_tools.py
└── eval_report.md   ← 20 个测试用例的评测报告
```

---

## 快速开始

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 配置 API key
$env:DEEPSEEK_API_KEY = "sk-你的key"

# 3. 运行
python main.py
```

---

## 权限边界

| 操作类型 | 示例 | 权限级别 | 说明 |
|---------|------|---------|------|
| 读操作 | 搜索、查文档 | 自动执行 | 无副作用 |
| （在此补充） | | | |
| 高危操作 | | 禁止 | |

---

## 已知限制

- （在此列出现有的限制和后续改进方向）
