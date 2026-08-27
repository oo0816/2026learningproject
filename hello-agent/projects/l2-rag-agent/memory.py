"""
L2 · 三层记忆系统
===============================

## 核心概念：为什么需要三层记忆？

LLM 本身是"无状态"的——每次 API 调用都是独立的，它不记得上一轮说了什么。
你的 L1 agent 用 messages 列表解决了这个问题：把历史对话全塞进去。

但这不够。想一想这些场景：

| 场景 | messages 能解决吗？ | 为什么？ |
|------|---------------------|---------|
| 用户说"记住我喜欢蓝色" | 能，在当前对话中 | 消息列表里有一条 user message |
| 用户关了程序，明天再打开问"我喜欢什么颜色？" | 不能 | messages 在内存里，进程结束就没了 |
| 用户问"我上周问过关于 Python 的什么问题？" | 不能 | messages 只包含当前会话，而且太长会被裁剪 |

三层记忆各解决一个时间尺度的问题：

```
┌──────────────────────────────────────────────────────┐
│  Layer 1: messages（对话上下文）                       │
│  生命周期：单次会话，进程内存                           │
│  存储内容：完整的 API 消息历史（user/assistant/tool）    │
│  问题：太长会超 token 限制，需要裁剪                     │
├──────────────────────────────────────────────────────┤
│  Layer 2: session_store（会话记忆）                    │
│  生命周期：单次会话，进程内存                           │
│  存储内容：提取出来的关键信息（用户偏好、重要事实）        │
│  位置：注入到 system prompt 中，不占 messages 位置       │
├──────────────────────────────────────────────────────┤
│  Layer 3: long_term（长期记忆）                        │
│  生命周期：跨会话，存磁盘（JSON 文件）                   │
│  存储内容：用户认为重要、需要跨会话记住的东西              │
│  实现：JSON 文件读写 + 关键词检索                       │
└──────────────────────────────────────────────────────┘
```

## 关键设计问题（实现前先想清楚）

1. session_store 和 messages 有什么区别？
   → messages 是"原始对话记录"，session_store 是"提取后的摘要信息"。
   → 比如用户说了一大段关于自己工作的话，messages 里存原文，
      session_store 只存 "用户职业: 后端工程师, 主力语言: Python"

2. 长期记忆怎么触发写入？
   → 方案 A（L2 用这个）：约定格式，模型在回复中嵌入 [[REMEMBER: key]] value [[/REMEMBER]]#这只是一个规定好的格式
   → 方案 B：每次对话结束后用另一个 LLM 调用来"总结记忆"（贵，L5 再试）
   → 方案 C：用户手动输入 "/remember 我喜欢蓝色"（最可控但最不智能）

3. 长期记忆怎么检索？
   → L2：简单的关键词匹配（Python 字符串 in 判断）
   → L3+：向量检索（和 RAG 共用一个 embedding 模型）
   → 真实产品（如 Claude Code）：混合检索（关键词 + 向量 + 时间衰减）
"""

import json
import re   #正则表达式
from pathlib import Path
from datetime import datetime


# ─────────────────────────────────────────────
# 任务 1：实现 SessionMemory
# ─────────────────────────────────────────────
# 本质就是一个 dict，但有两点增强：
# 1. 能从模型的回复中解析 [[REMEMBER: ...]] ... [[/REMEMBER]] 指令
# 2. 能格式化成适合注入 system prompt 的文本

class SessionMemory:
    """会话级记忆：本轮对话中的关键信息"""

    def __init__(self):
        self.store: dict[str, str] = {}

    def set(self, key: str, value: str):
        """手动写入一条记忆"""
        self.store[key] = value

    def get(self, key: str) -> str | None:
        """读取一条记忆"""
        return self.store.get(key)

    def get_all(self) -> str:
        """
        返回格式化的记忆摘要，用于注入 system prompt。
        如果 store 为空，返回空字符串——不往 system prompt 里塞废话。
        """
        if not self.store:
            return ""

        lines = ["[会话记忆]"]
        for k, v in self.store.items():
            lines.append(f"- {k}: {v}")
        return "\n".join(lines)

    def update_from_message(self, content: str):
        """
        从模型的回复中解析 [[REMEMBER: key]] value [[/REMEMBER]] 并存储。

        正则拆解：
        \[\[REMEMBER:\s*(.+?)\]\]  匹配标签开头 + key（非贪婪）
        \s*(.+?)                   匹配 value（非贪婪）
        \[\[/REMEMBER\]\]          匹配标签结尾
        """
        pattern = r"\[\[REMEMBER:\s*(.+?)\]\]\s*(.+?)\[\[/REMEMBER\]\]"
        matches = re.findall(pattern, content, re.DOTALL)
        for key, value in matches:
            self.set(key.strip(), value.strip())


# ─────────────────────────────────────────────
# 任务 2：实现 LongTermMemory
# ─────────────────────────────────────────────
# 把记忆存到 JSON 文件，关了程序也不丢。
# L2 用最简单的实现：一个 list of dict，每个 dict 是一条记忆。

