"""
L5 · 多 Agent 协作
==================

## 核心概念：多 Agent 不是魔法

多 Agent 本质上就是"多个 agent loop 在跑，通过某种方式传递信息"。
它不是让一个 agent 更聪明，而是让多个 agent 各司其职。

### 为什么需要多 Agent？

单 Agent 的问题：
- 一个 system prompt 要塞下所有指令 → 越来越长、越来越模糊
- 一个 agent 既要做研究又要写报告 → 上下文切换成本高
- 没有制衡机制 → agent 可能一条路走到黑

多 Agent 的优势：
- 每个 agent 职责单一，system prompt 短且精准
- 可以并行工作（research agent 搜资料的同时，writer agent 开始写大纲）
- 有检查机制（reviewer agent 审核 writer 的输出）

### 三种经典协作模式

```
模式 1：Supervisor（主管模式）—— L5 用这个
┌─────────────┐
│  Supervisor │ ← 分配任务、汇总结果
└──┬──┬──┬───┘
   │  │  │
   ▼  ▼  ▼
  R  W  Rv     ← Researcher / Writer / Reviewer

模式 2：Pipeline（流水线模式）
Research → Write → Review → （不通过则循环）

模式 3：Peer-to-Peer（对等协商）
Agent A ←→ Agent B  各自有专长，互相提问
```

### Agent 之间怎么通信？

三种方式，由简到繁：
1. **共享消息队列**：所有 agent 往同一个 messages list 写
2. **结构化交接**：上一个 agent 的输出是下一个的输入（Pipeline 模式）← L5 用这个
3. **消息总线**：每个 agent 订阅自己关心的消息（复杂但灵活）

## 本文件实现了什么

- **模型连接**：惰性加载（import 本文件不需要 API key），沿用 L1/L2/L3 的 DeepSeek 配置
- **BaseAgent**：任意角色 agent 的基类，带 独立 messages + 可选工具 + tool-call 循环
- **Researcher / Writer / Reviewer**：三个具体角色
- **Supervisor**：编排 research → write → review（循环）+ 护栏（最大轮次 / 总超时）+ 人工确认闸门
- **TraceLogger**：全链路调用追踪
- **依赖注入**：`model_fn` 可换成假模型，离线测试 / 评测不烧 token

用法：`python main.py`
"""

import os
import sys
import json
import time

sys.stdout.reconfigure(encoding="utf-8")


# ══════════════════════════════════════════════════════════════
# 模块 0：模型连接（惰性加载，import 本文件不解析 key）
# ══════════════════════════════════════════════════════════════
# 照抄 L3 的做法：把"配置加载"和"业务逻辑"解耦。
# 好处：离线单元测试 / 用假模型评测时，不需要 API key 也能 import main。

MODEL = "deepseek-chat"
BASE_URL = "https://api.deepseek.com"

# 真实模型只初始化一次（懒加载缓存）
_client_singleton = None


def _resolve_api_key():
    """解析 API key：先看环境变量，取不到再从 Windows 注册表读用户变量。"""
    key = os.environ.get("DEEPSEEK_API_KEY")
    if key:
        return key
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as k:
            key, _ = winreg.QueryValueEx(k, "DEEPSEEK_API_KEY")
        return key
    except Exception:
        return None


def create_client():
    """创建 OpenAI 兼容客户端；没配 key 时抛错（由调用方决定怎么处理）。"""
    global _client_singleton
    if _client_singleton is not None:
        return _client_singleton
    key = _resolve_api_key()
    if not key:
        raise RuntimeError(
            "未找到 DEEPSEEK_API_KEY\n请运行：$env:DEEPSEEK_API_KEY = 'sk-你的key'"
        )
    from openai import OpenAI  # 惰性 import：没装 openai 库时其它功能仍可用
    _client_singleton = OpenAI(api_key=key, base_url=BASE_URL)
    return _client_singleton


# ══════════════════════════════════════════════════════════════
# 模块 1：联网搜索工具（给 Researcher 用，可选）
# ══════════════════════════════════════════════════════════════

try:
    from duckduckgo_search import DDGS
    _SEARCH_AVAILABLE = True
except ImportError:
    _SEARCH_AVAILABLE = False


