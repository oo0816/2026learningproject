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
import urllib.request

sys.stdout.reconfigure(encoding="utf-8")


# ══════════════════════════════════════════════════════════════
# 模块 0：模型连接（惰性加载，import 本文件不解析 key）
# ══════════════════════════════════════════════════════════════
# 照抄 L3 的做法：把"配置加载"和"业务逻辑"解耦。
# 好处：离线单元测试 / 用假模型评测时，不需要 API key 也能 import main。
#
# ── 什么叫"惰性加载"（lazy）？──
#
# 反面做法是"急着加载"：在模块顶部直接写
#     client = OpenAI(api_key=os.environ["DEEPSEEK_API_KEY"])
# 这样只要 import 本文件，Python 就会立刻执行这一行。后果：
#     · 没设 key → KeyError，import 直接失败，你连跑测试的机会都没有
#     · 没装 openai 库 → ImportError，同样寸步难行
#     · 每次 import 都建一个连接，浪费
#
# 惰性做法是"用到才建"：把创建动作藏进 create_client()，
# 模块顶部只留一句 `_client_singleton = None`。import 时零副作用，
# 真正要调模型的那一刻才去解析 key、才去 import openai。
#
# 这不是洁癖，是实打实的功能需求：本文件支持"注入假模型"离线跑评测
# （见 BaseAgent 的 model_fn），那种场景下根本不需要真 key。
# 如果 import 阶段就强制要 key，整个评测能力就废了。

MODEL = "deepseek-chat"
BASE_URL = "https://api.deepseek.com"

# 真实模型只初始化一次（懒加载缓存）
#
# 这是"单例"（singleton）模式的最小写法：用一个模块级变量当缓存。
# 为什么要缓存？OpenAI 客户端内部维护着 HTTP 连接池，
# 每次调用都重新 OpenAI(...) 等于反复重建连接，多 agent 场景下浪费明显。
#
# 注意名字前面的下划线：Python 约定，表示"模块内部的，外部别碰"。
_client_singleton = None


# ── 配置从哪来（两层查找 + 一个平台专属兜底）──
#
# 代码需要 API key，但 key 不能写进源码（会跟着 git 提交出去）。
# 所以要找个"外部的地方"存。Windows 上有两个地方，各有各的坑：
#
#   存放地                             谁看得见
#   ─────────────────────────────────  ──────────────────────────
#   ① 进程内存的环境变量快照          只有当前这个进程
#   ② 注册表 HKCU\Environment         所有程序，永久有效
#
# 坑在于：`setx` 写的是 ②，但它**不会**更新已经开着的进程的 ①。
# 所以老终端里读 os.environ 是空的，必须重开终端才生效——很烦。
#
# 这个函数的策略：先试 ①（快，且跨平台），不行就直接翻 ② 原始数据。
# 直接读注册表就绕过了"要重开终端"的限制：setx 完立刻能读到。
def _resolve_env_key(name: str):
    """解析一个配置项：先看环境变量，取不到再从 Windows 注册表读用户变量。

    注册表兜底是因为：在 Windows 上「用户环境变量」要新开终端才生效，
    从注册表直接读可以立刻拿到，省得反复重开 PowerShell。
    """
    # ── 第一优先：环境变量 ──
    # 用 .get() 而不是 os.environ[name]：前者取不到返回 None，
    # 后者会抛 KeyError。这里「没有」是正常情况，不该当异常处理。
    key = os.environ.get(name)  # 取不到返回none（）
    if key:
        return key

    # ── 第二优先：注册表 ──
    # import 放在 try 里（不是文件顶部）是因为 winreg 只在 Windows 上有。
    # 在 Mac/Linux 上 import 会失败，被下面的 except 接住 → 返回 None，
    # 而不是让整个程序崩掉。
    try:
        import winreg  # windows的注册表
        # OpenKey(根节点, 路径) → 打开 HKCU\Environment 这一栏。
        # 返回的是一个「句柄」（handle，系统内部的编号），不是配置内容本身。
        # with 保证离开这个块时自动关闭句柄，等价于 try/finally。
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as k:
            # QueryValueEx(句柄, 值名) → 返回二元组 (数据, 类型)。
            # 类型是 REG_SZ / REG_EXPAND_SZ 这类注册表数据类型码，用不上，
            # 所以用 `_` 接住丢掉（Python 惯例：这个位置有东西但我不关心）。
            key, _ = winreg.QueryValueEx(k, name)
        return key
    except Exception:
        # 这里捕 Exception 而不是具体某个异常，是有意的：
        # 实测「键不存在」和「值不存在」抛的是同一个 FileNotFoundError，
        # 消息还一模一样，调用方根本没法区分。既然区分不了，
        # 就统一归为「没配这个 key」，交给调用方走降级分支。
        return None


def _resolve_api_key():
    """DeepSeek 的 key（模型调用用）。 是取apikey的意思


    薄薄一层包装，好处是那个字符串只出现一次（要改名只改这一行），
    而且调用点读起来是「取 api key」而不是「取名为 DEEPSEEK_API_KEY 的环境变量」。
    """
    return _resolve_env_key("DEEPSEEK_API_KEY")


def create_client():
    """创建 OpenAI 兼容客户端；没配 key 时抛错（由调用方决定怎么处理）。"""
    # global：函数里给变量赋值时，Python 默认当它是局部变量。
    # 不写这行，下面的 `_client_singleton = ...` 只会创建个局部变量，
    # 模块级那个永远是 None，缓存彻底失效（而且上面 if 还会报 UnboundLocalError）。
    global _client_singleton

    # ── 单例的「命中缓存」分支 ──
    if _client_singleton is not None:
        return _client_singleton

    key = _resolve_api_key()
    if not key:
        # 注意这里选择「抛错」而不是「返回 None」：这属于配置缺失（编程错误），
        # 早炸早好。调用方（CLI 入口）会接住它，给出友好提示。
        raise RuntimeError(
            "未找到 DEEPSEEK_API_KEY\n请运行：$env:DEEPSEEK_API_KEY = 'sk-你的key'"
        )

    # 惰性 import：没装 openai 库时其它功能仍可用
    # （比如只跑假模型评测、只测 TraceLogger，都不需要这个库）
    from openai import OpenAI

    # base_url 指向 DeepSeek —— 它提供 OpenAI 兼容接口，
    # 所以能直接复用官方 SDK，只是换个地址。
    _client_singleton = OpenAI(api_key=key, base_url=BASE_URL)
    return _client_singleton


# ══════════════════════════════════════════════════════════════
# 模块 1：联网搜索工具（给 Researcher 用，可选）
# ══════════════════════════════════════════════════════════════

# 用博查（Bocha）Web Search API。为什么不用 ddgs / duckduckgo_search？
# 那些库靠爬 DuckDuckGo、Google、Bing 的公开网页，在国内会被重置连接（os error 10054），
# 换 backend 也没用（bing/mojeek/brave/yandex 实测全挂）。博查是国内直连的正规 API。
#
# 只需标准库 urllib，不引入新依赖；没配 key 时优雅降级，agent 照样能跑。
# 配置：$env:BOCHA_API_KEY = 'sk-你的key'

BOCHA_URL = "https://api.bocha.cn/v1/web-search"


