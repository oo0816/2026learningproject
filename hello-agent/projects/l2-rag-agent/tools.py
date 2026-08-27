"""
L2 · 工具注册表 + 搜索工具
===============================

## 你要学会的东西

### 1. 工具是什么？
工具就是 agent 的手和脚。模型只能"想"，不能"做"——
- 不能查实时信息（训练数据有截止日期）
- 不能做精确计算（LLM 做数学是概率性的）
- 不能操作外部系统（发邮件、查数据库）

工具填补了这个 gap。

### 2. Function Calling 的原理
你不需要自己解析模型的输出来判断"它是不是想调工具"。
OpenAI 兼容的 API 在请求里带上 `tools` 参数，模型就会：
- 要么返回 `tool_calls`（它想调工具，包含工具名 + 参数 JSON）
- 要么返回普通的 `content`（它直接回答）

你的工作只是：
1. 定义工具的 schema（告诉模型：这个工具叫什么、干嘛的、参数是什么）
2. 收到 tool_calls 后执行真正的函数
3. 把执行结果以 `role: "tool"` 的格式塞回 messages

### 3. 工具的风险分级（L3 会正式实现）
不是所有工具都应该自动执行。一个简单的分级：
- safe：读操作，没副作用（搜索、查天气、计算）
- needs_approval：可能花钱或有风险（发邮件、删除文件）
- blocked：绝对不能自动执行（rm -rf、drop table）

### 4. 工具执行中的错误类型
你的 agent 需要正确处理这 4 种错误：
- 参数解析失败：模型生成的 JSON 格式不对
- 工具不存在：模型幻觉了一个工具名
- 工具执行超时：网络请求卡住了
- 工具返回空结果：搜到了 0 条

每种错误的处理方式不同，不能一概而论。

## 你的任务

在下面标记 TODO 的地方填写实现代码。参考你已经写过的 L1 main.py 中的工具部分。
"""

import json
import time

# ─────────────────────────────────────────────
# 任务 1：实现 web_search 工具
# ─────────────────────────────────────────────
# 目标：让 agent 能搜互联网。选一个免费方案：
#   A) pip install duckduckgo_search   （免费，无需 API key）
#   B) 用 Tavily Search API           （免费额度 1000次/月，需要注册）
#
# 函数签名已经写好，你来实现内部逻辑。
# 提示：搜索结果可能为空、可能超时、可能返回格式出乎意料——都要处理。

# 尝试导入搜索库，没装则降级
_SEARCH_AVAILABLE = False
try:
    from duckduckgo_search import DDGS
    _SEARCH_AVAILABLE = True
except ImportError:
    pass


def web_search(query: str, max_results: int = 3) -> str:
    """
    联网搜索，返回摘要和链接。

    参数:
        query: 搜索关键词
        max_results: 返回结果数量，默认 3 条

    返回:
        格式化的搜索结果字符串，或错误信息
    """
    if not _SEARCH_AVAILABLE:
        return ("搜索功能不可用：请先安装 duckduckgo_search\n"
                "运行：pip install duckduckgo_search")

    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))#uckduckgo_search 的作者在 DDGS 类里的 text() 方法里用了 yield，所以它天然就是懒的。不是他额外写的逻辑——是 Python 碰到 yield 就自动懒。
    except Exception as e:
        return f"搜索失败（网络错误或 API 限流）：{e}"

    # 空结果处理——告诉模型"没搜到"，而不是报错
    if not results:
        return f"搜索「{query}」未找到相关结果。建议：换一个更具体的关键词试试。"

    # 格式化结果：标题 + 摘要 + 链接
    lines = []
    for i, r in enumerate(results, 1):
        title = r.get("title", "无标题")
        href = r.get("href", "")
        body = r.get("body", "")[:200]  # 截断到 200 字，防止塞爆 messages
        lines.append(f"{i}. {title}\n   {body}\n   {href}")

    return "\n\n".join(lines)


# ─────────────────────────────────────────────
# 任务 2：从 L1 迁移基础工具
# ─────────────────────────────────────────────
# 把你 L1 main.py 中的 calculator 和 get_weather 复制过来。
# 想一想：L1 中你直接写在 main.py 里，L2 抽到 tools.py，
# 这样做的好处是什么？（提示：关注"注册表"的概念）

def calculator(expression: str) -> str:
    """
    安全计算数学表达式。

    安全策略：字符白名单 + 禁用 builtins。
    - 白名单：只允许数字、运算符、括号、小数点
    - {"__builtins__": {}}：封掉 __import__、open 等危险函数
    - 不是 100% 安全，但对学习场景足够了
    """
    allowed = set("0123456789+-*/().%^ ")
    if not all(c in allowed for c in expression):
        return "错误：表达式包含不允许的字符"
    try:
        result = eval(expression, {"__builtins__": {}}, {})
        return str(result)
    except Exception as e:
        return f"计算出错：{e}"


