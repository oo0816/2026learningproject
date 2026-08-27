"""
L2 · 工具调用 + 记忆 + RAG Agent
==================================

## 在 L1 的基础上，L2 升级了什么？

| 维度 | L1 | L2 |
|------|----|----|
| 工具数量 | 2（calculator, weather） | 3+（+web_search） |
| 工具注册 | 散落在 main.py | 注册表（tools.py） |
| 记忆 | 无（只有 messages） | 三层（messages + session + long_term） |
| 知识检索 | 无 | RAG（本地 embedding + 余弦相似度） |
| 错误处理 | 简单的 try/except | 错误分类（空结果/超时/格式错误/未知工具） |
| System prompt | 写死的字符串 | 动态构建（注入记忆 + RAG 状态） |

## Agent Loop 回顾

你在 L1 写的 agent loop 是这样的：

```
for step in range(MAX_STEPS):
    response = client.chat.completions.create(messages, tools)
    if response 有 tool_calls:
        执行工具 → 结果塞回 messages → continue
    else:
        return response.content  # 模型直接回答了
```

这个结构本身已经很好了。L2 不做结构性改变，只做增量：

1. **调用模型前**：动态构建 system prompt（注入记忆），先做 RAG 检索把结果塞进 messages
2. **执行工具时**：用 tools.py 的 execute_tool() 替代原来的 TOOLS_MAP[name](**args)
3. **收到回答后**：从回答中提取 [[REMEMBER]] 指令，清理后展示给用户
4. **上下文过长时**：调用 manage_context_window 裁剪

## 关键设计问题

### Q: agent loop 是 while True 还是 for 循环？
A: L1/L2 用 for 循环（有最大步数限制）。while True 需要自己管理退出条件，容易忘。

### Q: 如果模型没调工具直接回答了，代码怎么做？
A: 检查 msg.tool_calls 是否为空/None。为空就 return。这是正常情况——不是每次都要调工具。

### Q: 如果工具返回错误，agent 怎么处理？
A: 把错误信息以 tool result 的形式返回给模型。模型看到错误后会尝试：
   - 换一种方式调用工具（修正参数）
   - 告诉用户"我试了但失败了，原因是..."
   - 换另一个工具尝试
   关键是：不要把错误吞掉，让它可见。
"""

import os
import sys
import json
import time
import argparse
import re
from pathlib import Path
from openai import OpenAI

sys.stdout.reconfigure(encoding="utf-8")

# ── 内部模块（你写的 tools.py / memory.py / rag.py）──
from tools import TOOL_REGISTRY, get_tool_schemas, execute_tool
from memory import SessionMemory, LongTermMemory, manage_context_window
from rag import get_rag

# ══════════════════════════════════════════════════════════════
# 任务 1：模型连接（从 L1 迁移）
# ══════════════════════════════════════════════════════════════
# 把 L1 main.py 中的 API key 解析逻辑搬过来。
# 从环境变量读取 DEEPSEEK_API_KEY，取不到则读 Windows 注册表。

_api_key = os.environ.get("DEEPSEEK_API_KEY")
if not _api_key:
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as key:
            _api_key, _ = winreg.QueryValueEx(key, "DEEPSEEK_API_KEY")
    except FileNotFoundError:
        pass
if not _api_key:
    print("错误：未找到 DEEPSEEK_API_KEY")
    print("请运行：$env:DEEPSEEK_API_KEY = 'sk-你的key'")
    exit(1)

client = OpenAI(
    api_key=_api_key,
    base_url="https://api.deepseek.com",
)
MODEL = "deepseek-chat"

# ══════════════════════════════════════════════════════════════
# 任务 2：动态 System Prompt
# ══════════════════════════════════════════════════════════════
# L1 的 system prompt 是写死的。L2 需要动态注入：
# - 会话记忆（session_memory.get_all()）
# - 长期记忆（long_term_memory.get_all()）
# - RAG 状态（告诉模型知识库里有多少文档可用）
# - [[REMEMBER]] 指令的使用说明