# ── 工具的契约：永远返回字符串，永远不抛异常 ──
#
# 这一点很重要，是整个工具系统的设计前提。回顾 BaseAgent._run_tool()：
# 工具函数的返回值会被原样塞进 messages 里当 `role: "tool"` 的内容。
# 所以它必须是「模型读得懂的文本」。
#
# 假如这里改成 raise 一个异常，会怎样？
# 异常一路冒泡到 think() 的 except，整个 agent 直接挂掉，
# 模型连"搜索失败了，我改用已有知识"这个补救机会都没有。
#
# 所以这里的规矩是：把「失败」也当成一种正常结果，转成文本还给模型。
# 前缀 `[工具提示]` / `[工具错误]` 是给模型看的信号——它一看就知道
# 这不是搜索结果，而是系统在跟它说话。
def web_search(query: str, max_results: int = 3) -> str:
    """联网搜索（给 Researcher）。结果截断，防止塞爆上下文。"""
    # ── 前置检查：没配 key 就降级 ──
    # 这是"优雅降级"：搜索用不了不代表整个 agent 用不了。
    # 明确告诉模型"别假装搜到了"，防止它编造不存在的搜索结果（很常见的幻觉源）。
    key = _resolve_env_key("BOCHA_API_KEY")
    if not key:
        return ("[工具提示] 搜索功能不可用（未配置 BOCHA_API_KEY）。"
                "请基于你的已有知识继续，不要假装搜到了。")

    # ── 组装 HTTP 请求 ──
    # 三步：准备 body → 构造 Request 对象 → 真正发出去。
    #
    # ① body：把 Python 字典转成 JSON 字节串。
    #    .encode("utf-8") 不能省——网络传的是字节，不是 str。
    #    字段名是 count 不是 max_results，这是博查 API 定的。
    body = json.dumps({"query": query, "count": max_results}).encode("utf-8")

    # ② Request 对象：只是"打包"，还没发出去。里面三样东西：
    #    · URL
    #    · data=   有它 → POST 请求（没有就是 GET）
    #    · headers= 两个头：
    #        Authorization: Bearer xxx  ← 鉴权，key 放这里
    #        Content-Type: application/json ← 告诉对方"我发的是 JSON"
    req = urllib.request.Request(
        BOCHA_URL, data=body,
        headers={"Authorization": f"Bearer {key}",
                 "Content-Type": "application/json"},
    )

    # ③ urlopen 才是真正发出去并等响应。
    #    timeout=15 必须设！网络卡住时不会无限期挂起，15 秒后抛异常走降级。
    #    with 保证连接用完自动关闭。
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            # read() 拿到原始字节 → decode 成 str → json.loads 转成 dict
            payload = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        # 网络异常 / 401 / 限流都走这里，转成给模型看的文本，而不是让 agent 崩掉
        # type(e).__name__ 把异常类名也带上，方便你调试时看清是哪类失败
        return f"[工具提示] 搜索失败（网络、鉴权或限流）：{type(e).__name__}: {e}"

    # ── 解析响应 ──
    # 实测的响应结构（用真实 key 打过一次）：
    # {
    #   "code": 200,                     ← 业务状态码
    #   "msg": null,
    #   "data": {
    #     "webPages": {
    #       "value": [                   ← 结果数组在这里
    #         {"name": "标题", "url": "...", "snippet": "摘要",
    #          "siteName": "博客园", "datePublished": "..."},
    #         ...
    #       ]
    #     }
    #   }
    # }
    #
    # 注意：HTTP 层已经成功了（没进 except），但业务层可能仍有问题，
    # 所以要再看一眼 code 字段。两层状态是分开的。
    if payload.get("code") != 200:
        return f"[工具提示] 搜索被拒：{payload.get('msg') or payload.get('code')}"

    # 逐层往下挖，每一层都用 `or {}` / `or []` 兜底：
    # 万一某层是 None（API 改版、异常返回），继续 .get() 会报
    # AttributeError，用 `or` 换成空容器就能安全地一路走到底。
    # 这行等价于：payload["data"]["webPages"]["value"]，但绝不会抛异常。
    results = ((payload.get("data") or {}).get("webPages") or {}).get("value") or []
    if not results:
        # "搜到 0 条"不算错误，也是一种正常结果——如实告诉模型
        return f"[工具提示] 搜索「{query}」无结果，请基于知识继续。"

    # ── 格式化成模型友好的纯文本 ──
    # 为什么转文本而不直接把 JSON 丢给模型？
    # 精简（去掉一大堆用不上的字段）、省 token，而且模型对
    # 「编号 + 标题 + 摘要 + 链接」这种排版理解得更稳。
    lines = []
    for i, r in enumerate(results, 1):   # enumerate 第二参数是起始编号，从 1 开始
        # 每个字段都 `or 默认值`：API 可能返回 null，而 None 拼进 f-string
        # 会变成字符串 "None"，很难看。用 or 换成合理的缺省值。
        title = r.get("name") or "无标题"
        site = r.get("siteName") or ""
        snippet = (r.get("snippet") or "")[:150]   # 截断防塞爆上下文
        href = r.get("url") or ""
        head = f"{i}. {title}（{site}）" if site else f"{i}. {title}"
        lines.append(f"{head}\n   {snippet}\n   {href}")
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

    ── 为什么多 agent 特别需要这个？──

    单 agent 出问题你还能顺着读一遍代码。多 agent 不行：三个 agent
    在同一个进程里轮流跑，报错信息里根本看不出是"谁在第几步"出的问题。

    最典型的就是「Reviewer 一直不给过」。没有 trace，你只看到流程卡住；
    有了 trace，你能看到它每一轮到底在挑什么毛病——是真在挑刺，
    还是每次都重复同一句话（那就说明是模型在绕圈，不是报告有问题）。

    这也是 [坑 5] 说的那件事：日志太简略，出问题时无法定位。
    """

    def __init__(self):
        self.traces = []   # 一个列表，log() 往里追加，report() 读出来

    def log(self, agent: str, action: str, detail: str,
            result_preview: str = "", elapsed_ms: float = 0):
        """记一笔。后两个参数有默认值，所以可以只传前三个。"""
        now = time.time()          # 浮点秒数，比如 1770000000.234

        # 从浮点时间戳里抠出毫秒部分：
        #   int(now)      → 1770000000      （丢掉了小数）
        #   now - int(now) → 0.234          （只剩下小数部分，即秒以下的零头）
        #   * 1000         → 234.0          （换算成毫秒）
        #   int(...)       → 234            （取整）
        # 因为 time.time() 返回的是"秒 + 小数"，小数部分就是毫秒。
        ms = int((now - int(now)) * 1000)

        # time.strftime 只给到秒（"14:30:01"），毫秒得自己拼上去。
        # f".{ms:03d}" 的 03d = 补零到 3 位，所以是 ".007" 而不是 ".7"。
        timestamp = time.strftime("%H:%M:%S") + f".{ms:03d}"

        self.traces.append({
            "timestamp": timestamp,
            "agent": agent,
            "action": action,
            "detail": detail,
            # 只存前 120 字。如果 agent 输出上千字，全部塞进 trace 会让
            # trace 本身变得没法读，也可能撑爆内存/上下文。
            "result_preview": result_preview[:120],
            "elapsed_ms": round(elapsed_ms, 1),   # 保留 1 位小数就够
        })

    def report(self) -> str:
        """生成人类可读的 trace 报告"""
        if not self.traces:
            return "（无 trace）"

        lines = ["── Trace ──"]
        for t in self.traces:
            # f"{x:<11}" 里的 `<11` 是格式说明符：左对齐、占 11 个字符宽。
            # 不够长的用空格补齐。效果是让不同长度的内容对齐成一列：
            #   Researcher  | tool_call
            #   Writer      | answer
            #   Supervisor  | run/start
            # 不加这个，长短不一会把后面的竖线顶得参差不齐。
            # 想右对齐就用 `>11`，居中用 `^11`。
            lines.append(
                f"[{t['timestamp']}] {t['agent']:<11} | {t['action']:<18} | "
                f"{t['detail']}"
            )
            # 有结果预览就多缩进一行挂在下面，形成树状观感
            if t["result_preview"]:
                lines.append(f"                └─ 结果: {t['result_preview']}")

        return "\n".join(lines)   # 用换行拼成一整块文本，方便一次 print


# ══════════════════════════════════════════════════════════════
# 模块 3：BaseAgent — 任意角色 agent 的基类
# ══════════════════════════════════════════════════════════════

# ── 为什么用继承？──
#
# 回头看三个角色（Researcher / Writer / Reviewer），它们真正不同的只有两样：
#     ① system prompt（人设不同）
#     ② 有没有工具（只有 Researcher 带 web_search）
#
# 其余全部一样：都要调模型、都要处理工具调用、都要记 trace、都要算 token。
# 所以把这些"一样的东西"全放进基类，子类只需要填 ① 和 ②。
#
# 这是继承最正当的用法：**复用行为，而不是复用数据**。
# 子类 Writer 的代码只有 3 行，却能继承整套工具调用能力。
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

    本类一共就 4 个方法，分工很清楚：
        think()     对外唯一入口：给任务，拿结论（内含 agent loop）
        _call()     跟模型说一次话，把响应规范化成统一 dict
        _run_tool() 执行一次工具调用，把结果转成字符串
        _log()      记一笔 trace（没 tracer 就跳过）

    前面带下划线的三个是内部实现，外部只该调 think()。
    """

    # 类属性（不是实例属性）——所有 agent 共用同一个上限。
    # 单个 think 内最多允许几次"思考→调用工具→看结果"的循环。
    # 这是护栏：防止模型一直要工具不肯收尾，无限烧 token。
    MAX_TOOL_STEPS = 6

    def __init__(self, name: str, role: str, tools: list = None,
                 model_fn=None, tracer: TraceLogger = None):
        self.name = name
        self.role = role
        # `tools or {}` 是个惯用法：如果传进来的是 None，就用空字典。
        # 注意这里的类型标注写的是 list 但实际存的是 dict——
        # 小笔误，不影响运行（Python 不强制检查标注）。
        self.tools = tools or {}
        self.model_fn = model_fn  # None → 用真实 DeepSeek
        self.tracer = tracer      # None → 不记 trace（纯离线跑）
        # 下面两个是"账本"，run() 每次开始时会清零
        self.total_tokens = 0     # 本 agent 累计消耗的 token（可跨 think 累加）
        self.llm_calls = 0

    # ── 给 Agent 的对外接口 ────────────────────────────────
    #
    # think() 是 agent 的"大脑一击"：给它一个任务，它想一下、
    # （可能查几次资料）、然后给出文字结论。
    #
    # ── 先理解「工具调用协议」这个前提 ──
    #
    # 模型自己动不了手，它只能"说话"。所谓工具调用，本质是：
    #    模型输出一段特殊格式的话 → 「我想调用 web_search，参数是 {...}」
    #    程序读到了 → 真的去执行 → 把结果再喂回给模型
    #    模型拿到结果 → 这才给出最终回答
    #
    # 关键词是**对话是累积的**。模型没有记忆，每次请求都得把
    # 「到目前为止发生过的所有对话」整个再发一遍。所以必须按顺序往
    # messages 里追加消息，让模型看到完整的前因后果。
    #
    # 一次完整的工具调用，messages 会长成这个"三角"形状：
    #
    #   [0] system     "你是 Researcher..."          ← 人设
    #   [1] user       "研究一下量子计算"            ← 任务
    #   [2] assistant  tool_calls=[web_search(...)]  ← ① 模型：我想搜
    #   [3] tool       tool_call_id=xxx, "结果..."   ← ② 程序：搜好了，给你
    #   [4] assistant  "研究摘要：..."               ← ③ 模型：那我说结论
    #
    # 注意 ① 和 ③ 都是 assistant（都是模型说的），中间夹着 ②（程序说的）。
    # ② 必须紧跟在 ① 后面，而且要靠 tool_call_id 对上是哪一次调用——
    # 这是协议强制的，漏了或对不上，API 会直接报 400。
    def think(self, task: str, context: str = "") -> str:
        """
        Agent 执行一次"思考→行动→(必要时反复)→ 给出文本结论"。

        参数:
            task: 当前要完成的任务描述
            context: 上下文信息（如 Researcher 的输出给 Writer）

        返回: agent 的输出文本（纯文本；需要结构化时由调用方解析）
        """
        # ── 每个 think 从一张白纸开始 ──
        #
        # messages 是**局部变量**，不是 self.messages —— 这是有意的设计。
        # 如果做成实例属性，三个 agent 就会互相污染，而且上一轮任务的
        # 残留会带进下一轮（见 [坑 4]）。
        #
        # 代价是：agent 之间不共享记忆，信息全靠 Supervisor 手动"翻译"
        # 传递（Writer 收到的 context 就是 Supervisor 拼出来的）。
        # 粗糙，但可预测。
        user_prompt = f"{context}\n\n【任务】\n{task}" if context else task
        messages = [
            # system 消息定义"你是谁"——就是子类里那个 ROLE 字符串
            {"role": "system", "content": self.role},
            # user 消息是"要你干什么"
            {"role": "user", "content": user_prompt},
        ]

        # 整个 think 包在 try 里：模型可能调用失败（网络、key、限流），
        # 不能让异常冒泡出去把整个多 agent 流程炸掉。
        try:
            # ── 这个 for 就是经典的 agent loop 本尊 ──
            #
            # 它做的事：反复"问模型 → 如果它要工具就执行 → 把结果加进对话
            # → 再问 → ..."，直到模型不再要工具（说明它准备好回答了）。
            #
            # for + range(MAX_TOOL_STEPS) 是**护栏**：万一模型犯了轴，
            # 一直要工具不肯给结论，最多转 MAX_TOOL_STEPS（6）圈就强停。
            # 没有这个上限，就是一个无限循环 + 无限烧 token。
            for _ in range(self.MAX_TOOL_STEPS):
                # 1. 调用模型
                call_start = time.time()          # 记开始时间，为了算耗时
                resp = self._call(messages)       # 把整个对话发过去
                call_ms = (time.time() - call_start) * 1000   # 秒 → 毫秒

                tool_calls = resp.get("tool_calls") or []
                content = resp.get("content", "")

                # 2. 没要工具 → 直接回答，结束
                #
                # 这是循环的**正常出口**。模型这次没提工具请求，
                # 说明它认为信息够了，content 就是要的结果。
                if not tool_calls:
                    self._log("answer", f"给出回答（{len(content)} 字）",
                              content[:120], call_ms)
                    return content

                # 3. 要了工具 → 把 assistant 的请求记进对话，然后逐个执行
                #
                # ── 为什么要先 append 一条 assistant 消息？──
                #
                # 因为协议要求「三角」完整。上面说过 messages 是累积的，
                # 如果跳过这条直接塞 tool 结果，模型会看到：
                #     user: 研究一下量子计算
                #     tool: 搜索结果是...        ← 咦？谁让你搜的？
                # 协议规定 tool 消息前面必须有对应的 assistant 请求，
                # 否则 API 报 400。
                #
                # 换句话说：这条不是"记录"，是**给下一轮请求补上必要的上下文**。
                self._log("tool_request",
                          f"请求 {len(tool_calls)} 个工具调用",
                          f"tools={[tc['name'] for tc in tool_calls]}", call_ms)
                messages.append({
                    "role": "assistant",
                    # content or None：这次输出里 content 是空字符串 ""，
                    # 但 API 要求"只有 tool_calls、没有正文"时这里必须是 null。
                    # 空字符串和 null 在协议里含义不同，所以用 or 把 "" 转成 None。
                    "content": content or None,
                    # 把 _call() 规范化好的内部格式，转回 API 要求的嵌套格式。
                    # 注意这层 function 嵌套：这是 OpenAI 的原始 schema，
                    # 而在 think() 内部我们一直用扁平的 tc["name"]，更好读。
                    "tool_calls": [
                        {"id": tc["id"], "type": "function",
                         "function": {"name": tc["name"],
                                      "arguments": tc["arguments"]}}
                        for tc in tool_calls
                    ],
                })

                # ── 逐个执行工具，每个结果配一条 tool 消息 ──
                #
                # 模型一次可能要求调多个工具（这里遍历而不是只取第一个）。
                for tc in tool_calls:
                    tool_start = time.time()
                    result = self._run_tool(tc["name"], tc["arguments"])
                    tool_ms = (time.time() - tool_start) * 1000
                    self._log("tool_call", f"{tc['name']}({tc['arguments'][:80]})",
                              result[:120], tool_ms)
                    messages.append({
                        "role": "tool",
                        # tool_call_id 是"回执编号"：模型可能一次要调 3 个工具，
                        # 这个 id 让它知道"这条结果对应我哪个请求"。
                        # 必须和第 2 条消息里那个 tc["id"] 一字不差。
                        "tool_call_id": tc["id"],
                        "content": result,   # 工具返回值，必须是字符串
                    })
                # 回到循环顶部，把工具结果再喂给模型
                # —— 注意这里没有 return，所以会再转一圈。
        except Exception as e:
            # API / key / 网络错误 → 不静默吞，作为输出返回，让上层看见
            #
            # 这里"吞掉异常"是有道理的：多 agent 流程里一个 agent 挂了，
            # 不应该让整个程序崩。但不代表要假装没事——所以把错误
            # **格式化进返回值**，Supervisor 会检查这个前缀并作出反应
            # （见 run() 里的 research.startswith("[模型调用出错]")）。
            return f"[模型调用出错] {type(e).__name__}: {e}"

        # 能走到这里说明 for 循环转满 6 圈还没拿到结论——超步了。
        # 和上面同理，不抛异常，而是返回一段可识别的文本。
        return "[超步] 工具调用循环超过上限，已终止。"

    # ── 内部实现 ──────────────────────────────────────────

    # _call() 是"真正跟模型说话"的那一层。think() 只管逻辑，
    # 所有跟具体 API 打交道、解析响应的脏活都收在这里。
    #
    # ── 核心设计：把两种完全不同的来源，规范成同一个格式 ──
    #
    # 它有两个岔路：
    #   ① model_fn 不为 None → 用外面注入的假模型（离线评测，不花钱）
    #   ② model_fn 为 None   → 走真实 DeepSeek API
    #
    # 但**不管走哪条，返回的都是同一个字典**：
    #     {"content": str, "tool_calls": [...], "tokens": int}
    #
    # 这就是"规范化"（normalize）的意义：think() 完全不用知道
    # 这次调用是真模型还是假模型，它只认这个统一格式。
    # 少了这层，think() 里就得写一堆 if 判断走哪条路。
    #
    # 顺带一提，这也是"依赖注入"的落点：假模型只要遵守这个
    # 返回格式，就能无缝替换真模型，一分钱不花跑完整流程。
    def _call(self, messages) -> dict:
        """发一次模型调用，返回规范化 dict：{content, tool_calls, tokens}"""
        self.llm_calls += 1    # 计数器：本 agent 一共调了几次模型

        # ── 收集工具说明书 ──
        #
        # schemas 是**给模型看的**，不是给程序用的。它用自然语言告诉模型：
        # "你手上有个叫 web_search 的工具，能干这个，要传这些参数"。
        # 模型读了才知道自己可以要工具、以及该怎么写参数。
        #
        # self.tools 的结构是 {工具名: {"func": 真实函数, "schema": 说明书}}，
        # 这里只挑出 schema 发给模型——真实函数（func）当然不能发，
        # 那是本地执行用的。
        schemas = [self.tools[name]["schema"] for name in self.tools]

        if self.model_fn is not None:
            # ── 岔路 ①：注入的假模型 ──
            # 直接调，把 messages 和 schemas 都给它。
            # 返回什么由假模型自己决定，但必须符合约定的格式。
            resp = self.model_fn(messages, schemas)
        else:
            # ── 岔路 ②：真实 DeepSeek ──
            client = create_client()

            # 先把必填参数塞进字典，再按情况补可选项。
            # 这样写比一次写完更适合"可选参数"的场景。
            kwargs = {"model": MODEL, "messages": messages}
            if schemas:
                # 没有工具就不传 tools 字段——有些 API 对空列表会报错。
                kwargs["tools"] = schemas

            # **kwargs 是"字典解包"：等价于
            # client.chat.completions.create(model=MODEL, messages=messages, ...)
            raw = client.chat.completions.create(**kwargs)

            # ── 下面这一段全是"拆包装" ──
            # SDK 返回的是一个层层嵌套的**对象**（不是字典），
            # 取值要用 .属性 而不是 ["键"]，而且嵌得很深：
            #   raw.choices[0].message.tool_calls[0].function.name
            # choices 是列表是因为 API 支持一次生成多个候选，我们只用第 0 个。
            msg = raw.choices[0].message

            # 把 SDK 的对象转成朴素的 dict（扁平化，去掉 function 那层嵌套）。
            # 目的：和岔路 ① 的假模型输出的格式对齐。
            tool_calls = []
            for tc in (msg.tool_calls or []):   # or []：没要工具时它是 None
                tool_calls.append({
                    "id": tc.id,
                    "name": tc.function.name,
                    # arguments 是**字符串**形式的 JSON（不是 dict！），
                    # 因为这是模型"写"出来的文本。真正的解析在 _run_tool 里。
                    # or "{}"：极少数情况下它是 None，兜底成空参数。
                    "arguments": tc.function.arguments or "{}",
                })

            # ── 取 token 用量 ──
            # getattr(对象, 名字, 默认值)：安全地取属性，没有就返回默认值。
            # 为什么要这么小心？因为 usage 是可选字段，有些兼容接口
            # （比如 DeepSeek、各种中转）可能不返回它。直接 .usage 会炸。
            usage = getattr(raw, "usage", None)
            tokens = getattr(usage, "total_tokens", 0) or 0

            resp = {"content": msg.content or "", "tool_calls": tool_calls,
                    "tokens": tokens}

        # 累加到本 agent 的账上（跨多次 think 累计，最后 Supervisor 汇总）
        self.total_tokens += resp.get("tokens", 0)
        return resp

    # _run_tool() 负责"把模型的意图变成真实动作"。
    # 它拿到的 arguments 是**一段 JSON 文本**（模型生成的），
    # 要解析成 Python 参数，才能真的去调那个函数。
    #
    # 和 web_search 一样遵守同一个契约：永远返回字符串，永远不抛异常。
    def _run_tool(self, name: str, arguments: str) -> str:
        """执行一个工具，返回字符串结果。任何异常都变成可读的文本。"""
        # 模型理论上只会要它见过的工具，但它也可能"幻觉"出不存在的名字，
        # 所以要先查一下。宁可回一句错误提示，也不能 KeyError 崩掉。
        if name not in self.tools:
            return f"[工具错误] 未知工具：{name}"
        try:
            # ── 把 JSON 文本解析成 Python 字典 ──
            # 模型的输出是 '{"query": "量子计算", "max_results": 3}' 这样的文本。
            # json.loads 把它变成真正的 dict。
            # `if arguments else {}` 兜底：空字符串时给个空字典，
            # 这样下面 **args 不会炸（虽然也没参数可传）。
            args = json.loads(arguments) if arguments else {}

            # 防一手：模型可能生成合法的 JSON 但不是对象
            # （比如 '["量子计算"]' 或 '"量子计算"'）。
            # 那样 **args 会报类型错，不如提前拦下给个清楚提示。
            if not isinstance(args, dict):
                return f"[工具错误] 参数不是对象：{arguments[:120]}"

            # ── 真正执行 ──
            # **args 是"字典解包"：如果 args = {"query": "量子计算"}，
            # 这行等价于 self.tools["web_search"]["func"](query="量子计算")
            # —— 把字典的键变成关键字参数。这就是 schema 里声明
            # 参数名要跟函数形参名一致的原因，名字对不上就传不进去。
            raw = self.tools[name]["func"](**args)
        except Exception as e:
            # 工具内部抛的任何异常（网络、权限、写错）都在这里被接住，
            # 变成一段模型能读懂的文本。绝不让它冒泡上去炸掉 agent。
            return f"[工具错误] {type(e).__name__}: {e}"

        # 统一转字符串（模型只认文本），并截断到 2000 字——
        # 防止某个工具返回一大坨把上下文塞爆。
        return str(raw)[:2000]

    def _log(self, action: str, detail: str, preview: str = "", ms: float = 0):
        """有 tracer 时才记 trace（离线跑可不开）"""
        # 这个 if 是为了让离线测试更干净：不传 tracer 时所有 _log 调用
        # 都变成空操作。否则跑一次评测会打印出一大堆用不上的 trace。
        if self.tracer is not None:
            self.tracer.log(self.name, action, detail, preview, ms)