def web_search(query: str, max_results: int = 3) -> str:
    """联网搜索（给 Researcher）。结果截断，防止塞爆上下文。"""
    if not _SEARCH_AVAILABLE:
        return ("[工具提示] 搜索功能不可用（未安装 duckduckgo_search）。"
                "请基于你的已有知识继续，不要假装搜到了。")
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
    except Exception as e:
        return f"[工具提示] 搜索失败（网络或限流）：{e}"
    if not results:
        return f"[工具提示] 搜索「{query}」无结果，请基于知识继续。"
    lines = []
    for i, r in enumerate(results, 1):
        title = r.get("title", "无标题")
        href = r.get("href", "")
        body = r.get("body", "")[:150]
        lines.append(f"{i}. {title}\n   {body}\n   {href}")
    return "\n\n".join(lines)


# ══════════════════════════════════════════════════════════════
# 模块 2：TraceLogger — 调用链追踪
# ══════════════════════════════════════════════════════════════

class TraceLogger:
    """
    调用链追踪：可以看到每个 agent 在什么时间做了什么。

    trace 的每一项：
    {
        "timestamp": "14:30:01.234",
        "agent": "Researcher",
        "action": "tool_call",
        "detail": "web_search('量子计算最新进展')",
        "result_preview": "找到 3 条结果...",
        "elapsed_ms": 2340
    }
    """

    def __init__(self):
        self.traces = []

    def log(self, agent: str, action: str, detail: str,
            result_preview: str = "", elapsed_ms: float = 0):
        now = time.time()
        ms = int((now - int(now)) * 1000)
        timestamp = time.strftime("%H:%M:%S") + f".{ms:03d}"
        self.traces.append({
            "timestamp": timestamp,
            "agent": agent,
            "action": action,
            "detail": detail,
            "result_preview": result_preview[:120],  # 只存预览，防 trace 爆掉
            "elapsed_ms": round(elapsed_ms, 1),
        })

    def report(self) -> str:
        """生成人类可读的 trace 报告"""
        if not self.traces:
            return "（无 trace）"
        lines = ["── Trace ──"]
        for t in self.traces:
            lines.append(
                f"[{t['timestamp']}] {t['agent']:<11} | {t['action']:<18} | "
                f"{t['detail']}"
            )
            if t["result_preview"]:
                lines.append(f"                └─ 结果: {t['result_preview']}")
        return "\n".join(lines)


# ══════════════════════════════════════════════════════════════
# 模块 3：BaseAgent — 任意角色 agent 的基类
# ══════════════════════════════════════════════════════════════