def build_system_prompt() -> str:
    """
    动态构建 system prompt。

    设计原则：
    - 基础指令写死（工具使用指南、行为规范）
    - 动态信息注入（记忆内容、知识库状态）
    - 不要把整个长期记忆全塞进去——只注入"最近 5-10 条"或"相关的几条"

    思考：如果长期记忆有 500 条，全注入 system prompt 会怎样？
    → system prompt 就几千 token 了，留给对话的空间变小，贵且慢。
    """
    parts = [
        "你是一个有用的智能助手，可以调用工具、使用记忆和检索知识库。",
        "",
        "## 工具使用",
        "当需要实时信息、精确计算或外部数据时，调用相应工具。",
        "工具结果只对模型可见，请整理后以自然语言回复用户。",
        "",
        "## 记忆指令",
        "当用户表达了需要长期记住的信息时，在回复中嵌入：",
        "[[REMEMBER: 键名]] 具体内容 [[/REMEMBER]]",
        "",
        "## 引用要求",
        "回答引用知识库内容时，标注来源文件名，如（来源：readme.txt）。",
        "如果知识库没有相关内容，就用你自己的知识回答。",
    ]
    session_summary = session_memory.get_all()
    if session_summary:
        parts += ["", session_summary]
    long_term_summary = long_term_memory.get_all()
    if long_term_summary:
        parts += ["", long_term_summary]
    parts += ["", f"## 知识库状态\n{rag.stats()}"]
    return "\n".join(parts)


# ══════════════════════════════════════════════════════════════
# 任务 3：增强版 Agent Loop
# ══════════════════════════════════════════════════════════════

# 常量定义
MAX_STEPS = 10        # 最多调用 10 轮
TIMEOUT = 60           # 60 秒超时（L2 放宽，因为搜索和 RAG 可能慢）
MAX_CONTEXT_TURNS = 10  # 保留最近 10 轮对话，超出则裁剪

# 全局实例（模块加载时初始化）
session_memory = SessionMemory()
long_term_memory = LongTermMemory()
rag = get_rag()


def run_agent(user_query: str, verbose: bool = False) -> str:
    """
    增强版 agent loop。

    和 L1 的区别：
    1. 先做 RAG 检索，把相关文档注入 messages
    2. 用 build_system_prompt() 动态构建 system prompt
    3. 工具调用走 execute_tool() 而不是直接调函数
    4. 回答后提取 [[REMEMBER]] 指令
    5. 自动记录有工具调用的交互到长期记忆
    6. 消息过长时自动裁剪

    参数:
        user_query: 用户输入
        verbose: 是否打印详细的工具调用过程

    返回:
        agent 的最终回答（含统计信息 footer）
    """
    # Step 1: RAG 检索（如果知识库不为空）
    rag_context = rag.search_formatted(user_query)

    # Step 2: 构建初始 messages
    system_prompt = build_system_prompt()
    messages = [{"role": "system", "content": system_prompt}]
    if rag_context:
        messages.append({"role": "system", "content": rag_context})
    messages.append({"role": "user", "content": user_query})

    # Step 3: Agent loop
    start_time = time.time()
    tool_call_count = 0
    error_count = 0

    for step in range(MAX_STEPS):
        if time.time() - start_time > TIMEOUT:
            return f"[超时] agent 运行超过 {TIMEOUT} 秒，强制终止"

        messages = manage_context_window(messages, MAX_CONTEXT_TURNS)

        if verbose:
            print(f"  [step {step + 1}] 调用模型…")

        response = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            tools=get_tool_schemas(),
        )
        msg = response.choices[0].message

        # 模型想调工具
        if msg.tool_calls:
            messages.append(msg)
            for tc in msg.tool_calls:
                tool_name = tc.function.name
                try:
                    tool_args = json.loads(tc.function.arguments)
                except json.JSONDecodeError:
                    tool_args = {}
                    error_count += 1
                result = execute_tool(tool_name, tool_args)
                if verbose:
                    print(f"  [工具] {tool_name}{tool_args}")
                if result.startswith(("[工具错误]", "[权限拒绝]")):
                    error_count += 1
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": result,
                })
                tool_call_count += 1
            continue

        # 模型直接回答了
        content = msg.content or ""
        session_memory.update_from_message(content)
        if tool_call_count > 0:
            long_term_memory.add(
                f"用户询问「{user_query[:50]}」，共调用 {tool_call_count} 个工具完成回答",
                tags=["工具调用"],
                source="agent",
            )
        clean_content = re.sub(
            r"\[\[REMEMBER:\s*.+?\]\].*?\[\[/REMEMBER\]\]",
            "",
            content,
            flags=re.DOTALL,
        ).strip()

        elapsed = time.time() - start_time
        footer = (
            f"\n\n———\n"
            f"调用工具 {tool_call_count} 次 | 报错 {error_count} 次 | "
            f"耗时 {elapsed:.1f}s | 步数 {step + 1}"
        )
        return clean_content + footer

    # Step 4: 超步处理
    return f"[超步] agent 达到最大步数上限（{MAX_STEPS}），强制终止"