# ══════════════════════════════════════════════════════════════
# 任务 1：定义 Agent 角色（继承 BaseAgent，只改 system prompt + 工具）
# ══════════════════════════════════════════════════════════════

# ══════════════════════════════════════════════════════════════
# 任务 1：定义 Agent 角色（继承 BaseAgent，只改 system prompt + 工具）
# ══════════════════════════════════════════════════════════════
#
# 三个角色刻意做成"能力递减"：
#   Researcher —— 要查外部世界，所以带 web_search 工具
#   Writer     —— 只做文字加工，不需要工具
#   Reviewer   —— 只做判断，也不需要工具
#
# 这体现了多 agent 的一个核心原则：**给每个 agent 刚好够用的能力**。
# 如果 Writer 也有搜索工具，它可能自己去查、去编，反而不忠实于研究摘要了。
# 能力越少，行为越可预测——这也是为什么"多 agent"不是"更强 agent"，
# 而是"更可控的 agent 分工"。


class Researcher(BaseAgent):
    """研究员：搜索 + 汇总资料。带 web_search 工具。"""
    # 类属性 ROLE：整个类共用一个字符串，不用每个实例存一份。
    # 这里写的每一句都会成为 system prompt——即"你是谁、你要做什么"。
    ROLE = (
        "你是 Researcher（研究员）。你的任务：针对用户的主题做资料收集与要点梳理，"
        "输出一份「研究摘要」。\n"
        "要求：\n"
        "1. 可以调用 web_search 工具查证（最多 2 次搜索），拿不到就用你的知识补充并标注「知识补充」；\n"
        "2. 摘要分条列出：核心事实、关键角度、可用的数据/例子；\n"
        "3. 只输出研究摘要文本，不要写最终报告。"
    )

    def __init__(self, **kw):
        # **kw 收集调用方传进来的所有关键字参数（model_fn、tracer 等），
        # 再原样转交给父类。这样 Supervisor 就能用统一的方式构造三个角色：
        #     Researcher(model_fn=..., tracer=...)
        #     Writer(model_fn=..., tracer=...)
        # 而不用管每个角色的构造细节。这叫"参数透传"。
        super().__init__("Researcher", self.ROLE,
                         # ── tools 的结构：{工具名: {"func": 真实函数, "schema": 说明书}} ──
                         #
                         # 一个工具要记两份东西，因为有两类"读者"：
                         #   func   → 给**程序**看的：真的执行时调哪个函数
                         #   schema → 给**模型**看的：告诉它有这么个工具、怎么用
                         #
                         # 这两份必须对得上：schema 里写的参数名（query、max_results）
                         # 要和 web_search() 的形参名一模一样，否则
                         # _run_tool() 里的 **args 就传不进去。
                         tools={"web_search": {
                             "func": web_search,
                             # ── schema 是"工具说明书"，用的是 OpenAI 的固定格式 ──
                             #
                             # 这份 JSON 会原样发给模型。模型读了才知道：
                             # "我现在可以搜网页，要传一个 query 字符串"
                             #
                             # 关键点：description 是**自然语言**，是给模型看的提示词，
                             # 你写得越清楚，模型用得越准。
                             "schema": {
                                 "type": "function",   # 固定写法，表示这是个函数调用
                                 "function": {
                                     # name 必须和上面字典的键一致
                                     "name": "web_search",
                                     # ↓ 这句直接影响模型会不会/怎么用这个工具
                                     "description": "联网搜索网页资料，返回标题+摘要+链接。用于查证事实、找最新信息。",
                                     # parameters 用 JSON Schema 描述参数：
                                     # properties 列出每个参数的名字和类型
                                     "parameters": {
                                         "type": "object",
                                         "properties": {
                                             "query": {"type": "string", "description": "搜索关键词"},
                                             "max_results": {"type": "integer", "description": "返回条数，默认3"},
                                         },
                                         # required 里的参数模型**必须**给。
                                         # max_results 不在这里，所以模型可以省略它，
                                         # 省略时就用 web_search() 自己的默认值 3。
                                         "required": ["query"],
                                     },
                                 },
                             },
                         }},
                         **kw)