class BaseAgent:
    """
    所有 agent 的基类。

    每个 agent 有：
    - 名字（用于日志和 trace）
    - 角色描述（注入 system prompt）
    - 可用工具（不是所有 agent 都需要所有工具）
    - 独立的 messages 历史（每个 think 从干净状态开始，不跨 agent 串）

    关键设计：
    - model_fn 是可注入的"模型函数"。默认走真实 DeepSeek；
      评测时可以换成假函数，让 agent 离线跑确定性的脚本。
    - tools 是 {name: {"func": ..., "schema": {...}}} 的 dict；
      OpenAI schema 形式：{"type": "function", "function": {...}}
    """

    MAX_TOOL_STEPS = 6  # 单个 think 内最多允许几次"思考→调用工具→看结果"的循环

    def __init__(self, name: str, role: str, tools: list = None,
                 model_fn=None, tracer: TraceLogger = None):
        self.name = name
        self.role = role
        self.tools = tools or {}
        self.model_fn = model_fn  # None → 用真实 DeepSeek
        self.tracer = tracer      # None → 不记 trace（纯离线跑）
        self.total_tokens = 0     # 本 agent 累计消耗的 token（可跨 think 累加）
        self.llm_calls = 0

    # ── 给 Agent 的对外接口 ────────────────────────────────
    def think(self, task: str, context: str = "") -> str:
        """
        Agent 执行一次"思考→行动→(必要时反复)→ 给出文本结论"。

        参数:
            task: 当前要完成的任务描述
            context: 上下文信息（如 Researcher 的输出给 Writer）

        返回: agent 的输出文本（纯文本；需要结构化时由调用方解析）
        """
        # 每个 think 独立构建消息，避免把上次对话残留带进来
        user_prompt = f"{context}\n\n【任务】\n{task}" if context else task
        messages = [
            {"role": "system", "content": self.role},
            {"role": "user", "content": user_prompt},
        ]

        try:
            for _ in range(self.MAX_TOOL_STEPS):
                # 1. 调用模型
                call_start = time.time()
                resp = self._call(messages)
                call_ms = (time.time() - call_start) * 1000

                tool_calls = resp.get("tool_calls") or []
                content = resp.get("content", "")

                # 2. 没要工具 → 直接回答，结束
                if not tool_calls:
                    self._log("answer", f"给出回答（{len(content)} 字）",
                              content[:120], call_ms)
                    return content

                # 3. 要了工具 → 把 assistant 的请求记进对话，然后逐个执行
                self._log("tool_request",
                          f"请求 {len(tool_calls)} 个工具调用",
                          f"tools={[tc['name'] for tc in tool_calls]}", call_ms)
                messages.append({
                    "role": "assistant",
                    "content": content or None,
                    "tool_calls": [
                        {"id": tc["id"], "type": "function",
                         "function": {"name": tc["name"],
                                      "arguments": tc["arguments"]}}
                        for tc in tool_calls
                    ],
                })

                for tc in tool_calls:
                    tool_start = time.time()
                    result = self._run_tool(tc["name"], tc["arguments"])
                    tool_ms = (time.time() - tool_start) * 1000
                    self._log("tool_call", f"{tc['name']}({tc['arguments'][:80]})",
                              result[:120], tool_ms)
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc["id"],
                        "content": result,
                    })
                # 回到循环顶部，把工具结果再喂给模型
        except Exception as e:
            # API / key / 网络错误 → 不静默吞，作为输出返回，让上层看见
            return f"[模型调用出错] {type(e).__name__}: {e}"

        return "[超步] 工具调用循环超过上限，已终止。"

    # ── 内部实现 ──────────────────────────────────────────
    def _call(self, messages) -> dict:
        """发一次模型调用，返回规范化 dict：{content, tool_calls, tokens}"""
        self.llm_calls += 1

        # 收集本 agent 工具对应的 OpenAI schema（发送给模型时要用）
        schemas = [self.tools[name]["schema"] for name in self.tools]

        if self.model_fn is not None:
            resp = self.model_fn(messages, schemas)
        else:
            client = create_client()
            kwargs = {"model": MODEL, "messages": messages}
            if schemas:
                kwargs["tools"] = schemas
            raw = client.chat.completions.create(**kwargs)
            msg = raw.choices[0].message
            tool_calls = []
            for tc in (msg.tool_calls or []):
                tool_calls.append({
                    "id": tc.id,
                    "name": tc.function.name,
                    "arguments": tc.function.arguments or "{}",
                })
            usage = getattr(raw, "usage", None)
            tokens = getattr(usage, "total_tokens", 0) or 0
            resp = {"content": msg.content or "", "tool_calls": tool_calls,
                    "tokens": tokens}

        self.total_tokens += resp.get("tokens", 0)
        return resp

    def _run_tool(self, name: str, arguments: str) -> str:
        """执行一个工具，返回字符串结果。任何异常都变成可读的文本。"""
        if name not in self.tools:
            return f"[工具错误] 未知工具：{name}"
        try:
            args = json.loads(arguments) if arguments else {}
            if not isinstance(args, dict):
                return f"[工具错误] 参数不是对象：{arguments[:120]}"
            raw = self.tools[name]["func"](**args)
        except Exception as e:
            return f"[工具错误] {type(e).__name__}: {e}"
        return str(raw)[:2000]

    def _log(self, action: str, detail: str, preview: str = "", ms: float = 0):
        """有 tracer 时才记 trace（离线跑可不开）"""
        if self.tracer is not None:
            self.tracer.log(self.name, action, detail, preview, ms)


# ══════════════════════════════════════════════════════════════
# 任务 1：定义 Agent 角色（继承 BaseAgent，只改 system prompt + 工具）
# ══════════════════════════════════════════════════════════════

