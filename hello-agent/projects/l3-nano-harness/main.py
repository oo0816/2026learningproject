"""
L3 · Nano Harness — 从 Agent 到 Harness
=========================================

## 什么是 Harness？

你写的 L1/L2 agent 是一个"裸奔"的 agent loop——工具调用、记忆管理、消息收发
全部揉在一起。这在 demo 阶段够用，但加功能时会越来越乱。

Harness 就是"把 agent loop 拆成可替换的模块"。一个现代 agent harness 通常有：

```
┌──────────────────────────────────────────┐
│               Harness 架构               │
│                                          │
│  ┌──────────┐  ┌──────────┐  ┌────────┐ │
│  │  Agent   │  │  Tool    │  │Permission│ │
│  │  Loop    │──│  Registry│──│  Gate   │ │
│  └──────────┘  └──────────┘  └────────┘ │
│       │              │            │      │
│  ┌──────────┐  ┌──────────┐  ┌────────┐ │
│  │ Session  │  │  Context │  │  Error  │ │
│  │  Store   │  │ Compactor│  │ Logger  │ │
│  └──────────┘  └──────────┘  └────────┘ │
└──────────────────────────────────────────┘
```

L3 的目标：把你的 L1 agent 升级成一个模块化的 nano harness。

## L3 对比 L1/L2

| 模块 | L1 | L2 | L3 |
|------|----|----|-----|
| Agent Loop | 写死在 main.py | 写死在 main.py | 独立的 Agent 类 |
| 工具管理 | dict 散落 | TOOL_REGISTRY | ToolRegistry 类（注册/查找/校验） |
| 权限 | 无 | risk_level 标记 | PermissionGate（safe/needs_approval/blocked） |
| 会话存储 | 无 | SessionMemory | SessionStore（保存/恢复/多会话） |
| 上下文管理 | 无 | manage_context_window() | ContextCompactor（压缩策略可配置） |
| 错误日志 | print() | print() | 分级日志（INFO/WARN/ERROR）+ 调用链追踪 |

## 你要实现什么

不要求从零写。以你 L1 的 main.py 为起点，逐步模块化：

1. **ToolRegistry 类**：替代 TOOLS_MAP dict
   - register(tool): 注册工具，校验 schema 必填字段
   - get(name): 按名称查找
   - get_schemas(): 返回所有 schema
   - list(): 列出所有已注册工具

2. **PermissionGate 类**：替代 risk_level 字符串
   - 三级：SAFE（自动）/ NEEDS_APPROVAL（需确认）/ BLOCKED（拒绝）
   - check(tool_name): 返回是否允许执行
   - 可配置规则（如：所有文件删除操作 = BLOCKED）

3. **SessionStore 类**：替代 SessionMemory
   - save(session_id, messages): 保存对话到 JSON 文件
   - load(session_id): 恢复对话
   - list_sessions(): 列出所有已保存的会话

4. **结构化日志**：
   - 每条日志包含：时间戳、级别、模块名、消息
   - 记录每次工具调用的：工具名、参数、结果（前 100 字）、耗时

## 必答问题（边写边想）

- agent loop 在哪个文件？核心逻辑多少行？（对比 learn-claude-code 或 claw0）
拆成骨架模块化
- 工具是怎么注册的？tool schema 包含哪些字段？
register(name, func, schema, risk_level)，注册时校验（schema 必须有 function 键、
function 内有 name/description/parameters、parameters.type == "object"、不能重名）。
- 权限控制在哪里？每次调工具都要确认还是分级别？
分级别，问询，risklevel
- session 是怎么存、怎么恢复的？
json文件
- 上下文太长时怎么压缩？触发条件是什么？
按token约束 论数估计不准确，而且是约数，不卡硬要求
"""

import os
import sys
import re
import json
import time
import fnmatch
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional
from openai import OpenAI

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass  # 某些环境（重定向/无终端）不支持 reconfigure，忽略即可

# ══════════════════════════════════════════════════════════════
# 模块 0：模型连接（从 L1/L2 迁移，但改成惰性加载）
# ══════════════════════════════════════════════════════════════
# L1/L2 在模块顶层就解析 API key 并 exit(1)。
# L3 把它改成函数：只有真正要跑 agent 时才解析。
# 好处：import main.py 跑离线单元测试时不需要 API key。
#       ——这本身就是一个"harness 化"：配置加载和业务逻辑解耦。

MODEL = "deepseek-chat"
BASE_URL = "https://api.deepseek.com"


def _resolve_api_key() -> Optional[str]:
    """
    解析 API key：先看环境变量，取不到再从 Windows 注册表读用户变量。

    Windows 下 os.environ 偶尔拿不到用户变量（和终端启动方式有关），
    但注册表一定有。L1/L2 已踩过这个坑，这里直接沿用兜底。
    """
    key = os.environ.get("DEEPSEEK_API_KEY")
    if key:
        return key
    try:
        import winreg#读取注册表
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as k:
            key, _ = winreg.QueryValueEx(k, "DEEPSEEK_API_KEY")
        return key
    except Exception:#不对的话返回none避免崩溃
        return None


def create_client() -> OpenAI:
    """创建 OpenAI 兼容客户端；没配 key 时抛错（由调用方决定怎么处理）"""
    key = _resolve_api_key()
    if not key:
        raise RuntimeError(
            "未找到 DEEPSEEK_API_KEY\n请运行：$env:DEEPSEEK_API_KEY = 'sk-你的key'"
        )
    return OpenAI(api_key=key, base_url=BASE_URL)


# ══════════════════════════════════════════════════════════════
# 模块 1：ToolRegistry — 工具注册表
# ══════════════════════════════════════════════════════════════