# 注意 Writer 只有 3 行代码——它继承了 BaseAgent 的全部能力
# （调模型、工具循环、trace、token 统计），只是不需要工具而已。
# 这就是继承在这里的价值：换个人设就是一个新 agent。
class Writer(BaseAgent):
    """写手：根据研究摘要 + 用户需求，写结构化报告。不带工具。"""
    # prompt 里的要求写得很具体（"开头 2-3 句""用 ## 分节""结尾结论"）——
    # 这不是啰嗦，是在**降低输出的随机性**。要求越模糊，模型越自由发挥，
    # 下游的 Reviewer 就越难判断"合不合格"。
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
        # 不传 tools → 父类的 `tools or {}` 把它变成空字典，
        # _call() 里 schemas 也就是空的，于是请求里压根不带 tools 字段。
        # Writer 因此完全没有"动手"的能力，只能写字。
        super().__init__("Writer", self.ROLE, **kw)


# Reviewer 是最特殊的一个：它的输出不是给人读的文章，而是**给程序读的数据**。
#
# 这是多 agent 系统里很关键的一环：agent 之间要传递"判断结果"，
# 自由文本没法可靠地解析（模型可能写"我觉得还行"、"通过吧"、"pass!"），
# 所以强制它输出 JSON，让程序能确定性地读。
#
# 这也解释了为什么 prompt 里要强调"严格只输出这一行 JSON"——
# 模型很爱在 JSON 外面加一句"好的，这是我的评审结果："，
# 那会让 json.loads 直接失败。见下面 _parse_verdict() 的兜底处理。
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

