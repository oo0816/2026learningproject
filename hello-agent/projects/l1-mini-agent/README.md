# L1 · 最小 Agent Loop

不到 150 行的 agent：能调工具、能根据结果继续决策、能自己停下来。

## 依赖

```bash
pip install openai
```

## 配置

```bash
$env:DEEPSEEK_API_KEY = "sk-你的key"
```

Key 来源：[DeepSeek API Keys](https://platform.deepseek.com/api_keys)

## 运行

```bash
python main.py
```

交互模式，输入问题即可：

```
> 1加2乘以3等于多少？用计算器算一下
```

输入 `quit` 退出。

## 工具

| 工具 | 说明 |
|------|------|
| `calculator` | 安全计算数学表达式 |
| `get_weather` | 查询城市天气（模拟数据） |

## 架构

```
用户输入 → 模型（DeepSeek）→ 需要工具？→ 执行工具 → 结果喂回模型 → 循环
              │                                        ↑
              └──→ 不需要工具 → 直接返回 ──────────────┘
```

最多 10 轮，30 秒超时。

## 测试

```bash
python test_agent.py
```

3 个用例覆盖三条路径：单工具、多工具并行、零工具直接回答。