class ToolRegistry:
    """
    工具注册表：注册、查找、校验、导出 schema。

    比 L2 的 TOOL_REGISTRY dict 多了什么？
    - schema 校验：注册时检查必填字段（name, description, parameters）
    - 防重复注册：同名工具注册两次时警告或拒绝
    - 分类管理：按 risk_level 或功能分组

    设计思考：
    - 为什么注册时校验而不在调用时校验？
      → 尽早暴露配置错误。工具注册是启动阶段，调用是运行阶段——前者出错更好排查。

    - Registry 和 PermissionGate 的边界（对照真实 harness）：
      Registry 只回答"这个工具存在吗？怎么调用？"，
      PermissionGate 只回答"这个工具现在能调吗？"。
      所以 Registry.execute() 里不做任何权限判断——权限归 Gate，
      由外层 Agent 在调用前先问 Gate。两个模块零耦合。
    """

    # 注册项内部结构：{name, func, risk_level, schema}
    # risk_level 沿用 L2 的三档：safe / needs_approval / blocked

    def __init__(self):
        self.tools: dict[str, dict] = {}
        self.last_error: Optional[str] = None

    def register(self, name: str, func: Callable, schema: dict,
                 risk_level: str = "safe") -> bool:#返回的是有没有成功
        """
        注册一个工具。

        校验项：
        - schema 必须有 "function" 键
        - function 内必须有 name, description, parameters
        - parameters.type 必须是 "object"
        - schema 里的 function.name 必须和 name 参数一致（防止注册时写串）
        - 不能和已有工具重名
        - risk_level 必须是三档之一

        返回 True 表示注册成功，False 表示失败。
        失败原因存在 self.last_error，方便调用方打日志。
        """
        # 1. 防重复注册（覆盖注册会悄悄改掉行为，容易查不出 bug）
        if name in self.tools:
            self.last_error = f"工具 '{name}' 重复注册，已拒绝（如需覆盖请先 unregister）"
            return False

        # 2. schema 结构校验——逐层拆，哪层缺了告诉哪层
        if not isinstance(schema, dict) or "function" not in schema:
            self.last_error = f"工具 '{name}' 的 schema 缺少 'function' 键"
            return False

        fn = schema["function"]
        for field in ("name", "description", "parameters"):
            if field not in fn:
                self.last_error = f"工具 '{name}' 的 schema function 缺少 '{field}'"
                return False

        if fn["name"] != name:
            self.last_error = (
                f"工具 schema 的 function.name '{fn['name']}' "
                f"和注册名 '{name}' 不一致"
            )
            return False

        params = fn["parameters"]
        if not isinstance(params, dict) or params.get("type") != "object":
            self.last_error = f"工具 '{name}' 的 parameters.type 必须是 'object'"
            return False

        # 3. risk_level 校验
        if risk_level not in ("safe", "needs_approval", "blocked"):
            self.last_error = (
                f"工具 '{name}' 的 risk_level '{risk_level}' 无效，"
                f"必须是 safe / needs_approval / blocked"
            )
            return False

        # 4. 全部通过，入库
        self.tools[name] = {
            "name": name,
            "func": func,
            "risk_level": risk_level,
            "schema": schema,
        }
        self.last_error = None
        return True

    def get(self, name: str) -> Optional[dict]:
        """按名称查找工具，找不到返回 None"""
        return self.tools.get(name)

    def get_schemas(self) -> list[dict]:
        """返回所有工具的 OpenAI function calling schema"""
        return [t["schema"] for t in self.tools.values()]

    def list_tools(self) -> list[str]:
        """列出所有已注册的工具名"""
        return list(self.tools.keys())

    def execute(self, name: str, args: dict) -> str:
        """
        执行工具并返回字符串结果——带错误分类，绝不抛异常。

        注意：这里只做"执行层"的错误处理（找不到工具 / 参数错 / 异常 / 空结果），
        不做权限判断（那是 PermissionGate 的职责，由 Agent 调用前先问）。

        错误分类沿用 L2：
        1. 工具不存在 → 报错 + 列出可用工具
        2. 参数不匹配 → TypeError，告诉模型正确参数格式
        3. 执行异常 → 返回异常类型和消息（模型看到后可换种方式重试）
        4. 空结果 → 加警告提示
        """
        tool = self.tools.get(name)
        if tool is None:
            available = ", ".join(self.list_tools())
            return f"[工具错误] 未知工具 '{name}'。可用工具：{available}"

        try:
            start = time.time()
            result = tool["func"](**args)
            elapsed = time.time() - start
        except TypeError as e:
            params = tool["schema"]["function"]["parameters"]
            return (
                f"[工具错误] '{name}' 参数不匹配：{e}\n"
                f"期望参数格式：{params}"
            )
        except Exception as e:
            return f"[工具错误] '{name}' 执行异常：{type(e).__name__}: {e}"

        if elapsed > 10:
            return f"[工具警告] '{name}' 耗时 {elapsed:.1f}s，结果可能不完整。\n\n{result}"
        if result is None or (isinstance(result, str) and result.strip() == ""):
            return f"[工具警告] '{name}' 返回了空结果，可能需要换一种查询方式。"
        return str(result)


# ══════════════════════════════════════════════════════════════
# 模块 2：PermissionGate — 权限控制
# ══════════════════════════════════════════════════════════════