class Researcher(BaseAgent):
    """研究员：搜索 + 汇总资料。带 web_search 工具。"""
    ROLE = (
        "你是 Researcher（研究员）。你的任务：针对用户的主题做资料收集与要点梳理，"
        "输出一份「研究摘要」。\n"
        "要求：\n"
        "1. 可以调用 web_search 工具查证（最多 2 次搜索），拿不到就用你的知识补充并标注「知识补充」；\n"
        "2. 摘要分条列出：核心事实、关键角度、可用的数据/例子；\n"
        "3. 只输出研究摘要文本，不要写最终报告。"
    )

    def __init__(self, **kw):
        super().__init__("Researcher", self.ROLE,
                         tools={"web_search": {
                             "func": web_search,
                             "schema": {
                                 "type": "function",
                                 "function": {
                                     "name": "web_search",
                                     "description": "联网搜索网页资料，返回标题+摘要+链接。用于查证事实、找最新信息。",
                                     "parameters": {
                                         "type": "object",
                                         "properties": {
                                             "query": {"type": "string", "description": "搜索关键词"},
                                             "max_results": {"type": "integer", "description": "返回条数，默认3"},
                                         },
                                         "required": ["query"],
                                     },
                                 },
                             },
                         }},
                         **kw)


class Writer(BaseAgent):
    """写手：根据研究摘要 + 用户需求，写结构化报告。不带工具。"""
    ROLE = (
        "你是 Writer（报告写手）。输入是一份「研究摘要」和用户的原始需求。\n"
        "你的任务：写一份结构化中文报告。\n"
        "要求：\n"
        "1. 开头一段 2-3 句的摘要；\n"
        "2. 正文用 ## 分节，每节 2-5 句，条理清楚；\n"
        "3. 结尾一段「结论」；\n"
        "4. 忠实于研究摘要提供的事实，不编造；研究摘要标注「知识补充」的内容要如实标明；\n"
        "5. 只输出报告正文本身，不要任何自我介绍或客套话。"
    )

    def __init__(self, **kw):
        super().__init__("Writer", self.ROLE, **kw)


class Reviewer(BaseAgent):
    """评审：审核报告，输出结构化裁决 JSON（pass/revise）。不带工具。"""
    ROLE = (
        "你是 Reviewer（质量评审）。输入是 Writer 产出的报告草稿和用户需求。\n"
        "你的任务：按 3 条标准审核：\n"
        "1. 是否覆盖了用户需求的核心点；\n"
        "2. 结构是否清晰（摘要/分节/结论）；\n"
        "3. 是否有明显事实错误、空话或自相矛盾。\n"
        "输出格式（严格只输出这一行 JSON，不要任何其它文字）：\n"
        '{"verdict": "pass" 或 "revise", "score": 0到10的整数, "comments": "给 Writer 的具体修改意见"}'
    )

    def __init__(self, **kw):
        super().__init__("Reviewer", self.ROLE, **kw)


# ══════════════════════════════════════════════════════════════
# 任务 2：实现 Supervisor 编排
# ══════════════════════════════════════════════════════════════

# 解析 Reviewer 输出的 JSON。失败时给一个"必 revise"的保守结果——
# 宁可多改一轮，也不要把没审过的报告放行。
def _parse_verdict(text: str) -> dict:
    try:
        start, end = text.index("{"), text.rindex("}")
        obj = json.loads(text[start:end + 1])
        if obj.get("verdict") in ("pass", "revise"):
            return obj
        raise ValueError("verdict 字段非法")
    except Exception:
        return {"verdict": "revise", "score": 0,
                "comments": f"（评审输出无法解析，需按文本要求重写。原文：{text[:100]}）"}