# ── 从模型输出里"挖"出 JSON ──
#
# 为什么不能直接 json.loads(text)？
#
# 因为模型不听话。就算 prompt 里写了"严格只输出这一行 JSON"，
# 它仍然经常画出这样的东西：
#     "好的，我来评审一下这份报告。\n{"verdict": "pass", ...}\n
#      希望对你有帮助！"
# 前面有客套话，后面有总结——直接 json.loads 必然失败。
#
# 所以这里用"抓大括号"的土办法：从第一个 { 到最后一个 } 截出来再解析。
#
# 为什么是 index("{") 和 rindex("}")，而不是配对查找？
#   index  → 找**第一个** {
#   rindex → 找**最后一个** }  （r 是 reverse，从右往左找）
# 假设输出里出现了嵌套或多余的括号，取"最外层"通常是对的。
# 这是个糙但好用的启发式，够用。
#
# 失败时给一个"必 revise"的保守结果——宁可多改一轮，
# 也不要把没审过的报告放行。
def _parse_verdict(text: str) -> dict:
    try:
        start, end = text.index("{"), text.rindex("}")
        # 切片 [start:end+1]：end 位置上那个 } 要包含进来，所以 +1
        obj = json.loads(text[start:end + 1])
        # 光能解析还不够，还得检查内容是否合法。
        # 模型可能返回 {"verdict": "还行吧"} 这种解析得动但没用的东西。
        if obj.get("verdict") in ("pass", "revise"):
            return obj
        raise ValueError("verdict 字段非法")   # 主动抛，让下面统一处理
    except Exception:
        # ── 关键设计：失败时"宁严勿宽"（fail-closed）──
        #
        # 解析不出来时，默认判它 revise（要修改），而不是 pass。
        # 两种选法的代价不对称：
        #   误判成 revise → 多烧一轮 token，但报告质量有保障
        #   误判成 pass   → 一份根本没审过的报告被放行，质量失控
        # 所以选更保守的那个。
        #
        # 这个思路值得记住：当"判断失败"时，默认值应该偏向安全的一侧。
        # 下面 _default_ask_human 的"读不到输入就默认拒绝"是同一个道理。
        return {"verdict": "revise", "score": 0,
                "comments": f"（评审输出无法解析，需按文本要求重写。原文：{text[:100]}）"}