def get_weather(city: str) -> str:
    """
    获取城市天气（模拟数据）。

    L2 阶段用假数据，L5+ 可以替换为真实天气 API。
    这样做的好处：先验证 agent loop 能正常调用工具，
    后续只需要替换函数内部实现，不影响外部接口。
    """
    data = {
        "北京": "北京：5°C，晴朗，北风3级",
        "上海": "上海：12°C，多云，东风2级",
        "深圳": "深圳：20°C，小雨，南风1级",
        "杭州": "杭州：10°C，阴，微风",
    }
    return data.get(city, f"{city}：暂无天气数据（模拟服务）")


# ─────────────────────────────────────────────
# 任务 3：构建工具注册表
# ─────────────────────────────────────────────
# 注册表是一个 dict，key 是工具名，value 包含：
#   - name: 工具名
#   - func: 真正的 Python 函数
#   - risk_level: "safe" | "needs_approval" | "blocked"
#   - schema: OpenAI function calling 格式的 JSON schema
#
# 思考：为什么要把工具放在注册表里而不是散落各处？
# 提示：想象你要给项目加第 10 个工具时会发生什么。

# 工具注册表：名字 → {name, func, risk_level, schema}
# 所有工具统一注册在这里，加新工具只需在这里加一条
TOOL_REGISTRY = {
    "calculator": {
        "name": "calculator",
        "func": calculator,
        "risk_level": "safe",
        "schema": {
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
    },
    "get_weather": {
        "name": "get_weather",
        "func": get_weather,
        "risk_level": "safe",
        "schema": {
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
    },
    "web_search": {
        "name": "web_search",
        "func": web_search,
        "risk_level": "safe",
        "schema": {
            "type": "function",
            "function": {
                "name": "web_search",
                "description": "联网搜索最新信息。需要实时信息、新闻，或知识范围外的问题时使用。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "搜索关键词",
                        },
                        "max_results": {
                            "type": "integer",
                            "description": "返回结果数量，默认3",
                        },
                    },
                    "required": ["query"],
                },
            },
        },
    },
}


def get_tool_schemas() -> list[dict]:
    """返回所有工具的 OpenAI function calling schema 列表"""
    return [tool["schema"] for tool in TOOL_REGISTRY.values()]


def execute_tool(name: str, args: dict) -> str:
    """
    执行工具并返回结果——带完整的错误分类处理。

    错误处理优先级：
    1. 工具不存在 → 报错 + 列出可用工具名
    2. 工具被 blocked → 拒绝执行
    3. 工具 needs_approval → 打印警告（L3 升级为真正确认）
    4. 参数不匹配 → 捕获 TypeError，告诉模型正确格式
    5. 执行异常 → 返回异常类型和消息，模型看到后可以换种方式重试
    6. 空结果 → 检测并添加警告提示
    """
    # 1. 工具不存在
    if name not in TOOL_REGISTRY:
        available = ", ".join(TOOL_REGISTRY.keys())#用逗号加空格把它们粘成一句话
        return f"[工具错误] 未知工具 '{name}'。可用工具：{available}"

    tool = TOOL_REGISTRY[name]

    # 2. 被禁止的工具
    if tool["risk_level"] == "blocked":
        return f"[权限拒绝] 工具 '{name}' 已被禁止执行，请换一种方式。"

    # 3. 需要确认的工具
    if tool["risk_level"] == "needs_approval":
        # L2 简化：打一行警告，自动放行
        print(f"  ⚠️ 高危操作警告：正在执行 '{name}'（L3 将实现人工确认闸门）")

    # 4. 执行工具
    try:
        start = time.time()
        result = tool["func"](**args)#** 把字典拆成 key=value 传参
        elapsed = time.time() - start
    except TypeError as e:
        # 参数不对——告诉模型正确的格式
        params = tool["schema"]["function"]["parameters"]
        return f"[工具错误] '{name}' 参数不匹配：{e}\n期望参数格式：{params}"
    except Exception as e:
        # 其他异常
        return f"[工具错误] '{name}' 执行异常：{type(e).__name__}: {e}"

    # 5. 超时检测
    if elapsed > 10:
        return f"[工具警告] '{name}' 耗时 {elapsed:.1f}s，结果可能不完整。\n\n{result}"

    # 6. 空结果检测
    if result is None or (isinstance(result, str) and result.strip() == ""):
        return f"[工具警告] '{name}' 返回了空结果，可能需要换一种查询方式。"

    return str(result)


# ══════════════════════════════════════════════════════════════
# 常见坑（提前看，少走弯路）
# ══════════════════════════════════════════════════════════════
#
# 坑 1：schema 写错了，模型不调工具
#   → 检查 parameters 的 type 必须是 "object"，required 字段要和 properties 对应。
#   → 用英文写 description，大多数模型对英文的理解比中文好。
#
# 坑 2：工具返回结果太长，塞回 messages 后下一轮模型懵了
#   → 搜索结果截断到 200-300 字足够。
#   → 工具返回的不是给用户看的，是给模型看的——信息密度 > 完整度。
#
# 坑 3：搜索工具返回了不相关的结果
#   → 这是正常的，模型应该能判断相关性并告诉用户"搜到的结果不太对"。
#   → 不要在工具层做相关性过滤——那是模型的职责。
#
# 坑 4：忘记 import 搜索库就写代码
#   → 先 pip install，再 import。用 try/except ImportError 做降级处理。
#   → 这样即使没装库，agent 也能跑（只是搜索功能不可用）。
