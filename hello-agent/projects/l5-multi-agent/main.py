"""
L5 · 多 Agent 协作
==================

核心认知：多 Agent 不是“更聪明的单 Agent”，而是把复杂任务拆成可验证的角色，
由 Supervisor 负责编排：Researcher 收集资料 → Writer 生成报告 → Reviewer 审核。

本文件包含：
- 惰性模型连接：import 本模块不需要 API key
- BaseAgent：统一封装模型调用、工具循环、trace 和 token 统计
- Researcher / Writer / Reviewer：三种职责边界清晰的 Agent
- Supervisor：串行编排 + 修改轮数/总超时/卡住检测三道护栏 + 人工确认闸门
- TraceLogger：全链路可观测性
- model_fn 依赖注入：评测时可替换为假模型，离线跑确定性用例

运行：python main.py
"""

import os
import re
import sys
import json
import time
import urllib.request

sys.stdout.reconfigure(encoding="utf-8")

MODEL = "deepseek-chat"
BASE_URL = "https://api.deepseek.com"

_client_singleton = None

def _resolve_env_key(name: str):
    """解析配置项：先读环境变量，再读 Windows 用户环境变量注册表。

这样 setx 设置后不必重开终端，脚本也能立即读到。
"""
    key = os.environ.get(name)
    if key:
        return key

    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as k:
            key, _ = winreg.QueryValueEx(k, name)
        return key
    except Exception:
        return None

def _resolve_api_key():
    """返回 DeepSeek API Key。"""
    return _resolve_env_key("DEEPSEEK_API_KEY")

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

    from openai import OpenAI

    _client_singleton = OpenAI(api_key=key, base_url=BASE_URL)
    return _client_singleton

BOCHA_URL = "https://api.bocha.cn/v1/web-search"

def web_search(query: str, max_results: int = 3) -> str:
    """联网搜索（给 Researcher）。结果截断，防止塞爆上下文。"""
    key = _resolve_env_key("BOCHA_API_KEY")
    if not key:
        return ("[工具提示] 搜索功能不可用（未配置 BOCHA_API_KEY）。"
                "请基于你的已有知识继续，不要假装搜到了。")

    body = json.dumps({"query": query, "count": max_results}).encode("utf-8")

    req = urllib.request.Request(
        BOCHA_URL, data=body,
        headers={"Authorization": f"Bearer {key}",
                 "Content-Type": "application/json"},
    )

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        return f"[工具提示] 搜索失败（网络、鉴权或限流）：{type(e).__name__}: {e}"

    if payload.get("code") != 200:
        return f"[工具提示] 搜索被拒：{payload.get('msg') or payload.get('code')}"

    results = ((payload.get("data") or {}).get("webPages") or {}).get("value") or []
    if not results:
        return f"[工具提示] 搜索「{query}」无结果，请基于知识继续。"

    lines = []
    for i, r in enumerate(results, 1):
        title = r.get("name") or "无标题"
        site = r.get("siteName") or ""
        snippet = (r.get("snippet") or "")[:150]
        href = r.get("url") or ""
        head = f"{i}. {title}（{site}）" if site else f"{i}. {title}"
        lines.append(f"{head}\n   {snippet}\n   {href}")
    return "\n\n".join(lines)