class LongTermMemory:
    """
    长期记忆：JSON 文件持久化存储。

    每条记忆的格式：
    {
        "id": 1,
        "content": "用户喜欢用 Python 做后端开发",
        "tags": ["偏好", "技术栈"],
        "source": "agent",       # "agent" | "user" | "system"
        "created_at": "2026-07-20T10:30:00"
    }

    思考：为什么每条记忆要有 tags 和 source 字段？
    提示：想想你一年后有 500 条记忆，怎么快速找到想要的那几条？
    """

    def __init__(self, file_path: str = None):
        if file_path is None:
            file_path = Path(__file__).parent / "long_term_memory.json"
        self.file_path = Path(file_path)
        self.entries: list[dict] = []
        self._load()

    def _load(self):
        """从 JSON 文件加载记忆。文件不存在或损坏 → 空列表，不崩溃。"""
        if not self.file_path.exists():
            self.entries = []
            return
        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                self.entries = json.load(f)
        except (json.JSONDecodeError, IOError):
            self.entries = []

    def _save(self):
        """将记忆写入 JSON 文件。ensure_ascii=False 保留中文，indent=2 方便人看。"""
        with open(self.file_path, "w", encoding="utf-8") as f:
            json.dump(self.entries, f, ensure_ascii=False, indent=2)

    def add(self, content: str, tags: list[str] = None, source: str = "agent") -> int:
        """添加一条长期记忆，返回记忆 ID"""
        entry = {
            "id": len(self.entries) + 1,
            "content": content,
            "tags": tags or [],
            "source": source,
            "created_at": datetime.now().isoformat(),
        }
        self.entries.append(entry)
        self._save()
        return entry["id"]

    def search(self, keyword: str) -> list[dict]:
        """
        按关键词检索记忆——同时检查 content 和 tags。
        用 .lower() 做大小写不敏感匹配。
        """
        kw = keyword.lower()
        results = []
        for entry in self.entries:
            if kw in entry["content"].lower():
                results.append(entry)
            elif any(kw in tag.lower() for tag in entry.get("tags", [])):
                results.append(entry)
        return results

    def get_all(self) -> str:
        """返回格式化的记忆摘要（最近 10 条），用于注入 system prompt"""
        if not self.entries:
            return ""
        lines = ["[长期记忆]"]
        for entry in self.entries[-10:]:
            lines.append(f"  [{entry['id']}] {entry['content'][:100]}")
        return "\n".join(lines)

    def get_recent(self, n: int = 5) -> list[dict]:
        """返回最近 n 条记忆"""
        return self.entries[-n:]


# ─────────────────────────────────────────────
# 任务 3：实现上下文窗口管理
# ─────────────────────────────────────────────

def manage_context_window(messages: list[dict], max_turns: int = 10) -> list[dict]:
    """
    当 messages 太长时间裁剪。保留 system prompt + 最近 max_turns 轮对话。

    输入: [system, user1, assistant1, user2, assistant2, ..., user20, assistant20]
    输出: [system, summary_system_msg, user11, assistant11, ..., user20, assistant20]

    策略：
    - role == "system" 的消息全部保留（定义了 agent 行为，不能丢）
    - 非 system 消息只保留最近 (max_turns * 2) 条（一轮对话约等于 2 条：user + assistant）
    - 被裁剪的用一条摘要消息替换
    """
    if len(messages) <= 1:
        return messages

    # 分离 system 和非 system
    system_msgs = [m for m in messages if m["role"] == "system"]
    other_msgs = [m for m in messages if m["role"] != "system"]

    keep_count = max_turns * 2
    if len(other_msgs) <= keep_count:
        return messages  # 没超，不用裁剪

    # 保留尾部最近的消息
    kept = other_msgs[-keep_count:]
    removed_count = len(other_msgs) - keep_count

    summary = {
        "role": "system",
        "content": f"[上下文已压缩] 早期 {removed_count} 条消息已被移除，保留了最近 {keep_count} 条。",
    }

    return system_msgs + [summary] + kept


# ══════════════════════════════════════════════════════════════
# 常见坑
# ══════════════════════════════════════════════════════════════
#
# 坑 1：把 messages 直接当记忆用
#   → messages 是对话记录，不是记忆。一个会话 100 轮后 messages 几万 token，
#     每次都全量发给 LLM，又贵又慢。session_store 存摘要，注入 system prompt。
#
# 坑 2：长期记忆无限增长
#   → JSON 文件会越来越大，每次启动全量加载到内存。
#   → L2 先用着，L3 考虑分页/归档/按时间衰减清理。
#
# 坑 3：记忆检索时只匹配了 content 忘了匹配 tags
#   → 用户 tag 了 "重要" 但搜 "重要" 时没检查 tags 字段——这种 bug 很隐蔽。
#
# 坑 4：[[REMEMBER]] 指令没被清理就展示给用户
#   → 模型学会了在回复中嵌入记忆指令，但这些指令不应该让用户看到。
#   → 在 main.py 中展示给用户之前，用正则把记忆标签去掉。
#
# 坑 5：上下文裁剪后模型丢失关键信息
#   → 比如用户在第 2 轮说了自己的名字，第 30 轮被裁剪掉了，
#     模型就"忘记"了用户的名字。解决方案：重要信息应该在 session_store 里有备份。