class PermissionGate:
    """
    权限控制闸门。

    三级权限：
    - ALLOW: 自动执行（读操作、计算）
    - ASK: 需要用户确认（发邮件、修改文件）
    - DENY: 完全禁止（rm -rf、drop table）

    两种实现方式（L3 先做 A，L5 升级到 B）：
    A) 规则匹配：按工具名/关键词/risk_level 匹配
    B) 动态策略：每次调用时根据上下文决定（参数内容、调用历史等）

    check(tool_name) 只收到工具名，怎么知道它的 risk_level？
    → Registry 和 Gate 不互相调用（保持独立）。risk_level 由外层 Agent
      在调用 check 时作为参数带进来。这对应真实 harness 的写法：
      harness 把"工具定义"作为上下文喂给 permission checker。
    """

    ALLOW = "allow"
    ASK = "ask"
    DENY = "deny"

    # risk_level（L2 的标记）→ 闸门动作 的默认映射。
    # 这就是把 L2 的"纸上分级"变成 L3 的"真正拦截"的那一步。
    RISK_DEFAULT = {
        "safe": ALLOW,            # 读操作/计算 → 自动
        "needs_approval": ASK,    # 有副作用 → 先问用户
        "blocked": DENY,          # 危险操作 → 直接拒绝
    }

    def __init__(self, default_action: str = "deny"):
        """
        default_action：没有任何规则命中、也不知道 risk_level 时的兜底行为。

        设计选择（README 必答问题之一）：
        - 默认 DENY（白名单模式）：更安全。新工具默认不可用，显式加规则才放行。
        - 默认 ALLOW（黑名单模式）：更方便，但危险工具一旦漏配规则就被放行。
        → L3 选默认 DENY。理由：权限系统出错的方向应该是"拒绝过度"而不是
          "放行过度"——前者只是不好用，后者是真的安全事故。
        """
        # 规则格式：{"pattern": "web_search", "action": "allow"}
        # pattern 支持通配符，如 "file_delete*"（用 fnmatch 匹配）
        self.rules: list[dict] = []
        self.default_action = default_action

    def add_rule(self, pattern: str, action: str) -> bool:
        """
        添加一条权限规则。

        pattern 既可以是工具名（web_search、file_delete*），
        也可以是 risk_level 关键字（safe / needs_approval / blocked），
        check 时两种都会尝试匹配。返回是否添加成功。
        """
        if action not in (self.ALLOW, self.ASK, self.DENY):
            print(f"  ✗ 规则添加失败：未知动作 '{action}'")
            return False
        self.rules.append({"pattern": pattern, "action": action})
        return True

    def _matches(self, pattern: str, target: str) -> bool:
        """fnmatch 做通配符匹配（大小写不敏感），'*' '?' 都支持"""
        return fnmatch.fnmatchcase(target.lower(), pattern.lower())

    def check(self, tool_name: str, risk_level: Optional[str] = None) -> str:
        """
        检查工具是否可以执行。返回 "allow" | "ask" | "deny"。

        匹配优先级（重要，决定了规则的覆盖能力）：
        1. 用户显式规则（按添加顺序，第一个命中的生效）→ 用户规则永远能覆盖默认行为
        2. 没规则命中 → 用 risk_level 对应的默认动作（safe→allow 等）
        3. 连 risk_level 都不知道 → 用 default_action（默认 deny）

        为什么"显式规则 > risk 默认"？
        → 例：web_search 默认 safe（allow），但某天你想彻底禁用搜索，
          加一条 add_rule("web_search", "deny") 就能压过默认行为。
          反过来，想放行一个 blocked 工具，同样加一条 allow 规则即可。
        """
        # 显式规则优先：先匹配工具名，再匹配 risk_level 关键字
        for rule in self.rules:
            pattern, action = rule["pattern"], rule["action"]
            if self._matches(pattern, tool_name):
                return action
            if risk_level and self._matches(pattern, risk_level):
                return action

        # 没规则命中 → risk_level 默认 → default_action 兜底
        if risk_level in self.RISK_DEFAULT:
            return self.RISK_DEFAULT[risk_level]
        return self.default_action

    def request_approval(self, tool_name: str, args: dict) -> bool:
        """
        ASK 级别的工具需要用户确认。
        L3 简化实现：打印工具名和参数，等待用户输入 y/n。

        - 输入 y / yes → True（放行）
        - 输入 n / no / 直接回车 → False（拒绝）
        - stdin 不可读（EOF，比如被脚本调用）→ False
          → 拿不到用户决定时默认拒绝，永远不让"无人确认的高危操作"溜过去。
        """
        print()
        print("╔══════════════════════════════════════════════════╗")
        print("║  ⚠️  工具需要你的确认                            ║")
        print("╚══════════════════════════════════════════════════╝")
        print(f"  工具：{tool_name}")
        try:
            pretty_args = json.dumps(args, ensure_ascii=False, indent=2)
        except (TypeError, ValueError):
            pretty_args = str(args)
        print(f"  参数：{pretty_args}")
        try:
            answer = input("  允许执行吗？[y/N] ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print("  （无法读取输入，默认拒绝）")
            return False
        return answer in ("y", "yes")

    def describe(self) -> str:
        """把当前规则和默认行为格式化出来，供 /rules 命令查看"""
        lines = ["默认行为：" + self.default_action + "（无规则且未知风险等级时）"]
        lines += ["risk 默认映射：safe→allow | needs_approval→ask | blocked→deny"]
        if not self.rules:
            lines.append("显式规则：（无）")
        else:
            lines.append("显式规则：")
            for r in self.rules:
                lines.append(f"  - {r['pattern']} → {r['action']}")
        return "\n".join(lines)


# ══════════════════════════════════════════════════════════════
# 模块 3：SessionStore — 会话存储
# ══════════════════════════════════════════════════════════════

class SessionStore:
    """
    会话存储：把对话历史存到磁盘，下次启动能恢复。

    存储目录：./sessions/（main.py 同级目录，和 L2 的
    long_term_memory.json 放一起的约定保持一致，不依赖启动时的 cwd）
    每个会话一个 JSON 文件：sessions/{session_id}.json

    文件结构：
    {
      "session_id": "20260720-143000",
      "created_at": "2026-07-20T14:30:00",
      "updated_at": "2026-07-20T15:00:00",
      "messages": [
        {"role": "user", "content": "你好"},
        {"role": "assistant", "content": "你好！有什么可以帮助你的？"},
        ...
      ],
      "metadata": {
        "tool_call_count": 5,
        "user_name": "张三"  // 从 session memory 提取的
      }
    }

    关键设计决策：
    - 什么时候保存？每次对话轮次后自动保存？还是用户手动 /save？
      → L3 选"每轮对话结束后自动保存一次"。理由：崩溃最多丢当前这轮的
        中间过程，不会丢整段历史；而每调一次工具就写盘太频繁（一次对话
        可能要写 3-5 次盘）。
    - 如果 messages 有 500 条（几万 token），每次保存都写整个文件会不会太慢？
      → 会，但 L3 的规模（单用户、几十轮）完全可以接受。
        先保证正确性和可读性，性能问题留到真的出现时再优化
        （升级方向：增量追加日志 / 只写最近 N 轮 + 定期归档 / SQLite）。
    - 多个会话同时存在时，怎么区分？
      → session_id = 创建时间（yyyyMMdd-HHmmss-毫秒），天然有序且不重复。
    """

    def __init__(self, base_dir: Optional[str] = None):
        if base_dir is None:
            base_dir = Path(__file__).parent / "sessions"
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    # ── 内部工具 ──────────────────────────────────────────
    @staticmethod
    def _valid_session_id(session_id: str) -> bool:
        """session_id 只允许字母/数字/下划线/短横线，防止路径穿越（../ 注入）"""
        return bool(re.fullmatch(r"[\w\-]+", session_id or ""))

    def _path(self, session_id: str) -> Path:
        if not self._valid_session_id(session_id):
            raise ValueError(f"非法的 session_id：{session_id!r}")
        return self.base_dir / f"{session_id}.json"

    def _load_raw(self, session_id: str) -> Optional[dict]:
        p = self._path(session_id)
        if not p.exists():
            return None
        try:
            with open(p, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            # 文件损坏：宁可不恢复也不让整个 agent 崩掉
            return {"session_id": session_id, "messages": [], "corrupt": True}

    @staticmethod
    def new_session_id() -> str:
        """生成新会话 id：20260720-143000-123（时间+毫秒，防同一秒连建冲突）"""
        return datetime.now().strftime("%Y%m%d-%H%M%S") + f"-{int(time.time() * 1000) % 1000:03d}"

    # ── 对外接口 ──────────────────────────────────────────
    def save(self, session_id: str, messages: list[dict],
             metadata: Optional[dict] = None) -> bool:
        """
        保存/更新一个会话。已存在的会话保留 created_at，只更新 updated_at。

        原子写：先写临时文件再 os.replace，防止写一半断电导致 JSON 损坏。
        """
        now = datetime.now().isoformat(timespec="seconds")
        old = self._load_raw(session_id)
        data = {
            "session_id": session_id,
            "created_at": (old or {}).get("created_at", now),
            "updated_at": now,
            "messages": messages,
            "metadata": metadata or {},
        }
        # 老会话的 metadata 也保留（比如累计的 tool_call_count）
        if old and old.get("metadata"):
            merged = dict(old["metadata"])
            merged.update(metadata or {})
            data["metadata"] = merged

        p = self._path(session_id)
        tmp = p.with_suffix(".json.tmp")
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            os.replace(tmp, p)
            return True
        except IOError:
            return False

    def load(self, session_id: str) -> Optional[dict]:
        """
        恢复一个会话：返回完整数据 dict（含 messages / metadata），
        找不到返回 None。只有 messages 的取法由调用方决定。
        """
        data = self._load_raw(session_id)
        return data if data and not data.get("corrupt") else data

    def list_sessions(self) -> list[dict]:
        """
        列出所有会话，按最近更新排序。
        每条：{session_id, updated_at, message_count, preview}
        preview = 最后一条 user 消息的前 60 字（帮你认出这是哪个会话）
        """
        sessions = []
        for f in sorted(self.base_dir.glob("*.json"), key=lambda p: p.stat().st_mtime,
                        reverse=True):
            if f.name.endswith(".tmp"):
                continue
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, IOError):
                continue
            msgs = data.get("messages", [])
            preview = ""
            for m in reversed(msgs):
                if m.get("role") == "user":
                    preview = str(m.get("content", ""))[:60]
                    break
            sessions.append({
                "session_id": data.get("session_id", f.stem),
                "updated_at": data.get("updated_at", "?"),
                "message_count": len(msgs),
                "preview": preview,
            })
        return sessions

    def delete(self, session_id: str) -> bool:
        """删除一个会话（/delete 命令用）"""
        p = self._path(session_id)
        if p.exists():
            p.unlink()
            return True
        return False


# ══════════════════════════════════════════════════════════════
# 模块 4：结构化日志
# ══════════════════════════════════════════════════════════════

class Logger:
    """
    简单的分级日志。

    L1/L2 全程 print()，跑完根本不知道"它内部到底调了什么"。
    L3 换成分级日志：每条日志包含 时间戳、级别、模块名、消息，
    同时打屏幕 + 落盘（logs/agent.log），出问题能回查。

    级别：
    - INFO：正常流程（step、工具调用）
    - WARN：可恢复的异常（文件损坏、工具超时、被拒绝）
    - ERROR：应该被注意到的问题（API 调用失败等）
    """

    LEVELS = ("INFO", "WARN", "ERROR")

    def __init__(self, log_file: Optional[str] = None, console: bool = True):
        if log_file is None:
            log_dir = Path(__file__).parent / "logs"
            log_dir.mkdir(parents=True, exist_ok=True)
            log_file = log_dir / "agent.log"
        self.log_file = Path(log_file)
        self.log_file.parent.mkdir(parents=True, exist_ok=True)
        self.console = console

    def _emit(self, level: str, module: str, msg: str):
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        line = f"[{ts}] [{level}] [{module}] {msg}"
        if self.console:
            try:
                print(line)
            except Exception:
                pass  # 打印失败（如 stdout 已关闭）不影响主流程
        try:
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(line + "\n")
        except IOError:
            pass

    def info(self, msg: str, module: str = "harness"):
        self._emit("INFO", module, msg)

    def warn(self, msg: str, module: str = "harness"):
        self._emit("WARN", module, msg)

    def error(self, msg: str, module: str = "harness"):
        self._emit("ERROR", module, msg)

    def tool_call(self, name: str, args: dict, result: str, elapsed: float,
                  module: str = "tool"):
        """
        记录一次工具调用：工具名、参数、结果（前 100 字）、耗时。

        为什么结果只记前 100 字？
        → 日志是给人排查用的：知道"调了谁、给了什么、成败如何"就够定位问题了。
          完整结果已经在对话历史里（会喂回给模型），不需要在日志里再存一份大的。
        """
        try:
            args_str = json.dumps(args, ensure_ascii=False)
        except (TypeError, ValueError):
            args_str = str(args)
        if len(args_str) > 200:
            args_str = args_str[:200] + "…"
        result_str = (result or "")[:100].replace("\n", " ")
        self._emit(
            "INFO", module,
            f"{name} args={args_str} → {result_str} ({elapsed * 1000:.0f}ms)",
        )


# ══════════════════════════════════════════════════════════════
# 内置工具（从 L1/L2 迁移）
# ══════════════════════════════════════════════════════════════
# 工具函数本身和 L1/L2 一样，区别在于：
# - 每个工具现在带 risk_level（safe / needs_approval / blocked）
# - 工具的元数据（schema + risk）统一进 ToolRegistry，由 Agent 在启动时注册
# - PermissionGate 按 risk_level 决定 allow / ask / deny

def calculator(expression: str) -> str:
    """
    安全计算数学表达式（risk: safe）。

    安全策略：字符白名单 + 禁用 builtins。
    不是 100% 安全，但对学习场景足够了——真要做隔离，L6 起换沙箱。
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
    """获取城市天气（模拟数据，risk: safe）。L5+ 可替换为真实天气 API。"""
    data = {
        "北京": "北京：5°C，晴朗，北风3级",
        "上海": "上海：12°C，多云，东风2级",
        "深圳": "深圳：20°C，小雨，南风1级",
        "杭州": "杭州：10°C，阴，微风",
    }
    return data.get(city, f"{city}：暂无天气数据（模拟服务）")


# 搜索库没装时优雅降级，不 import 失败
_SEARCH_AVAILABLE = False
try:
    from duckduckgo_search import DDGS
    _SEARCH_AVAILABLE = True
except ImportError:
    pass


def web_search(query: str, max_results: int = 3) -> str:
    """联网搜索（risk: safe）。结果截断，防止塞爆上下文。"""
    if not _SEARCH_AVAILABLE:
        return ("搜索功能不可用：请先安装 duckduckgo_search\n"
                "运行：pip install duckduckgo_search")
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
    except Exception as e:
        return f"搜索失败（网络错误或 API 限流）：{e}"
    if not results:
        return f"搜索「{query}」未找到相关结果。建议：换一个更具体的关键词试试。"
    lines = []
    for i, r in enumerate(results, 1):
        title = r.get("title", "无标题")
        href = r.get("href", "")
        body = r.get("body", "")[:200]
        lines.append(f"{i}. {title}\n   {body}\n   {href}")
    return "\n\n".join(lines)


def send_email(to: str, subject: str, body: str) -> str:
    """
    发送邮件（risk: needs_approval！演示用，实际不联网）。

    为什么这个工具要标 needs_approval 而不是 safe？
    → 它有副作用（真的会给别人发邮件）。即使本 demo 是模拟的，
      也要养成习惯：有副作用的操作永远不能静默自动执行。
    """
    # 模拟发送前的校验，体现"就算放行，也要做参数合法性检查"
    if "@" not in to:
        return f"[工具错误] 收件人格式不合法：{to}（示例：a@example.com）"
    print(f"  ✉️  [模拟] 正在向 {to} 发送邮件……")
    return f"[模拟] 已向 {to} 发送邮件，主题：{subject}"


# 工具清单：name + schema + risk_level，Agent 启动时循环注册
# 加第 N 个工具 = 加一个函数 + 加一条记录，Agent 和 loop 一行都不用改
TOOL_DEFINITIONS = [
    {
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
    {
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
    {
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
                        "query": {"type": "string", "description": "搜索关键词"},
                        "max_results": {
                            "type": "integer", "description": "返回结果数量，默认3"},
                    },
                    "required": ["query"],
                },
            },
        },
    },
    {
        "name": "send_email",
        "func": send_email,
        "risk_level": "needs_approval",
        "schema": {
            "type": "function",
            "function": {
                "name": "send_email",
                "description": "发送邮件给指定收件人（当前为模拟实现）",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "to": {"type": "string", "description": "收件人邮箱"},
                        "subject": {"type": "string", "description": "邮件主题"},
                        "body": {"type": "string", "description": "邮件正文"},
                    },
                    "required": ["to", "subject", "body"],
                },
            },
        },
    },
]


# ══════════════════════════════════════════════════════════════
# 模块 5：Agent 类 — 把所有模块组装起来
# ══════════════════════════════════════════════════════════════

class Agent:
    """
    模块化的 Agent。

    和 L1 的 run_agent() 函数有什么区别？
    - L1：一个函数干了所有事（调模型、查工具 dict、塞消息、打印）
    - L3：Agent 类持有 ToolRegistry、PermissionGate、SessionStore、Logger，
         但自己不实现它们——只负责"编排"。

    一次工具调用在 L3 的完整链路（对比 L1 的直接执行）：
      模型说要调 web_search
        → Agent 查 ToolRegistry.get("web_search")    这个工具有吗？
        → Agent 问 PermissionGate.check(名字, risk)  现在能调吗？
             allow → 直接执行
             ask   → PermissionGate.request_approval() 问用户
             deny  → 返回 [权限拒绝]
        → ToolRegistry.execute() 真正执行（只做错误处理，不做权限）
        → Logger.tool_call() 记录这次调用（名字/参数/结果前100字/耗时）
        → 结果塞回 messages，继续下一轮

    这符合"单一职责原则"：每个类只做一件事，Agent 类负责编排。
    """

    MAX_STEPS = 10          # 最多调多少轮模型（L1 沿用的护栏）
    TIMEOUT = 60            # 总超时（L2 放宽到 60s，因为 web_search 可能慢）
    CONTEXT_MAX_TURNS = 12  # 上下文压缩触发：超过 12 轮对话就裁剪
    CONTEXT_MAX_CHARS = 30000  # 上下文压缩触发：消息总量超过约 3 万字符也裁剪

    def __init__(self, client: OpenAI, model: str = MODEL,
                 register_default_tools: bool = True):
        # 所有模块在 Agent 里组装
        self.client = client
        self.model = model
        self.tool_registry = ToolRegistry()
        self.permission_gate = PermissionGate(default_action="deny")
        self.session_store = SessionStore()
        self.logger = Logger()

        # 会话状态（Agent 进程内只活跃一个会话）
        self._history: list[dict] = []      # 当前会话的完整消息
        self._session_id: Optional[str] = None

        if register_default_tools:
            self._register_builtin_tools()

    # ── 工具注册 ──────────────────────────────────────────
    def _register_builtin_tools(self):
        """注册内置工具；注册失败的项打日志但不让整个 agent 挂掉"""
        for td in TOOL_DEFINITIONS:
            ok = self.tool_registry.register(
                td["name"], td["func"], td["schema"], td["risk_level"])
            if ok:
                self.logger.info(
                    f"注册工具 '{td['name']}'（risk={td['risk_level']}）",
                    module="registry")
            else:
                self.logger.error(
                    f"工具 '{td['name']}' 注册失败：{self.tool_registry.last_error}",
                    module="registry")

    def register_tool(self, name: str, func: Callable, schema: dict,
                      risk_level: str = "safe") -> bool:
        """运行时注册自定义工具（Agent 的开放扩展点）加外带工具，类似于读文件"""
        ok = self.tool_registry.register(name, func, schema, risk_level)
        if ok:
            self.logger.info(f"注册工具 '{name}'（risk={risk_level}）", module="registry")
        else:
            self.logger.error(f"注册失败：{self.tool_registry.last_error}", module="registry")
        return ok

    # ── System Prompt ─────────────────────────────────────
    def build_system_prompt(self) -> str:
        """组装 system prompt。工具清单由 API 的 tools 参数提供，这里只写行为约定"""
        names = ", ".join(self.tool_registry.list_tools())#用逗号隔开
        return (
            "你是一个有用的智能助手，可以调用工具来完成计算、查询等任务。\n"
            "\n"
            "## 工具使用\n"
            f"可用工具：{names}\n"
            "当需要精确计算、实时信息或外部数据时，调用相应工具；\n"
            "工具结果只对模型可见，请整理后以自然语言回复用户。\n"
            "不需要工具时直接回答，不要为了调而调。\n"
            "\n"
            "## 回复要求\n"
            "用中文、简洁地回答用户。"
        )

    # ── 上下文压缩（Context Compactor 的最小版）────────────
    # 为什么 L3 不单独抽一个 ContextCompactor 类？
    # → L3 只有一种压缩策略（裁掉最老的轮次），放在 Agent 里一个方法就够。
    #   当策略多起来（摘要式压缩、按 token 预算压缩……）再抽类，别提前设计。
    #   （真正的 harness 如 learn-claude-code 里它就是独立的 context manager。）
    def _manage_context(self, messages: list[dict]) -> list[dict]:
        """
        上下文压缩：触发条件 + 策略。

        触发条件（满足其一就压缩）：
        a) 非 system 消息数 > CONTEXT_MAX_TURNS * 2（≈12 轮对话）
        b) 所有消息的总字符数 > CONTEXT_MAX_CHARS（粗略的 token 代理指标）

        策略（drop 式）：
        - system 消息永远保留（定义了 agent 行为，不能丢）
        - 只保留最近 CONTEXT_MAX_TURNS 轮，老的直接丢
        - 丢完如果第一条是 role=tool，连它一起丢
          （tool 消息必须紧跟在声明它的 assistant 消息之后，否则 API 报错）

        已知取舍：drop 式压缩会丢失早期信息，属于"最省钱的保底策略"。
        L5 升级方向：把被裁掉的部分用模型总结成一段摘要塞回去（summary 式压缩）。
        """
        if len(messages) <= 1:
            return messages

        system_msgs = [m for m in messages if m["role"] == "system"]
        other_msgs = [m for m in messages if m["role"] != "system"]

        total_chars = sum(len(str(m.get("content", ""))) for m in messages)
        over_turns = len(other_msgs) > self.CONTEXT_MAX_TURNS * 2
        over_chars = total_chars > self.CONTEXT_MAX_CHARS

        if not over_turns and not over_chars:
            return messages

        kept = other_msgs[-(self.CONTEXT_MAX_TURNS * 2):]#切片语法，从第24个（倒数 开始取，取到列表末尾
        while kept and kept[0]["role"] == "tool":
            kept.pop(0)  # 裁掉它的 assistant 了，孤立的 tool 结果也必须丢，丢掉单纯的工具调用
        removed = len(other_msgs) - len(kept)
        self.logger.warn(
            f"上下文压缩：丢弃最早 {removed} 条消息"
            f"（turns超限={over_turns}, chars超限={over_chars}）",
            module="agent")
        return system_msgs + kept#保留system和裁剪完成的keep

    # ── 单步工具调用 ──────────────────────────────────────
    def _handle_tool_call(self, tool_call, messages: list[dict]) -> tuple[int, int]:
        """
        处理一个工具调用请求，返回 (成功调用次数, 被拦截次数)。

        这条链是 L3 相对 L1/L2 的核心差异：
        Registry（存在吗）→ Gate（能调吗）→ Execute（执行）→ Logger（留痕）
        """
        tool_name = tool_call.function.name
        try:
            tool_args = json.loads(tool_call.function.arguments)
            if not isinstance(tool_args, dict):
                tool_args = {}
        except json.JSONDecodeError:
            tool_args = {}  # 模型生成的 JSON 坏了，按空参数处理，把错误交给模型自己发现

        tool = self.tool_registry.get(tool_name)
        risk = tool["risk_level"] if tool else None

        # 第 1 道闸：权限
        decision = self.permission_gate.check(tool_name, risk_level=risk)
        if decision == PermissionGate.DENY:
            self.logger.warn(f"权限拒绝：{tool_name}（规则判定 deny）", module="gate")
            # 拒绝也必须回一条 role=tool 消息：assistant 的 tool_calls 已经进对话了，
            # 不补上这个 tool_call_id 的回复，下一轮 API 会报“悬空的 tool call”，
            # 而且模型也没法向用户解释“为什么没执行”。
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": f"[权限拒绝] 工具 '{tool_name}' 被权限规则禁止执行，请向用户说明或换一种方式。",
            })
            return 0, 1

        if decision == PermissionGate.ASK:
            approved = self.permission_gate.request_approval(tool_name, tool_args)
            if not approved:
                self.logger.warn(f"用户拒绝：{tool_name}", module="gate")
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": f"[用户拒绝] 用户取消了工具 '{tool_name}' 的执行，请向用户说明情况。",
                })
                return 0, 1

        # 第 2 道闸：执行（Registry.execute 自带错误分类，不抛异常）
        start = time.time()
        result = self.tool_registry.execute(tool_name, tool_args)
        elapsed = time.time() - start
        self.logger.tool_call(tool_name, tool_args, result, elapsed)

        messages.append({
            "role": "tool",
            "tool_call_id": tool_call.id,
            "content": result,
        })
        return 1, 0
#return 0, 1   # 被拦了：成功 0 次，拦截 +1
#return 1, 0   # 正常执行：成功 +1，拦截 0 次

    # ── Agent Loop ────────────────────────────────────────
    def run(self, user_query: str, session_id: Optional[str] = None) -> str:
        """
        执行一次 agent 对话。返回模型最终回答（带统计 footer）。

        session_id 语义：
        - 传入 session_id → 持久会话。存在则续上，不存在则新建；
          每轮结束自动保存到 SessionStore，下次启动可恢复。
        - 不传 → 一次性对话（不落盘）。适合测试/脚本调用。

        和 L1 run_agent 结构一致，但每一步都走上面的模块链路。
        """
        # ── 0. 会话装载 ──
        if session_id is not None:
            if self._session_id != session_id:
                data = self.session_store.load(session_id)
                history = list(data["messages"]) if data and data.get("messages") else []
                if not any(m.get("role") == "system" for m in history):
                    history.insert(0, {"role": "system", "content": self.build_system_prompt()})
                self._history = history
                self._session_id = session_id
                self.logger.info(f"会话 '{session_id}'：恢复 {len(history)} 条消息", module="session")
        else:
            # 一次性对话：总是从干净的 system + 本轮 user 开始
            self._history = []
            self._session_id = None

        messages = self._history
        messages.append({"role": "user", "content": user_query})

        # ── 1. Loop ──
        start_time = time.time()
        tool_call_count = 0
        blocked_count = 0
        stop_reason = ""

        for step in range(self.MAX_STEPS):
            if time.time() - start_time > self.TIMEOUT:
                stop_reason = f"[超时] agent 运行超过 {self.TIMEOUT} 秒，强制终止"
                break

            messages = self._manage_context(messages)

            self.logger.info(f"step {step + 1}：调用模型…", module="agent")
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    tools=self.tool_registry.get_schemas(),
                )
            except Exception as e:
                # API 层错误：不能静默吞，打 ERROR 日志并让用户知道
                self.logger.error(f"模型调用失败：{type(e).__name__}: {e}", module="agent")
                stop_reason = f"[模型错误] {type(e).__name__}: {e}"
                break

            msg = response.choices[0].message

            # 情况 A：模型想调工具
            if msg.tool_calls:
                # 先把模型的工具调用请求记进对话（assistant 消息）
                messages.append(msg.model_dump(exclude_none=True))
                for tc in msg.tool_calls:
                    n_ok, n_blocked = self._handle_tool_call(tc, messages)
                    tool_call_count += n_ok
                    blocked_count += n_blocked
                continue  # 回到循环，把工具结果再喂给模型

            # 情况 B：模型直接回答了
            content = msg.content or ""
            messages.append({"role": "assistant", "content": content})
            elapsed = time.time() - start_time
            footer = (
                f"\n\n———\n"
                f"调用工具 {tool_call_count} 次 | 权限拦截 {blocked_count} 次 | "
                f"耗时 {elapsed:.1f}s | 步数 {step + 1}"
            )
            self._save_session(tool_call_count)
            return content + footer

        # ── 2. 没走完就结束（超时/超步/模型错误）──
        if not stop_reason:
            stop_reason = f"[超步] agent 达到最大步数上限（{self.MAX_STEPS}），强制终止"
        messages.append({"role": "assistant", "content": stop_reason})
        self._save_session(tool_call_count)
        return stop_reason

    def _save_session(self, tool_call_count: int):
        """把当前历史落盘（仅持久会话）。tool_call_count 累计进 metadata"""
        if self._session_id is None:
            return
        old_meta = (self.session_store.load(self._session_id) or {}).get("metadata", {})
        metadata = {
            "tool_call_count": old_meta.get("tool_call_count", 0) + tool_call_count,
        }
        self.session_store.save(self._session_id, self._history, metadata)
        self.logger.info(
            f"会话 '{self._session_id}' 已保存（共 {len(self._history)} 条消息）",
            module="session")

    def new_session(self) -> str:
        """开启一个全新会话，返回新 session_id（CLI 的 /new 用）"""
        self._session_id = self.session_store.new_session_id()
        self._history = [{"role": "system", "content": self.build_system_prompt()}]
        self.logger.info(f"新会话：{self._session_id}", module="session")
        return self._session_id


# ══════════════════════════════════════════════════════════════
# CLI 入口
# ══════════════════════════════════════════════════════════════

def create_agent() -> Agent:
    """解析 API key 并创建 agent；没 key 时打印指引后退出"""
    try:
        client = create_client()
    except RuntimeError as e:
        print(f"错误：{e}")
        sys.exit(1)
    return Agent(client=client, model=MODEL)

#argv[0] = 脚本自己的名字（main.py）
#argv[1] 往后 = 你在脚本名后面敲的每个参数，按空格拆开、顺序排列
def main():
    # 单次查询模式：python main.py "1+1等于几"
    if len(sys.argv) > 1 and not sys.argv[1].startswith("-"):
        agent = create_agent()
        print(agent.run(" ".join(sys.argv[1:])))
        return

    # 查看会话模式：python main.py --sessions
    if "--sessions" in sys.argv:
        store = SessionStore()
        sessions = store.list_sessions()
        if not sessions:
            print("（还没有保存过会话）")
        else:
            for s in sessions:
                print(f"[{s['session_id']}] {s['updated_at']} "
                      f"| {s['message_count']} 条 | {s['preview']}")
        return

    agent = create_agent()
    session_id = agent.new_session()

    print("=" * 55)
    print("L3 · Nano Harness（模块化 agent harness）")
    print("当前会话：" + session_id)
    print("命令：/new 新会话 | /sessions 列表 | /load <id> 恢复")
    print("      /tools 工具 | /rules 权限 | quit 退出")
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

        if query == "/new":
            session_id = agent.new_session()
            print(f"已切换：{session_id}")
            continue
        if query == "/sessions":
            sessions = agent.session_store.list_sessions()
            if not sessions:
                print("（还没有保存过会话）")
            else:
                for s in sessions:
                    marker = "◀" if s["session_id"] == session_id else " "
                    print(f"{marker} [{s['session_id']}] {s['updated_at']} "
                          f"| {s['message_count']} 条 | {s['preview']}")
            continue
        if query.startswith("/load"):
            parts = query.split()
            if len(parts) < 2:
                print("用法：/load <session_id>")
                continue
            sid = parts[1]
            data = agent.session_store.load(sid)
            if data is None or not data.get("messages"):
                print(f"找不到会话 {sid}，或会话为空")
                continue
            agent._history = [m for m in data["messages"]
                              if m.get("role") != "system"]  # 让 run() 重新注入 system
            agent._session_id = sid
            session_id = sid
            print(f"已恢复会话 {sid}（{len(agent._history)} 条消息），可以继续提问")
            continue
        if query == "/tools":
            for name in agent.tool_registry.list_tools():
                t = agent.tool_registry.get(name)
                desc = t["schema"]["function"]["description"][:40]
                print(f"  {name}（{t['risk_level']}）：{desc}")
            continue
        if query == "/rules":
            print(agent.permission_gate.describe())
            continue
        if query == "/help":
            print("命令：/new /sessions /load <id> /tools /rules /help，quit 退出")
            continue

        print()
        print(agent.run(query, session_id=session_id))


if __name__ == "__main__":
    main()      #「import 安全，运行才启动」调用时不主动运行


# ══════════════════════════════════════════════════════════════
# 常见坑（经验总结，写完后对照检查）
# ══════════════════════════════════════════════════════════════
#
# 坑 1：过度设计
#   → L3 只需要 5 个模块。不要一开始就搞 20 个类。
#   → 上下文压缩就是一个 Agent 方法，等策略多了再抽类。
#
# 坑 2：PermissionGate 和 ToolRegistry 的职责边界模糊
#   → Registry 只管"这个工具存在吗？怎么调用？"
#   → Gate 只管"这个工具现在能调吗？"
#   → 它们是独立的模块，不要互相调用。risk_level 由 Agent 传给 Gate。
#   → 所以 Registry.execute() 里没有权限判断，Gate.check() 里没有执行逻辑。
#
# 坑 3：SessionStore 存太多东西
#   → 只存 messages 和必要的 metadata。
#   → 不要尝试把整个 Agent 状态序列化（太复杂且难以维护）。
#
# 坑 4：上下文裁剪后 tool 消息孤立
#   → tool 消息必须紧跟声明它的 assistant(tool_calls) 消息，否则 API 报错。
#   → 裁剪只从头部进行，若头部是 tool 消息必须一并丢弃（见 _manage_context）。
#
# 坑 5：会话恢复后忘了 system prompt
#   → 历史文件里可能没有 system 消息（旧版本），run() 装载时要兜底注入。
#
# 坑 6：忘记对比 learn-claude-code 的架构
#   → L3 的核心目标是"理解一个真正的 harness 怎么设计"。
#   → 写完自己的 nano harness 后，一定要去读 learn-claude-code 的 agent loop，
#     对比差异（README 要求列 3 点）。


# ══════════════════════════════════════════════════════════════
# 必答问题参考答案（写完再读一遍，对照代码找答案）
# ══════════════════════════════════════════════════════════════
#
# Q1. agent loop 在哪个文件？核心逻辑多少行？
#   → 本文件（main.py）的 Agent.run()，约 70 行。
#     对照 learn-claude-code / claw0：它们的 agent loop 会拆到单独
#     文件（loop/ 或 agent/），几行核心 + 大量 hook 点。区别在于：
#     L3 的 loop 是"直接写死每步做什么"，成熟 harness 的 loop 是
#     "定义好每步的接口，实现可替换"。
#
# Q2. 工具是怎么注册的？tool schema 包含哪些字段？
#   → 工具函数 + schema + risk_level 合成 TOOL_DEFINITIONS，
#     Agent 启动时调用 ToolRegistry.register() 批量注册。
#     schema = OpenAI function calling 格式：type / function.name /
#     function.description / function.parameters(type=object + properties
#     + required)。注册时校验这些字段，错一个就不注册（启动期暴露错误）。
#
# Q3. 权限控制在哪里？每次调工具都要确认还是分级别？
#   → PermissionGate。分级别：safe→自动、needs_approval→问用户、
#     blocked→拒绝。用户可以加显式规则覆盖默认（如禁用某工具）。
#     默认 deny（白名单思维）：规则没覆盖到的都不执行。
#
# Q4. session 是怎么存、怎么恢复的？
#   → SessionStore：每轮对话结束自动把完整 messages 写成一个 JSON 文件
#     （sessions/{id}.json，原子写）。恢复：Agent.run(session_id=id) 时
#     load() 读文件、校验 system 消息、把历史接上继续聊。多会话靠
#     session_id 区分，/sessions 按更新时间倒序列出。
#
# Q5. 上下文太长时怎么压缩？触发条件是什么？
#   → Agent._manage_context()。两个触发条件：
#     (a) 非 system 消息超过 12 轮（CONTEXT_MAX_TURNS*2 条）；
#     (b) 消息总字符数超过约 3 万（CONTEXT_MAX_CHARS，粗略 token 代理）。
#     压缩策略：保留全部 system + 最近 12 轮，头部直接丢弃，
#     若丢弃后头部是孤立的 tool 消息则一并丢弃。
#     L5 升级：对丢弃部分做摘要式压缩，而不是直接丢。