class TraceLogger:
    """调用链追踪器：记录每个 Agent 在什么时间做了什么。

多 Agent 出问题时，trace 用来定位是哪一步、哪个角色、哪次工具调用出了问题。
"""

    def __init__(self):
        self.traces = []

    def log(self, agent: str, action: str, detail: str,
            result_preview: str = "", elapsed_ms: float = 0):
        """记一笔。后两个参数有默认值，所以可以只传前三个。"""
        now = time.time()

        ms = int((now - int(now)) * 1000)

        timestamp = time.strftime("%H:%M:%S") + f".{ms:03d}"

        self.traces.append({
            "timestamp": timestamp,
            "agent": agent,
            "action": action,
            "detail": detail,
            "result_preview": result_preview[:120],
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

class BaseAgent:
    """所有 Agent 的基类。

四个职责：
- think()      对外入口：跑完 agent loop，返回文本结论
- _call()      调一次模型，规范化 {content, tool_calls, tokens}
- _run_tool()  执行一次工具调用，异常转成可读文本
- _log()       写一条 trace

model_fn 可注入假模型，用于离线评测；tools 结构为 {name: {"func", "schema"}}。
"""

    MAX_TOOL_STEPS = 6

    def __init__(self, name: str, role: str, tools: list = None,
                 model_fn=None, tracer: TraceLogger = None):
        self.name = name
        self.role = role
        self.tools = tools or {}
        self.model_fn = model_fn
        self.tracer = tracer
        self.total_tokens = 0
        self.llm_calls = 0

    def think(self, task: str, context: str = "") -> str:
        """
        Agent 执行一次"思考→行动→(必要时反复)→ 给出文本结论"。

        参数:
            task: 当前要完成的任务描述
            context: 上下文信息（如 Researcher 的输出给 Writer）

        返回: agent 的输出文本（纯文本；需要结构化时由调用方解析）
        """
        user_prompt = f"{context}\n\n【任务】\n{task}" if context else task
        messages = [
            {"role": "system", "content": self.role},
            {"role": "user", "content": user_prompt},
        ]

        try:
            for _ in range(self.MAX_TOOL_STEPS):
                call_start = time.time()
                resp = self._call(messages)
                call_ms = (time.time() - call_start) * 1000

                tool_calls = resp.get("tool_calls") or []
                content = resp.get("content", "")

                if not tool_calls:
                    self._log("answer", f"给出回答（{len(content)} 字）",
                              content[:120], call_ms)
                    return content

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
        except Exception as e:
            return f"[模型调用出错] {type(e).__name__}: {e}"

        return "[超步] 工具调用循环超过上限，已终止。"

    def _call(self, messages) -> dict:
        """发一次模型调用，返回规范化 dict：{content, tool_calls, tokens}"""
        self.llm_calls += 1

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
        "3. 是否有明显事实错误、空话或自相矛盾；\n"
        "4. 字数是否符合用户要求（用户提了字数就必须逐字核对）。\n"
        "输出格式（严格只输出这一行 JSON，不要任何其它文字）：\n"
        '{"verdict": "pass" 或 "revise", "score": 0到10的整数, '
        '"issue_type": "最主要问题的类别", "comments": "给 Writer 的具体修改意见"}\n'
        "issue_type 只能从下面 7 个词里选一个，必须原样照抄，不要翻译、不要加注解：\n"
        "  length    字数/篇幅不符合要求\n"
        "  accuracy  事实错误、无依据的断言、与检索结果不符\n"
        "  structure 结构混乱、缺分节或结论、段落冗余重复\n"
        "  coverage  漏掉了用户要求的要点\n"
        "  style     语言表达、措辞、可读性\n"
        "  other     以上都不是\n"
        "  none      verdict 为 pass 时填这个\n"
        "verdict 为 revise 时，issue_type 必须指出**最主要**的那一个问题——\n"
        "只填一个，别罗列。comments 里再详细展开。"
    )

    def __init__(self, **kw):
        super().__init__("Reviewer", self.ROLE, **kw)

ISSUE_TYPES = frozenset({
    "length",
    "accuracy",
    "structure",
    "coverage",
    "style",
    "other",
    "none",
})

def _normalize_issue_type(obj: dict) -> str:
    """把模型给的 issue_type 收进枚举；收不进去的一律当 "unknown"。

    这里要宽容一点：模型经常不老实照抄枚举，而是写成
    "length（字数超标）" 或者 "Length" 这类带注解/带大小写的变体。
    直接判非法太浪费——抓出开头的那个词再比一次就够了。

    "unknown" 是**不参与比较**的哨兵值：护栏 3 只认得出具体类别的重复。
    这样即使模型完全乱填，最坏结果也只是"少触发一次护栏"（多烧一轮），
    而不是"把不同问题误判成同一个"（错误放行）。
    """
    raw = str(obj.get("issue_type") or "").strip().lower()
    if raw in ISSUE_TYPES:
        return raw
    head = re.split(r"[（(\[【:：]", raw, maxsplit=1)[0].strip()
    return head if head in ISSUE_TYPES else "unknown"

_LENGTH_RE = re.compile(r"(\d{2,5})\s*字")

def _extract_length_limit(text: str):
    """把模型返回的 issue_type 归一化为固定枚举；无法识别则视为 unknown。"""
    m = _LENGTH_RE.search(text)
    if not m:
        return None
    n = int(m.group(1))
    return n if 50 <= n <= 5000 else None

def _parse_verdict(text: str) -> dict:
    try:
        start, end = text.index("{"), text.rindex("}")
        obj = json.loads(text[start:end + 1])
        if obj.get("verdict") in ("pass", "revise"):
            obj["issue_type"] = _normalize_issue_type(obj)
            return obj
        raise ValueError("verdict 字段非法")
    except Exception:
        return {"verdict": "revise", "score": 0, "issue_type": "unknown",
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
    """主管 Agent：编排 Researcher → Writer → Reviewer，并控制成本与交付。

护栏：
- max_review_loops：最多让 Writer 修改几次
- total_timeout：整个流程的总超时
- stuck 检测：连续两轮同一 issue_type 则强制放行
- 人工闸门：交付前确认；超时则直接返回草稿
"""

    def __init__(self, max_review_loops: int = 3, total_timeout: int = 120,
                 model_fn=None, ask_human=None):
        self.max_review_loops = max_review_loops
        self.total_timeout = total_timeout

        self.ask_human = ask_human or _default_ask_human

        self.tracer = TraceLogger()
        self.researcher = Researcher(model_fn=model_fn, tracer=self.tracer)
        self.writer = Writer(model_fn=model_fn, tracer=self.tracer)
        self.reviewer = Reviewer(model_fn=model_fn, tracer=self.tracer)
        self.trace_log = []

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
        self.tracer = TraceLogger()
        for agent in (self.researcher, self.writer, self.reviewer):
            agent.tracer = self.tracer
            agent.total_tokens = 0
            agent.llm_calls = 0
        self.trace_log = self.tracer.traces
        self.tracer.log("Supervisor", "run/start", f"用户请求：{user_request[:80]}")

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

        limit = _extract_length_limit(clean)
        limit_rule = ""
        shrink_hint = ""
        if limit:
            limit_rule = (
                f"【硬性要求·最高优先级】全文总字数控制在 {limit} 字左右，"
                f"不得超过 {int(limit * 1.5)} 字。\n"
                f"这条优先级高于下面任何「写得详细 / 写充分」的暗示：\n"
                f"如果研究摘要素材太多，**只挑最重要的 3 点写**，其余果断舍弃。\n"
                f"宁可少讲，不能超字数。\n\n"
            )
            shrink_hint = (
                "\n\n注意：本次改写要**做减法**——在上一版基础上删减、合并、压缩，"
                "不要推倒重写，更不要扩写。改完必须比上一版更短。"
            )
            self.tracer.log("Supervisor", "write/limit",
                            f"从需求中识别到字数上限 {limit} 字（硬约束已注入）")

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

        self.tracer.log("Supervisor", "write/start", "把研究摘要交给 Writer")
        report = self.writer.think(
            clean,
            context=f"{limit_rule}【研究摘要】\n{research}")
        if report.startswith("[模型调用出错]") or report.startswith("[超步]"):
            return self._finish(start_time, f"❌ Writer 失败：{report}",
                                status="agent_error")
        self.tracer.log("Supervisor", "write/done",
                        f"报告草稿 {len(report)} 字", report[:120])

        review_loops = 0
        round_no = 0
        reason = "passed"
        verdict = None
        last_issue = None

        while True:
            if review_loops >= self.max_review_loops:
                reason = "max_loops_force_pass"
                self.tracer.log("Supervisor", "review/max_loops",
                                f"Writer 已改满 {self.max_review_loops} 次仍未通过，强制放行并标记")
                break

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

            comment = verdict.get("comments", "")
            issue = verdict.get("issue_type", "unknown")
            if issue not in ("none", "unknown") and issue == last_issue:
                reason = "stuck_force_pass"
                self.tracer.log("Supervisor", "review/stuck",
                                f"连续两轮卡在同一个问题（{issue}），"
                                f"改不动了，强制放行")
                break

            last_issue = issue

            review_loops += 1
            self.tracer.log("Supervisor", "revise/round",
                            f"第 {review_loops} 次改写，意见：{comment[:60]}")
            report = self.writer.think(
                clean,
                context=f"{limit_rule}"
                        f"【研究摘要】\n{research}\n\n"
                        f"【上一版报告】\n{report}\n\n"
                        f"【评审要求修改】\n{comment}\n\n请按评审意见修改报告，"
                        f"逐条回应每一条意见。{shrink_hint}")
            self.tracer.log("Writer", "revise/done",
                            f"改写完成 {len(report)} 字", report[:120])

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
