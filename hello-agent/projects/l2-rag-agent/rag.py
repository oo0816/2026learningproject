"""
L2 · 简易 RAG 模块
===============================

## 什么是 RAG？为什么 agent 需要它？

RAG = Retrieval-Augmented Generation（检索增强生成）。

大白话：先搜到相关资料，再把资料喂给模型，让模型"参考着回答"。

### 为什么不用微调（fine-tuning）而是用 RAG？

| 维度 | RAG | 微调 |
|------|-----|------|
| 知识更新 | 改文档即可，实时见效 | 需要重新训练 |
| 可溯源 | 能告诉用户"这个答案来自 XX 文档" | 知识融入权重，不可溯源 |
| 成本 | 只需要 embedding 成本 | GPU 训练成本高 |
| 幻觉控制 | 有原文对照，幻觉更容易被发现 | 可能自信地胡说 |

Agent 需要 RAG 因为：模型训练数据有截止日期，且不可能包含你的私有文档。

### RAG 的流水线（5 步）

```
文档 → [1.加载] → [2.分块] → [3.向量化] → [4.存储] → [5.检索]
                                                    ↑
                                              用户提问时触发
```

每一步都有设计选择：

1. **加载**：读文件、读数据库、读 API……L2 只处理 .txt 文件。
2. **分块**：文档太长不能直接向量化（embedding 模型有最大 token 限制）。
   怎么分？固定长度切？按句子切？按段落切？
3. **向量化**：把文字变成数字向量。"猫"和"猫咪"的向量距离近，"猫"和"汽车"距离远。
   模型选哪个？本地跑还是调 API？
4. **存储**：向量存在哪？L2 用内存 list，L3 升级到 ChromaDB/FAISS。
5. **检索**：用户提问也向量化 → 算余弦相似度 → 返回 top-K 最相关的分块。

### 余弦相似度是什么？

两个向量 A 和 B 的夹角越小（余弦值越接近 1），它们越"像"。

```
cos(A, B) = (A·B) / (|A| × |B|)

A·B = a1×b1 + a2×b2 + ... + an×bn     （点积）
|A| = sqrt(a1² + a2² + ... + an²)       （模长）
```

取值范围 [-1, 1]：1 = 方向完全相同，0 = 正交（无关），-1 = 方向完全相反。
"""

import math
import re
from pathlib import Path
from typing import Optional


# ─────────────────────────────────────────────
# 任务 1：实现文本分块
# ─────────────────────────────────────────────
# 为什么需要分块？因为 embedding 模型一次只能处理有限 token（all-MiniLM-L6-v2 是 256 token），
# 一整本书直接向量化是不行的。

def split_text(text: str, chunk_size: int = 300) -> list[str]:
    """
    把长文本切成小块，尽量在句子边界处切（不截断句子）。

    策略：按"。"分割 → 逐句拼接到当前块 → 超过 chunk_size 就开始新块。

    为什么按句子而不是固定字符数切？
    → 固定字符数可能在句子中间截断，破坏语义完整性。
       "今天天气很好。我去了公园" 切成 "今天天气很好。我去" 就丢失了信息。

    思考题：
    - 如果一句话本身就超过 chunk_size（比如 500 字的长句），怎么办？
    - 要不要 overlap（相邻块之间重叠一部分）？为什么？
    """
    text = text.replace("\n", " ")
    sentences = [s.strip() for s in re.split(r"(?<=[。！？.!?])", text) if s.strip()]

    chunks = []
    current = ""
    for sentence in sentences:
        if len(current) + len(sentence) <= chunk_size:
            current += sentence
        else:
            if current:
                chunks.append(current)
                current = ""
            if len(sentence) > chunk_size:
                # 超长单句：硬切，保证不丢失
                for i in range(0, len(sentence), chunk_size):
                    chunks.append(sentence[i:i + chunk_size])
            else:
                current = sentence
    if current:
        chunks.append(current)
    return chunks


# ─────────────────────────────────────────────
# 任务 2：实现 SimpleRAG 类
# ─────────────────────────────────────────────