def _default_ask_human(question: str) -> bool:
    """默认人工闸门：控制台 y/N。stdin 不可读（EOF）→ 默认拒绝。"""
    print()
    print("╔══════════════════════════════════════════════════╗")
    print("║  ⚠️  危险操作需要你的确认                        ║")
    print("╚══════════════════════════════════════════════════╝")
    print(f"  {question}")
    try:
        answer = input("  允许执行吗？[y/N] ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print("  （无法读取输入，默认拒绝）")
        return False
    return answer in ("y", "yes")


class Supervisor:
    """
    主管 Agent：负责分配任务、协调流程、判断是否完成。

    工作流程：
    1. 接收用户需求
    2. 派发给 Researcher → 收集资料
    3. Researcher 的输出 → 交给 Writer → 生成报告
    4. Writer 的输出 → 交给 Reviewer → 审核
    5. Reviewer 通过 → 走到人工闸门 → 返回最终报告
    6. Reviewer 不通过 → 把修改意见给 Writer → 回到步骤 4

    关键保护：
    - max_review_loops: Reviewer 最多让 Writer 改 N 次，超过则强制通过并标记
    - total_timeout: 整个流程的总超时
    - trace_log: 记录每一步的输入/输出/耗时，便于调试

    依赖注入（评测用）：
    - model_fn: 传一个假模型函数给所有 agent → 离线跑确定性用例，不烧 token
    - ask_human: 人工闸门的回调；测试时传 lambda q: True/False 免交互
    """

    def __init__(self, max_review_loops: int = 3, total_timeout: int = 120,
                 model_fn=None, ask_human=None):
        self.max_review_loops = max_review_loops
        self.total_timeout = total_timeout
        self.ask_human = ask_human or _default_ask_human

        # 三个 agent 共享同一个 TraceLogger；model_fn 透传实现依赖注入
        self.tracer = TraceLogger()
        self.researcher = Researcher(model_fn=model_fn, tracer=self.tracer)
        self.writer = Writer(model_fn=model_fn, tracer=self.tracer)
        self.reviewer = Reviewer(model_fn=model_fn, tracer=self.tracer)
        self.trace_log = []  # 每次 run 会刷新为这次的 trace

    def run(self, user_request: str) -> dict:
        """
        执行一次完整的多 agent 协作。

        返回:
        {
            "final_report": "最终报告内容",
            "review_loops": 2,           # Reviewer 让 Writer 改了几次
            "trace": [...],              # 完整的调用链
            "total_time": 45.2,          # 总耗时
            "total_tokens": 12000,       # 总 token 消耗（如果可以获取）
        }
        """
        start_time = time.time()
        # 每次 run 用新的 logger / 清零 token，保证多轮调用互不污染
        self.tracer = TraceLogger()
        for agent in (self.researcher, self.writer, self.reviewer):
            agent.tracer = self.tracer
            agent.total_tokens = 0
            agent.llm_calls = 0
        self.trace_log = self.tracer.traces
        self.tracer.log("Supervisor", "run/start", f"用户请求：{user_request[:80]}")

        # ── 0. 输入校验（轻量分支，不烧 token）──
        clean = (user_request or "").strip()
        if not clean:
            return self._finish(start_time, "❌ 错误：输入为空。请描述你想研究的主题。",
                                status="bad_input")
        if not any(ch.isalnum() for ch in clean):
            return self._finish(start_time, "❌ 错误：输入看起来没有有效内容（只有符号/空白）。",
                                status="bad_input")
        if len(clean) > 2000:
            return self._finish(start_time,
                                "❌ 错误：输入过长（超过 2000 字），请精简后重试。",
                                status="bad_input")

        def _deadline():
            return time.time() - start_time > self.total_timeout

        # ── 1. Research 阶段 ──
        self.tracer.log("Supervisor", "research/start", f"派出 {self.researcher.name}")
        research = self.researcher.think(clean)
        if research.startswith("[模型调用出错]") or research.startswith("[超步]"):
            return self._finish(start_time, f"❌ Researcher 失败：{research}",
                                status="agent_error")
        self.tracer.log("Supervisor", "research/done",
                        f"研究摘要 {len(research)} 字", research[:120])
        if _deadline():
            return self._finish(start_time, "❌ 超时：Research 阶段超过总时限。",
                                status="timeout")

        # ── 2. Write 阶段 ──
        self.tracer.log("Supervisor", "write/start", "把研究摘要交给 Writer")
        report = self.writer.think(
            clean,
            context=f"【研究摘要】\n{research}")
        if report.startswith("[模型调用出错]") or report.startswith("[超步]"):
            return self._finish(start_time, f"❌ Writer 失败：{report}",
                                status="agent_error")
        self.tracer.log("Supervisor", "write/done",
                        f"报告草稿 {len(report)} 字", report[:120])

        # ── 3. Review 循环（护栏：最大改写次数 + 总超时 + 防反复横跳）──
        # review_loops 语义 = "Writer 被要求改了几次"（见类注释/返回注释）。
        review_loops = 0
        round_no = 0                  # 第几次评审（trace 用，含通过的那次）
        reason = "passed"             # 循环正常结束时 = 评审通过
        verdict = None
        last_comments = None          # 上一轮"要求修改"的意见，用于检测反复横跳

        while True:
            # 护栏 1：已经让 Writer 改满 max_review_loops 次 → 不再审，强制通过
            if review_loops >= self.max_review_loops:
                reason = "max_loops_force_pass"
                self.tracer.log("Supervisor", "review/max_loops",
                                f"Writer 已改满 {self.max_review_loops} 次仍未通过，强制放行并标记")
                break

            # 护栏 2：总超时 → 带当前草稿退出（不再问人工）
            if _deadline():
                reason = "timeout"
                self.tracer.log("Supervisor", "review/timeout",
                                "总超时，带当前草稿退出")
                break

            round_no += 1
            self.tracer.log("Supervisor", "review/round",
                            f"第 {round_no} 轮评审（当前第 {review_loops} 次修改后版本）")

            review_text = self.reviewer.think(
                clean,
                context=f"【报告草稿】\n{report}\n\n请评审。")
            verdict = _parse_verdict(review_text)
            self.tracer.log("Reviewer", "verdict",
                            f"verdict={verdict['verdict']} score={verdict.get('score')}",
                            verdict.get("comments", ""), )

            if verdict["verdict"] == "pass":
                reason = "passed"
                break

            # 护栏 3：评审意见和上一轮一模一样 → 模型在自说自话，强制放行
            comment = verdict.get("comments", "")
            if last_comments and comment.strip() == last_comments.strip():
                reason = "oscillation_force_pass"
                self.tracer.log("Supervisor", "review/oscillation",
                                "评审意见与上一轮完全相同，判定反复横跳，强制放行")
                break

            last_comments = comment

            # 未通过 → 让 Writer 按意见改写一次
            review_loops += 1
            self.tracer.log("Supervisor", "revise/round",
                            f"第 {review_loops} 次改写，意见：{comment[:60]}")
            report = self.writer.think(
                clean,
                context=f"【研究摘要】\n{research}\n\n"
                        f"【上一版报告】\n{report}\n\n"
                        f"【评审要求修改】\n{comment}\n\n请按评审意见重写报告，"
                        f"逐条回应每一条意见。")
            self.tracer.log("Writer", "revise/done",
                            f"改写完成 {len(report)} 字", report[:120])

        # ── 4. 人工确认闸门（危险操作 = "把报告作为最终交付物发出去"）──
        # 模拟一个有副作用的交付动作（比如发邮件给团队）。必须人工确认才执行。
        # 超时/出错时报告不完整，不触发交付闸门，直接作为草稿返回。
        if reason == "timeout":
            approved = False
            status = "timeout"
            self.tracer.log("Supervisor", "gate/skip", "流程超时，跳过交付闸门")
            head = "⏰ 超时未完成：以下为当前草稿（未评审完、未交付）。"
        else:
            self.tracer.log("Supervisor", "gate/ask", "交付前请用户确认（危险操作闸门）")
            gate_ms = time.time()
            approved = self.ask_human(
                f"评审结果：{reason}。\n"
                f"是否将这份最终报告「发送给团队」作为本次交付？（模拟操作，不会真的发送）")
            gate_elapsed = (time.time() - gate_ms) * 1000
            self.tracer.log("Supervisor", "gate/result",
                            f"approved={approved}", "", gate_elapsed)

            if approved:
                print("  ✉️  [模拟] 已向团队发送最终报告……")
                status = "ok" if reason == "passed" else f"ok({reason})"
                head = "✅ 已人工确认并交付。"
            else:
                status = "ok(draft)" if reason == "passed" else f"ok({reason})(draft)"
                head = "🕐 未获人工确认——报告保留为草稿，未发送。"

        final_report = f"{head}\n\n{report}"

        # ── 5. 汇总返回 ──
        elapsed = time.time() - start_time
        total_tokens = (self.researcher.total_tokens
                        + self.writer.total_tokens
                        + self.reviewer.total_tokens)
        self.tracer.log("Supervisor", "run/done",
                        f"评审轮数={review_loops} token={total_tokens} "
                        f"耗时={elapsed:.1f}s 状态={status}")
        return {
            "final_report": final_report,
            "review_loops": review_loops,
            "status": status,
            "reason": reason,
            "gate_approved": approved,
            "trace": self.trace_log,
            "total_time": round(elapsed, 2),
            "total_tokens": total_tokens,
        }

    # 提前终止的公共出口（错误/超时/坏输入），结构一致方便上层统一处理
    def _finish(self, start_time, report: str, status: str) -> dict:
        elapsed = time.time() - start_time
        self.trace_log.append({
            "timestamp": time.strftime("%H:%M:%S"),
            "agent": "Supervisor",
            "action": f"run/{status}",
            "detail": "提前终止（不烧 token）",
            "result_preview": report[:120],
            "elapsed_ms": 0,
        })
        return {
            "final_report": report,
            "review_loops": 0,
            "status": status,
            "reason": status,
            "gate_approved": False,
            "trace": self.trace_log,
            "total_time": round(elapsed, 2),
            "total_tokens": 0,
        }


# ══════════════════════════════════════════════════════════════
# CLI 入口
# ══════════════════════════════════════════════════════════════

def main():
    print("=" * 55)
    print("L5 · 多 Agent 协作（Research → Write → Review）")
    print("=" * 55)
    print()
    print("角色：")
    print("  Researcher — 搜资料、出研究摘要（可联网）")
    print("  Writer     — 按摘要写结构化报告")
    print("  Reviewer   — 审报告，不通过就让 Writer 改（最多 3 轮）")
    print()

    # 提前验证 key（友好报错而不是到第一轮才炸）
    try:
        create_client()
    except RuntimeError as e:
        print(f"❌ {e}")
        print("（设好 key 再跑：$env:DEEPSEEK_API_KEY = 'sk-你的key'）")
        return

    supervisor = Supervisor()

    print("输入你想研究的问题（空行退出）：")
    print("提示：你可以先空跑体验角色协作，也可以随便问一个问题。")
    print("-" * 55)
    while True:
        try:
            user_input = input("\n你 > ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n再见！")
            break
        if not user_input:
            break
        if user_input.lower() in ("quit", "exit"):
            break

        print("\n⏳ 三个 agent 协作中……\n")
        result = supervisor.run(user_input)

        print("\n" + "=" * 55)
        print("最终报告")
        print("=" * 55)
        print(result["final_report"])
        print()
        print(f"—— 状态：{result['status']} | 评审轮数：{result['review_loops']} | "
              f"耗时 {result['total_time']}s | token {result['total_tokens']} ——")
        print()
        print(supervisor.tracer.report())
        print()


if __name__ == "__main__":
    main()


# ══════════════════════════════════════════════════════════════
# 常见坑
# ══════════════════════════════════════════════════════════════
#
# 坑 1：把多 Agent 当万能药
#   → 多 Agent 增加延迟和成本。如果一个 agent 就能干好的活，不要拆。
#
# 坑 2：Reviewer 永远不满意 → 死循环
#   → 多 agent 系统最经典的问题。解决方案：max_review_loops
#     + 每次记录修改了什么 + 检测"反复横跳"（意见与上轮相同→强制放行）。
#
# 坑 3：Agent 之间传递的信息丢失
#   → 用结构化格式交接。本实现里 Writer 的 context = 摘要 + 报告 + 意见，
#     三块用【】标题分隔，让模型分得清谁是谁。
#
# 坑 4：所有 agent 共用一个 messages list → 混乱
#   → 每个 agent 的 think 都从干净的 system+user 开始，互不污染；
#     信息由 Supervisor 负责"翻译"传递。
#
# 坑 5：Trace 日志太简略，出问题时无法定位
#   → 本实现的 trace 记录：哪个 agent → 什么操作 → 输入 → 输出预览 → 耗时。
#     如果 Reviewer 一直 reject，你可以在 trace 里看到它每次的理由。