# ══════════════════════════════════════════════════════════════
# 任务 4：CLI 入口
# ══════════════════════════════════════════════════════════════
# 支持三种运行模式：
# 1. 交互模式：python main.py
# 2. 单次查询：python main.py "今天天气怎么样"
# 3. 加载文档：python main.py --load ./docs/


def load_docs(path: str, glob_pattern: str):
    """加载文件或目录到 RAG 知识库"""
    p = Path(path)
    if p.is_dir():
        files = sorted(p.rglob(glob_pattern))
    elif p.is_file():
        files = [p]
    else:
        print(f"路径不存在：{path}")
        return
    total = 0
    for f in files:
        try:
            n = rag.load_file(str(f))
        except Exception as e:
            print(f"  ✗ {f.name}: {e}")
            continue
        total += n
        print(f"  ✓ {f.name}: {n} 个分块")
    print(f"共加载 {len(files)} 个文件，{total} 个分块")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="L2 · 工具调用+记忆+RAG Agent")
    parser.add_argument("query", nargs="?", help="单次查询（省略则进入交互模式）")
    parser.add_argument("--load", type=str, help="加载文档文件或目录到 RAG 知识库")
    parser.add_argument("--load-glob", type=str, default="*.txt", help="加载文档时的文件匹配模式")
    parser.add_argument("--verbose", "-v", action="store_true", help="显示详细的工具调用过程")
    parser.add_argument("--rag-stats", action="store_true", help="显示 RAG 索引状态后退出")
    parser.add_argument("--memory", action="store_true", help="显示长期记忆后退出")
    args = parser.parse_args()

    if args.rag_stats:
        print(rag.stats())
        sys.exit(0)

    if args.memory:
        entries = long_term_memory.entries
        if not entries:
            print("（暂无长期记忆）")
        else:
            for e in long_term_memory.get_recent(20):
                print(f"[{e['id']}] {e['content']}（{e['created_at']}）")
        sys.exit(0)

    if args.load:
        load_docs(args.load, args.load_glob)

    if args.query:
        print(run_agent(args.query, verbose=args.verbose))
        sys.exit(0)

    print("=" * 55)
    print("L2 · 工具调用 + 记忆 + RAG Agent")
    print("特殊命令：/memory 查看记忆 | /rag 查看知识库 | quit 退出")
    print("=" * 55)

    while True:
        try:
            query = input("\n> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if query.lower() in ("quit", "exit", "q"):
            break
        if not query:
            continue
        if query == "/memory":
            entries = long_term_memory.entries
            if not entries:
                print("（暂无长期记忆）")
            else:
                for e in long_term_memory.get_recent(20):
                    print(f"[{e['id']}] {e['content']}")
            continue
        if query == "/rag":
            print(rag.stats())
            continue
        print()
        print(run_agent(query, verbose=args.verbose))


# ══════════════════════════════════════════════════════════════
# 常见坑
# ══════════════════════════════════════════════════════════════
#
# 坑 1：import 了 tools.py 但 tools.py 里的函数还是空的
#   → 先写完 tools.py / memory.py / rag.py 再写 main.py。
#   → 建议顺序：tools.py → memory.py → rag.py → main.py
#
# 坑 2：RAG 检索没找到结果 ≠ 报错
#   → 没找到是正常的，agent 应该用自己的知识回答。
#   → 不要因为 RAG 没结果就不回答问题。
#
# 坑 3：[[REMEMBER]] 标签被展示给用户
#   → 展示前用 re.sub 把标签和内容一起删掉。
#   → 正则：r"\[\[REMEMBER:\s*.+?\]\].*?\[\[/REMEMBER\]\]"
#
# 坑 4：长期记忆和会话记忆是两套独立的系统
#   → 不要混用！session_memory 管当前会话，long_term_memory 管跨会话。
#   → 同一个 key 不需要在两个地方各存一份。
#
# 坑 5：超时设置太短
#   → L1 的 30 秒可能不够。搜索 API 有时要 3-5 秒，
#     embedding 模型第一次加载要几十秒。L2 建议 60 秒。