# ── 人工确认闸门 ──
#
# 这是"人在环上"（human-in-the-loop）的最小实现：程序在做一个
# **有副作用、不可撤销**的动作之前，先停下来问人。
#
# 本实现里那个"危险动作"是模拟的（"把报告发给团队"），
# 但模式是真的：真实系统里这类操作是发邮件、删数据、转账、发布上线。
#
# 为什么要做成可替换的回调（在 Supervisor 里是 self.ask_human）？
# 因为自动化测试里没法真的敲键盘——测试时传
#     ask_human=lambda q: True
# 就能跳过交互，直接模拟"用户点了同意"。
def _default_ask_human(question: str) -> bool:
    """默认人工闸门：控制台 y/N。stdin 不可读（EOF）→ 默认拒绝。"""
    print()
    print("╔══════════════════════════════════════════════════╗")
    print("║  ⚠️  危险操作需要你的确认                        ║")
    print("╚══════════════════════════════════════════════════╝")
    print(f"  {question}")
    try:
        answer = input("  允许执行吗？[y/N] ").strip().lower()
        #                                  ↑ 去掉首尾空格和换行
        #                                            ↑ 转小写，这样 Y/YES 也能认
    except (EOFError, KeyboardInterrupt):
        # EOFError：没有输入源了（比如被脚本调用、输入被重定向）
        # KeyboardInterrupt：用户按了 Ctrl+C
        # 两种都属于"问不到人" → **默认拒绝**（fail-closed，
        # 和 _parse_verdict 的保守策略一致）。绝不能因为问不到就默认放行。
        print("  （无法读取输入，默认拒绝）")
        return False

    # 只认 y / yes 两种回答。其它（包括直接回车、乱输）一律当拒绝。
    # 这是 CLI 提问的通用惯例：默认选项用大写表示（[y/N] 里的 N），
    # 意味着直接回车走 N。
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
        # 这里有 4 个"旋钮"，全都有默认值，所以可以 Supervisor() 直接跑，
        # 测试时再按需覆盖（比如 Supervisor(total_timeout=1) 测超时）。
        self.max_review_loops = max_review_loops   # 护栏 1 的上限
        self.total_timeout = total_timeout         # 护栏 2 的总时限（秒）

        # `ask_human or _default_ask_human`：传了就用传的，没传就用默认的。
        # 这是"可选参数 + 默认实现"的惯用写法，等价于：
        #     if ask_human is None: self.ask_human = _default_ask_human
        # 但一行就写完了。注意这里要写 _default_ask_human（函数本身），
        # 不能写成 _default_ask_human()（那是"立刻调用一次"）。
        self.ask_human = ask_human or _default_ask_human

        # 三个 agent 共享同一个 TraceLogger；model_fn 透传实现依赖注入。
        #
        # 关键点：三个 agent 拿到的是**同一个** logger 对象。
        # 所以三条线的记录会按真实时间顺序汇到一份 trace 里，
        # 而不是各记各的三份。这正是你想要的效果——你要看的是
        # "整个过程"，不是"每个 agent 各自的流水账"。
        #
        # model_fn 也一样透传给三个 agent：传一个假模型，
        # 三个角色就全都离线跑，一分钱不花。
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
        # ── 准备工作：重置状态，让每次 run 互不污染 ──
        #
        # Supervisor 实例是被复用的（CLI 里是一个 while 循环反复调用 run）。
        # 如果不重置，第二次运行的 trace 会和第一次混在一起，
        # token 数也会一直累加，数字全部失真。
        start_time = time.time()
        # 每次 run 用新的 logger / 清零 token，保证多轮调用互不污染
        self.tracer = TraceLogger()
        for agent in (self.researcher, self.writer, self.reviewer):
            # 三个 agent 换成新的 logger（旧的那份连同记录一起被丢弃）
            agent.tracer = self.tracer
            agent.total_tokens = 0
            agent.llm_calls = 0
        # 注意 trace_log 拿到的是新 logger 里的那个列表的**引用**，
        # 所以后面往里追加的记录，两边都能看到。
        self.trace_log = self.tracer.traces
        self.tracer.log("Supervisor", "run/start", f"用户请求：{user_request[:80]}")

        # ── 0. 输入校验（轻量分支，不烧 token）──
        #
        # 「轻量」是重点：这三条检查纯字符串操作，纳秒级完成，零成本。
        # 放在所有模型调用**之前**，就能把垃圾输入挡在门外——
        # 否则你要为一个空字符串白烧掉三次模型调用的钱。
        #
        # 这是所有 agent 系统的通用做法：**能本地判断的，别问模型**。
        clean = (user_request or "").strip()
        #                          ↑ .strip() 去掉首尾空白（空格、换行、Tab）
        # `user_request or ""` 是防 None：万一传进来的是 None，
        # 直接 .strip() 会 AttributeError，先换成空串。
        if not clean:
            return self._finish(start_time, "❌ 错误：输入为空。请描述你想研究的主题。",
                                status="bad_input")
        # any(...) 是"只要有一个满足就为真"。
        # ch.isalnum() 判断字符是不是字母或数字——所以这行的意思是
        # "整个输入里至少要有一个字母或数字"。
        # 拦的是 "🦀🦀🦀" 这种只有符号/表情的输入（对应 evals.md 第 10 条）。
        if not any(ch.isalnum() for ch in clean):
            return self._finish(start_time, "❌ 错误：输入看起来没有有效内容（只有符号/空白）。",
                                status="bad_input")
        # 长度上限：防止超长输入把 prompt 撑爆（超出模型上下文窗口会直接报错）
        if len(clean) > 2000:
            return self._finish(start_time,
                                "❌ 错误：输入过长（超过 2000 字），请精简后重试。",
                                status="bad_input")

        # ── 一个"现在超时了吗"的小工具 ──
        #
        # 这是个**闭包**（closure）：定义在 run() 内部的函数，
        # 它能直接读到外层的 start_time 和 self.total_timeout。
        # 好处是不用每次都写 `time.time() - start_time > self.total_timeout`
        # 这一长串，调用点写 `if _deadline():` 就一目了然。
        def _deadline():
            return time.time() - start_time > self.total_timeout

        # ── 1. Research 阶段 ──
        #
        # 三个阶段的结构完全一样，都是"记一笔 → 调 agent → 检查结果"。
        self.tracer.log("Supervisor", "research/start", f"派出 {self.researcher.name}")
        research = self.researcher.think(clean)
        # ── 怎么知道 agent 失败了？──
        #
        # 这里的检查方式有点"土"：看返回值是不是以特定前缀开头。
        # 因为 think() 的设计是**不抛异常**，而是把错误格式化进返回值
        # （见 BaseAgent.think() 的 except 分支）。
        # 所以只能靠"约定好的前缀"来识别。
        #
        # 这是本实现里比较粗糙的一处。更干净的做法是让 think() 返回
        # 一个 (是否成功, 内容) 的元组，或者自定义一个异常类型。
        # 用前缀的代价是：万一模型自己输出了 "[模型调用出错]" 这几个字，
        # 会被误判。实际中不太可能，但确实是隐患。
        if research.startswith("[模型调用出错]") or research.startswith("[超步]"):
            return self._finish(start_time, f"❌ Researcher 失败：{research}",
                                status="agent_error")
        self.tracer.log("Supervisor", "research/done",
                        f"研究摘要 {len(research)} 字", research[:120])
        # 阶段之间的检查点：每个阶段结束都看一眼有没有超时
        if _deadline():
            return self._finish(start_time, "❌ 超时：Research 阶段超过总时限。",
                                status="timeout")

        # ── 2. Write 阶段 ──
        #
        # ── 这就是"agent 之间怎么通信"的全部答案 ──
        #
        # 答案朴素得让人失望：**把上一个 agent 的输出，拼成字符串，
        # 当参数传给下一个**。没有消息队列、没有共享内存，
        # 就是 Supervisor 手动"转交"。
        #
        # context 里用【】把不同来源的内容隔开，是给模型看的路标——
        # 让它清楚知道"哪段是研究摘要、哪段是我的任务"。
        # 不隔开的话，两块文字糊在一起，模型容易分不清谁是谁（见 [坑 3]）。
        self.tracer.log("Supervisor", "write/start", "把研究摘要交给 Writer")
        report = self.writer.think(
            clean,                                  # 原始需求
            context=f"【研究摘要】\n{research}")     # 上游产物
        if report.startswith("[模型调用出错]") or report.startswith("[超步]"):
            return self._finish(start_time, f"❌ Writer 失败：{report}",
                                status="agent_error")
        self.tracer.log("Supervisor", "write/done",
                        f"报告草稿 {len(report)} 字", report[:120])

        # ══════════════════════════════════════════════════════
        # 3. Review 循环 —— 整个多 agent 系统最容易出事的地方
        # ══════════════════════════════════════════════════════
        #
        # ── 先看这个循环的形状：它是个状态机 ──
        #
        # `while True` + 内部 break，共有 **4 种出口**，每种给 reason
        # 赋一个不同的值，下游靠这个值判断发生了什么：
        #
        #   reason="passed"                → 评审通过（唯一的好结局）
        #   reason="max_loops_force_pass"  → 改太多次了，认输放行
        #   reason="timeout"               → 总超时，带着草稿退出
        #   reason="oscillation_force_pass"→ 评审在原地绕圈，强行放行
        #
        # 后三种都是"强制放行"，但要区分开——因为它们对最终报告的
        # 可信度影响不同，status 里会如实体现出来。
        #
        # ── 为什么必须有这些护栏？（[坑 2]）──
        #
        # 三个 agent 里，Reviewer 是唯一有"否决权"的。
        # 而模型有个很常见的毛病：**它永远能挑出毛病**。
        # 如果放任下去，就是 Reviewer 说不行 → Writer 改 → 还是不行 → ...
        # 无限循环，无限烧钱。这是多 agent 系统的头号杀手。
        #
        # 所以这里像给机器装了三道急停开关，任何一道触发就立刻停下。

        # ── 两个计数器，别搞混 ──
        #
        # review_loops：Writer **被要求改了几次**（管着护栏 1 的上限）
        # round_no    ：评审了**几轮**（只用来在 trace 里显示）
        #
        # 这两个数不是一回事！举第一个循环的例子：
        #   第 1 轮评审 → 不通过 → 改第 1 次     （round_no=1, review_loops=1）
        #   第 2 轮评审 → 不通过 → 改第 2 次     （round_no=2, review_loops=2）
        #   第 3 轮评审 → 通过了               （round_no=3, review_loops=2）
        # 收尾时 round_no=3 但 review_loops=2 —— 审了 3 轮，只改了 2 次。
        # 外部返回的是 review_loops（"改了几次"），因为那才是成本指标。
        review_loops = 0
        round_no = 0                  # 第几次评审（trace 用，含通过的那次）
        reason = "passed"             # 循环正常结束时 = 评审通过
        verdict = None
        last_comments = None          # 上一轮"要求修改"的意见，用于检测反复横跳

        while True:
            # ── 护栏 1：已经让 Writer 改满 max_review_loops 次 → 不再审，强制通过 ──
            #
            # 为什么放在循环**最顶部**？因为这样它能在每次评审前
            # 兜住所有路径——不管上一轮发生了什么，只要改的次数用完了
            # 就到此为止。放在中间或末尾都可能被某条分支绕过。
            if review_loops >= self.max_review_loops:
                reason = "max_loops_force_pass"
                self.tracer.log("Supervisor", "review/max_loops",
                                f"Writer 已改满 {self.max_review_loops} 次仍未通过，强制放行并标记")
                break

            # ── 护栏 2：总超时 → 带当前草稿退出（不再问人工）──
            #
            # 和护栏 1 的区别：护栏 1 管"改了几次"，这个管"花了多久"。
            # 两者防的是不同情况——可能只改了 1 次但每轮都很慢。
            if _deadline():
                reason = "timeout"
                self.tracer.log("Supervisor", "review/timeout",
                                "总超时，带当前草稿退出")
                break

            round_no += 1
            self.tracer.log("Supervisor", "review/round",
                            f"第 {round_no} 轮评审（当前第 {review_loops} 次修改后版本）")

            # ── 这一步：把草稿交给 Reviewer ──
            review_text = self.reviewer.think(
                clean,                                       # 原始需求（用来看有没有跑题）
                context=f"【报告草稿】\n{report}\n\n请评审。")
            # Reviewer 输出的是 JSON 文本，解析成 dict 才能用程序判断
            verdict = _parse_verdict(review_text)
            self.tracer.log("Reviewer", "verdict",
                            f"verdict={verdict['verdict']} score={verdict.get('score')}",
                            verdict.get("comments", ""), )

            # ── 出口 ①：评审通过（正常收尾）──
            if verdict["verdict"] == "pass":
                reason = "passed"
                break

            # ── 护栏 3：评审意见和上一轮一模一样 → 模型在自说自话，强制放行 ──
            #
            # 这一条最有意思，防的是一种很隐蔽的失败模式：
            # Writer 认认真真改了一版，Reviewer 却给出**字面上完全相同**的
            # 修改意见——说明它根本没看新版本，只是在重复自己的话。
            # 这时候再循环下去纯属浪费，不如放行。
            #
            # .strip() 是为了忽略首尾空白差异（"意见 " 和 "意见" 算同一句）。
            # last_comments 初始是 None，所以第一轮不会触发
            # （`if last_comments` 对 None 为假）——第一轮没有"上一轮"可比。
            comment = verdict.get("comments", "")
            if last_comments and comment.strip() == last_comments.strip():
                reason = "oscillation_force_pass"
                self.tracer.log("Supervisor", "review/oscillation",
                                "评审意见与上一轮完全相同，判定反复横跳，强制放行")
                break

            # 记住这一轮的意见，供下一轮比对
            last_comments = comment

            # ── 走到这里说明：没通过，且还有修改额度 → 让 Writer 改一版 ──
            review_loops += 1
            self.tracer.log("Supervisor", "revise/round",
                            f"第 {review_loops} 次改写，意见：{comment[:60]}")
            report = self.writer.think(
                clean,
                # ── 注意这次交给 Writer 的东西明显变多了 ──
                # 第一次写只要"研究摘要"，改写时要给三块：
                #   研究摘要   → 事实依据不能丢
                #   上一版报告 → 在它基础上改，而不是推倒重来
                #   评审意见   → 明确要改什么
                # 少给任何一块，Writer 都可能改出新问题（比如把
                # 研究摘要里的事实改没了）。
                context=f"【研究摘要】\n{research}\n\n"
                        f"【上一版报告】\n{report}\n\n"
                        f"【评审要求修改】\n{comment}\n\n请按评审意见重写报告，"
                        f"逐条回应每一条意见。")
            self.tracer.log("Writer", "revise/done",
                            f"改写完成 {len(report)} 字", report[:120])
            # 循环回到顶部 —— 但注意 report 已经被换成新版了，
            # 所以下一轮评审的是新草稿。这就是"迭代改进"的闭环。

        # ── 4. 人工确认闸门（危险操作 = "把报告作为最终交付物发出去"）──
        #
        # 模拟一个有副作用的交付动作（比如发邮件给团队）。必须人工确认才执行。
        #
        # ── 为什么超时要跳过闸门？──
        #
        # 超时意味着报告不完整（还没评审完）。这时候去问用户
        # "要不要发出去？"是在制造事故——用户可能顺手点了同意，
        # 结果发出去一份半成品。
        #
        # 所以这里的策略是：**不完整的产出根本不进入交付流程**，
        # 直接当草稿返回。宁可少做一步，也不要给用户一个
        # "把半成品发出去"的机会。
        if reason == "timeout":
            approved = False
            status = "timeout"
            self.tracer.log("Supervisor", "gate/skip", "流程超时，跳过交付闸门")
            head = "⏰ 超时未完成：以下为当前草稿（未评审完、未交付）。"
        else:
            self.tracer.log("Supervisor", "gate/ask", "交付前请用户确认（危险操作闸门）")

            # 给闸门本身也计时——用户思考的时间也算进总耗时里
            gate_ms = time.time()
            approved = self.ask_human(
                f"评审结果：{reason}。\n"
                f"是否将这份最终报告「发送给团队」作为本次交付？（模拟操作，不会真的发送）")
            gate_elapsed = (time.time() - gate_ms) * 1000
            self.tracer.log("Supervisor", "gate/result",
                            f"approved={approved}", "", gate_elapsed)

            # ── status 是怎么拼出来的 ──
            #
            # 这里用字符串拼接把两件事编码进一个字段：
            #   ① 评审结局   ok / ok(max_loops_force_pass) / ...
            #   ② 是否已交付 有无 (draft) 后缀
            #
            # 用户批准了：  status = "ok"               或 "ok(oscillation_force_pass)"
            # 用户没批准：  status = "ok(draft)"        或 "ok(oscillation_force_pass)(draft)"
            #                                         ↑ 加了 draft 后缀，表示只是草稿
            #
            # `if reason == "passed" else ...` 这个三元表达式是在说：
            # 一切正常就写干净的 "ok"；走了强制放行的路径就把原因
            # 如实标在括号里，让人一眼看出"这份报告的质量是打了折扣的"。
            #
            # 说白了：**不隐藏降级**。程序偷懒放行了，就得让人看得见。
            if approved:
                print("  ✉️  [模拟] 已向团队发送最终报告……")
                status = "ok" if reason == "passed" else f"ok({reason})"
                head = "✅ 已人工确认并交付。"
            else:
                status = "ok(draft)" if reason == "passed" else f"ok({reason})(draft)"
                head = "🕐 未获人工确认——报告保留为草稿，未发送。"

        # 最后把这段"说明头"和正文拼起来，让用户一眼知道这份东西的状态
        final_report = f"{head}\n\n{report}"

        # ── 5. 汇总返回 ──
        # 把三个 agent 各自的 token 账加起来。因为每次 run 开头都清零过，
        # 所以这三个数只统计本次 run，不会被上一轮污染。
        elapsed = time.time() - start_time
        total_tokens = (self.researcher.total_tokens
                        + self.writer.total_tokens
                        + self.reviewer.total_tokens)
        self.tracer.log("Supervisor", "run/done",
                        f"评审轮数={review_loops} token={total_tokens} "
                        f"耗时={elapsed:.1f}s 状态={status}")
        # 返回一个结构化的字典，而不是一段文本——
        # 这样调用方（CLI 或自动化测试）能按需取用：
        # 想展示就取 final_report，想统计成本就取 total_tokens，
        # 想排查问题就取 trace。塞成一大段字符串就没法这么用了。
        return {
            "final_report": final_report,
            "review_loops": review_loops,
            # status 是"结局 + 是否交付"的组合串（见上面那段注释）
            "status": status,
            # reason 只记"循环为什么结束"，不含交付信息，是两个维度
            "reason": reason,
            "gate_approved": approved,
            "trace": self.trace_log,
            # round 保留 2 位小数，避免一堆 45.2384716 这种没意义的精度
            "total_time": round(elapsed, 2),
            "total_tokens": total_tokens,
        }

    # ── 提前终止的公共出口 ──
    #
    # run() 里有 5 个地方会"半路退出"（空输入、只含符号、超长、
    # 某个 agent 失败、超时），它们全都调这个方法收尾。
    #
    # 为什么要抽出来？两个理由：
    #
    # ① **返回值结构必须一致**。调用方（CLI、评测脚本）拿到的永远是
    #    同样几个键，不用写一堆 if 判断"这次是正常结束还是异常结束"。
    #    看返回的 status 字段就知道。
    #
    # ② 返回的字典结构要和 run() 正常结束时的**完全一样**。
    #    如果这里少一个键，调用方取 result["gate_approved"] 就会 KeyError。
    #    用同一个方法收尾，就不会漏。
    #
    # 注意 total_tokens 写死 0：能走到这里说明要么还没开始调模型，
    # 要么是中途失败，没必要去统计一个不完整的数字。
    def _finish(self, start_time, report: str, status: str) -> dict:
        elapsed = time.time() - start_time
        # 注意这里是 .append 而不是通过 tracer.log()——
        # 因为格式和 TraceLogger.log 不完全一样（这里没有 agent 名字等），
        # 就直接往列表里塞一条原始记录。
        self.trace_log.append({
            "timestamp": time.strftime("%H:%M:%S"),
            "agent": "Supervisor",
            "action": f"run/{status}",     # 比如 "run/bad_input"
            "detail": "提前终止（不烧 token）",
            "result_preview": report[:120],
            "elapsed_ms": 0,
        })
        return {
            "final_report": report,
            "review_loops": 0,             # 压根没走到评审阶段，当然是 0
            "status": status,
            # 这里 reason 直接等于 status。在提前终止的场景下，
            # "为什么结束"和"结局是什么"是同一件事，没必要分开。
            "reason": status,
            "gate_approved": False,        # 没交付
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

    # ── 提前验证 key ──
    #
    # 这是"早失败"（fail fast）原则：与其让用户输完问题、
    # 等三个 agent 跑到一半才炸出一个看不懂的报错，
    # 不如在开始前就检查好，用一句人话告诉他"你没配 key，这样配"。
    #
    # 这也是模块 0 那个惰性设计的好处：create_client() 可以
    # 在任何时候被手工调用一次，就为了提前探雷。
    try:
        create_client()
    except RuntimeError as e:
        # 只捕 RuntimeError——那是 create_client() 自己抛的"没配 key"。
        # 其它异常（比如没装 openai 库）不在这里处理，让它照常报出来，
        # 免得把真问题也伪装成"你没配 key"。
        print(f"❌ {e}")
        print("（设好 key 再跑：$env:DEEPSEEK_API_KEY = 'sk-你的key'）")
        return   # 函数返回值是 None，等于退出

    supervisor = Supervisor()

    print("输入你想研究的问题（空行退出）：")
    print("提示：你可以先空跑体验角色协作，也可以随便问一个问题。")
    print("-" * 55)

    # ── 一个最朴素的 REPL（读-算-打印 循环）──
    #
    # Supervisor 实例建在循环**外面**，只建一次，循环里反复调用
    # run()。前面说过 run() 开头会重置状态，所以复用是安全的。
    while True:
        try:
            user_input = input("\n你 > ").strip()
        except (EOFError, KeyboardInterrupt):
            # 用户按了 Ctrl+C 或输入被重定向到空 → 优雅退出，
            # 而不是甩一个大红报错。
            print("\n再见！")
            break

        # ── 三种退出方式，随便哪种都行 ──
        if not user_input:          # ① 直接敲回车（空行）
            break
        if user_input.lower() in ("quit", "exit"):   # ② 输入 quit / exit
            break

        print("\n⏳ 三个 agent 协作中……\n")
        result = supervisor.run(user_input)

        # ── 展示结果：正文 + 一行统计 + 完整 trace ──
        print("\n" + "=" * 55)
        print("最终报告")
        print("=" * 55)
        print(result["final_report"])
        print()
        # 这一行把本次运行的四个关键指标摊开：
        # status 里能看出是不是强制放行的、有没有交付（见 run() 里的注释）
        print(f"—— 状态：{result['status']} | 评审轮数：{result['review_loops']} | "
              f"耗时 {result['total_time']}s | token {result['total_tokens']} ——")
        print()
        # 完整的调用链，用来复盘"每个 agent 到底干了什么"
        print(supervisor.tracer.report())
        print()


# ── 这一行是干什么的？──
#
# Python 里每个 .py 文件都可以被两种方式使用：
#   ① 直接运行：python main.py        → __name__ 的值是 "__main__"
#   ② 被别人 import：import main      → __name__ 的值是 "main"
#
# 这个判断的意思是："只有被直接运行时才执行 main()"。
#
# 少了这一行会怎样？别人 `import main`（比如写测试、或者复用里面的
# Supervisor 类）时，CLI 界面会**立刻弹出来开始问你问题**——
# import 一个模块却触发了交互，非常糟糕。
#
# 这也是为什么这个文件能被当库用、也能当程序跑。
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