class SimpleRAG:
    """
    内存向量检索器。

    核心数据结构：self.chunks — 一个 list，每个元素是 dict：
    {
        "id": 1,
        "text": "这是文档内容...",
        "source": "readme.txt",     # 来源文件名
        "embedding": [0.1, -0.3, ...]  # 384 维的浮点数向量
    }

    思考：为什么用内存 list 而不是数据库？
    → L2 文档量少（几十个分块），list 足够。L3 文档多时再引入向量数据库。
      先理解原理，再优化性能——这个顺序很重要。
    """

    def __init__(self):
        self.chunks: list[dict] = []
        self._model = None  # 懒加载：第一次用时才下载模型

    # ── embedding 模型管理 ──

    @property
    def model(self):
        """
        懒加载 embedding 模型。第一次访问时才下载和加载。

        为什么懒加载？
        → 模型文件 ~80MB，下载要几十秒。如果用户只是想看看 RAG 的代码结构，
          没必要一 import 就下载模型。

        推荐模型：sentence-transformers/all-MiniLM-L6-v2
        - 384 维向量（轻量）
        - 中英文都支持
        - 本地运行，不花钱
        """
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
                self._model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
            except ImportError:
                raise ImportError("请先安装 sentence-transformers：pip install sentence-transformers")
        return self._model

    # ── 文档加载 ──

    def load_text(self, text: str, source: str = "inline", chunk_size: int = 300):
        """
        加载一段文本：分块 → 向量化 → 存入 self.chunks。

        参数:
            text: 文本内容
            source: 来源标识（用于检索时告诉用户答案来自哪里）
            chunk_size: 每块最大字符数

        返回: 加载的分块数量
        """
        chunks = split_text(text, chunk_size)
        if not chunks:
            return 0
        embeddings = self._embed(chunks)
        start_id = len(self.chunks) + 1
        for i, (chunk, emb) in enumerate(zip(chunks, embeddings)):
            self.chunks.append({
                "id": start_id + i,
                "text": chunk,
                "source": source,
                "embedding": emb,
            })
        return len(chunks)

    def load_file(self, file_path: str, chunk_size: int = 300):
        """加载一个文件到 RAG 索引"""
        p = Path(file_path)
        try:
            text = p.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            text = p.read_text(encoding="gbk")
        return self.load_text(text, source=p.name, chunk_size=chunk_size)

    # ── 向量化 ──

    def _embed(self, texts: list[str]) -> list[list[float]]:
        """
        把文本列表转成向量列表。

        sentence-transformers 的用法：
            embeddings = self.model.encode(texts, show_progress_bar=False)
            return embeddings.tolist()

        注意：encode 默认返回 numpy array，tolist() 转成 Python list 便于 JSON 序列化。
        """
        embeddings = self.model.encode(texts, show_progress_bar=False)
        return embeddings.tolist()

    # ── 检索 ──

    def search(self, query: str, top_k: int = 3) -> list[dict]:
        """
        检索最相关的 top_k 个分块。

        步骤：
        1. 把 query 向量化
        2. 对 self.chunks 中每个 chunk 计算余弦相似度
        3. 按相似度降序排列
        4. 返回 top_k 个，过滤掉相似度低于 0.1 的（噪声）

        返回格式：[{id, text, source, score}, ...]

        思考题：阈值 0.1 是怎么定的？
        → 经验值。太高会漏掉相关结果，太低会混入噪声。
          实际项目中这个值需要根据你的数据和场景调优。
        """
        if not self.chunks:
            return []
        q_vec = self._embed([query])[0]
        scored = []
        for chunk in self.chunks:
            score = self.cosine_similarity(q_vec, chunk["embedding"])
            scored.append((score, chunk))
        scored.sort(key=lambda x: x[0], reverse=True)

        results = []
        for score, chunk in scored:
            if score < 0.1:
                break
            results.append({
                "id": chunk["id"],
                "text": chunk["text"],
                "source": chunk["source"],
                "score": round(score, 4),
            })
            if len(results) >= top_k:
                break
        return results

    def search_formatted(self, query: str, top_k: int = 3) -> str:
        """检索并返回格式化的文本，可以直接注入到 LLM 的 messages 中"""
        results = self.search(query, top_k)
        if not results:
            return ""
        lines = ["[知识库检索结果]"]
        for r in results:
            lines.append(f"（来源:{r['source']} 相似度:{r['score']}）\n{r['text']}")
        return "\n\n".join(lines)

    # ── 工具方法 ──

    @staticmethod
    def cosine_similarity(a: list[float], b: list[float]) -> float:
        """
        计算两个向量的余弦相似度。

        公式：cos = dot(A,B) / (norm(A) * norm(B))

        分三步：
        1. dot = sum(a[i] * b[i] for i in range(len(a)))
        2. norm_a = sqrt(sum(x*x for x in a))
        3. return dot / (norm_a * norm_b)

        小心：分母为 0（零向量）的情况要处理，返回 0.0。
        """
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = math.sqrt(sum(x * x for x in a))
        norm_b = math.sqrt(sum(x * x for x in b))
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)

    @property
    def chunk_count(self) -> int:
        return len(self.chunks)

    def stats(self) -> str:
        """返回 RAG 索引的统计信息"""
        sources = {c["source"] for c in self.chunks}
        return f"RAG 索引：共 {len(self.chunks)} 个分块，来自 {len(sources)} 个来源"


# ── 全局单例 ──
# 为什么用单例？因为 RAG 索引应该全局共享——main.py 加载一次文档，
# agent 循环中随时检索，没必要创建多个 RAG 实例。

_rag_instance: Optional[SimpleRAG] = None


def get_rag() -> SimpleRAG:
    """获取全局 RAG 单例"""
    global _rag_instance
    if _rag_instance is None:
        _rag_instance = SimpleRAG()
    return _rag_instance


# ══════════════════════════════════════════════════════════════
# 常见坑
# ══════════════════════════════════════════════════════════════
#
# 坑 1：第一次加载模型时卡住了（在下载 80MB 的模型文件）
#   → 正常的，等几分钟。模型文件缓存在本地，以后就快了。
#   → 如果下载太慢，可以先 pip install 时指定镜像源。
#
# 坑 2：embedding 之后忘记 .tolist()
#   → model.encode() 返回 numpy array，不能直接 JSON 序列化。
#   → 存到 list/dict 之前一定要 .tolist()。
#
# 坑 3：分块太大或太小
#   → 太大（1000+ 字）：检索到的块包含太多无关信息，模型被干扰。
#   → 太小（50 字）：语义不完整，检索不到。
#   → 300-500 字是比较平衡的选择。
#
# 坑 4：检索到了但不相关（相似度低但被返回了）
#   → 设置最低相似度阈值（如 0.1）过滤噪声。
#   → 没有找到相关结果时，明确告诉 agent "没找到"，而不是返回一堆不相关的东西。
#
# 坑 5：只有向量检索，没有关键词检索
#   → 纯向量检索对"精确匹配"不敏感——搜 "Python 3.12" 可能搜出一堆 Python 2.7 的内容。
#   → 成熟的 RAG 系统用混合检索（向量 + 关键词），L2 先不做，L3 再升级。
