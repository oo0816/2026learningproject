"""
L1 · 最小 Agent Loop
一个不到 150 行的 agent：能调用工具、能根据结果继续决策、能自己停下来。
"""

import os
import sys
import json
import time
from openai import OpenAI

sys.stdout.reconfigure(encoding="utf-8")
#Windows 终端默认编码是 GBK，中文可能乱码。这行强制改成 UTF-8，让你的 agent 正常输出中文。

# ── 1. 连接模型 ──
# 先取环境变量，取不到则从 Windows 注册表读用户变量
_api_key = os.environ.get("DEEPSEEK_API_KEY")
if not _api_key:
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as key:
            _api_key, _ = winreg.QueryValueEx(key, "DEEPSEEK_API_KEY")
    except FileNotFoundError:
        pass
#这是 Windows 特有的技巧。如果你在"系统属性 → 环境变量"里设了永久变量，os.environ 有时候拿不到（和终端启动方式有关），但注册表里一定有。这个兜底防止"明明设了变量却读不到"的情况。
if not _api_key:
    print("错误：未找到 DEEPSEEK_API_KEY")
    print("请运行：$env:DEEPSEEK_API_KEY = 'sk-你的key'")
    exit(1)

client = OpenAI(
    api_key=_api_key,
    base_url="https://api.deepseek.com",
)

MODEL = "deepseek-chat"

# ── 2. 工具注册表 ──
def calculator(expression: str) -> str:
    """安全计算数学表达式"""
    try:
        allowed = set("0123456789+-*/().%^ ")
        if not all(c in allowed for c in expression):
            return "错误：表达式包含不允许的字符"
        result = eval(expression, {"__builtins__": {}}, {})
        return str(result)
    except Exception as e:
        return f"计算出错：{e}"


def get_weather(city: str) -> str:
    """获取城市天气（模拟数据）"""
    data = {
        "北京": "北京：5°C，晴朗，北风3级",
        "上海": "上海：12°C，多云，东风2级",
        "深圳": "深圳：20°C，小雨，南风1级",
        "杭州": "杭州：10°C，阴，微风",
    }
    return data.get(city, f"{city}：暂无天气数据（模拟服务）")


# 注册表：名字 → 真正的函数
TOOLS_MAP = {
    "calculator": calculator,
    "get_weather": get_weather,
}

# 工具的 schema 描述——告诉模型每个工具是干嘛的、参数怎么填
TOOLS_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "calculator",
            "description": "计算数学表达式。支持加减乘除、括号、幂运算。",
            "parameters": {
                "type": "object",
                "properties": {
                    "expression": {
                        "type": "string",
                        "description": "数学表达式，如 '(3+5)*2-4/2'",
                    }
                },
                "required": ["expression"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "获取指定城市的天气信息",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {
                        "type": "string",
                        "description": "城市名称，如'北京'",
                    }
                },
                "required": ["city"],
            },
        },
    },
]

# ── 3. Agent Loop ──
MAX_STEPS = 10       # 最多调 10 轮
TIMEOUT = 30          # 30 秒超时

def run_agent(user_query: str) -> str:
    """最小 agent：问模型 → 执行工具 → 结果喂回 → 循环，直到模型说停"""
    messages = [
        {"role": "system", "content": "你是一个有用的助手。当需要计算或查询天气时，使用提供的工具。不需要工具就直接回答。"},
        {"role": "user", "content": user_query},
    ]

    start_time = time.time()
    tool_call_count = 0

    for step in range(MAX_STEPS):
        # 超时检查
        if time.time() - start_time > TIMEOUT:
            return f"[超时] agent 运行超过 {TIMEOUT} 秒，强制终止"

        # 问模型
        response = client.chat.completions.create(
            model=MODEL,           # 用哪个模型，这里是 deepseek-chat
            messages=messages,     # 把整个对话历史发给它
            tools=TOOLS_SCHEMA,    # 告诉它"你有这些工具可以用"
        )

        msg = response.choices[0].message
#response                          ← 整个响应对象
#  └── choices                     ← 模型的回复列表（通常只有 1 个）
#        └── [0]                   ← 取第一个（也是唯一一个）回复
#              └── message         ← 回复的消息体
#                    ├── content   ← 模型直接说的话（"北京今天5°C..."）
#                    └── tool_calls ← 模型想调的工具（如果有的话）

        # 情况 A：模型想调工具
        if msg.tool_calls:
            # 先把模型的要求记到对话里
            messages.append(msg)

            for tc in msg.tool_calls:
                tool_name = tc.function.name
                tool_args = json.loads(tc.function.arguments)

                # 执行工具
                if tool_name in TOOLS_MAP:
                    result = TOOLS_MAP[tool_name](**tool_args)# 字典拆包
                    tool_call_count += 1
                else:
                    result = f"错误：未知工具 {tool_name}"

                # 把执行结果塞回对话
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": result,
                })

            continue  # 回到循环，再问模型

        # 情况 B：模型直接回答了，没有调工具
        elapsed = time.time() - start_time
        return (
            f"{msg.content}\n\n"
            f"———\n"
            f"调用工具 {tool_call_count} 次 | 耗时 {elapsed:.1f}s | 步数 {step + 1}"
        )

    return "[超步] agent 达到最大步数上限，强制终止"


# ── 4. CLI 入口 ──interact
if __name__ == "__main__":
    print("=" * 50)
    print("L1 · 最小 Agent Loop")
    print("输入 quit 退出")
    print("=" * 50)

    while True:
        query = input("\n> ").strip()#strip() 去掉首尾空格
        if query.lower() in ("quit", "exit", "q"):
            break
        if not query:
            continue
        print()
        print(run_agent(query))
