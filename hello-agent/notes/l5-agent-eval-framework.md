# L5 · 多 Agent + 评测面试笔记

> 整理日期：2026-10-15  
> 对应代码：`hello-agent/projects/l5-multi-agent/main.py`  
> 离线测试：`test_l5_offline.py`，8 passed / 0 failed  
> 在线记录：`online_results.md`、`online_reports/`、`online_traces/`

---

## 0. 一句话理解多 Agent

多 Agent 不是让单个模型变强，而是把复杂任务拆成多个职责单一、上下文隔离的角色，并解决它们之间的协调、通信、停止条件和评测问题。

```text
User
  → Supervisor
  → Researcher → Writer → Reviewer
  → 修改循环 / 护栏
  → Human Gate
  → Final Report
```

核心原则：

1. 职责单一
2. 最小能力
3. 结构化交接
4. 上下文隔离
5. 有制衡
6. 有停止条件
7. 有可观测性
8. 有评测

---

## 1. 单个 Agent 的运行机制

### Q1：一个 Agent 的一次 `think()` 里发生了什么？

完整流程：

```text
1. 构造 messages
   system = 角色提示
   user   = 任务 + Supervisor 传来的 context

2. 调用模型
   把 messages 和工具 Schema 发给 LLM

3. 判断模型返回
   A. 有 tool_calls：
      - assistant 消息追加进 messages
      - 本地执行工具
      - tool 结果按 tool_call_id 配对追加
      - 回到第 2 步
   B. 没有 tool_calls：
      - 模型给出结论
      - think() 返回 content

4. 受 MAX_TOOL_STEPS 限制
   防止模型一直调工具不结束
```

一句话：

> `think()` = 给角色一个任务，它自己调模型、调工具，直到产出该角色应该产出的文本。

在 L5 里：

- Researcher 可能多轮调用 `web_search`。
- Writer 一般一次模型调用后返回报告。
- Reviewer 一次调用后返回裁决 JSON。

---

### Q2：为什么每个 Agent 的 messages 要从干净状态开始？

因为需要**上下文隔离**。

如果所有 Agent 共用一份 messages，会出现：

- Writer 看到 Researcher 的无关搜索结果和工具报错。
- Reviewer 看到 Writer 的思考过程和中间草稿。
- 一个 Agent 的人设被另一个 Agent 的指令污染。
- Token 快速膨胀。
- 出错时无法判断是谁把上下文带坏了。

正确做法：

```text
原始上下文留在各 Agent 内部
跨 Agent 只传递结构化必要信息
Supervisor 负责“翻译”和路由
```

例如 Writer 初稿只需要：

```text
用户原始需求
+ Researcher 的研究摘要
```

改写时再多两块：

```text
上一版报告
+ Reviewer 的修改意见
```

共享的是结构化状态：

```text
research
report
comments
loop_count
reason
```

不是所有原始消息。

好处：

- 角色边界清晰
- 上下文更短、更便宜
- 行为更稳定、可复现
- Trace 更容易定位问题

---

### Q3：为什么工具错误不能直接抛异常，而要喂回模型？

因为工具错误本身也是一种**观察结果**。

模型遇到错误后应该有机会：

- 修正参数再试一次
- 换一个工具
- 改变策略
- 向用户解释失败原因

如果工具直接抛异常，Agent Loop 会崩掉：

```text
模型：调用 search(query=None)
工具：抛出 TypeError
程序：崩溃退出
```

正确做法：

```text
[工具错误] 参数缺失：query 不能为空
```

然后以 `role="tool"` 消息回到模型，让模型决定下一步。

L5 工具契约：

> 工具永远返回字符串，永远不抛异常。

错误分类：

- 未知工具
- JSON 解析失败
- 参数类型不对
- 工具内部异常
- 执行超时
- 空结果

一句话：

> 工具错误不是程序级崩溃，而是任务级反馈；Agent 的价值之一就是能从失败中调整策略。

---

## 2. 角色设计和能力边界

### Q4：为什么只有 Researcher 有搜索工具？

最小能力原则。

```text
Researcher：需要外部信息 → 给 web_search
Writer：加工信息 → 不需要搜索
Reviewer：判断质量 → 不需要搜索
```

好处：

- 行为更可预测
- 成本更可控
- 权限更小
- 责任边界清晰

一句话：

> 每个 Agent 只给刚好够用的能力。

---

### Q5：为什么 Writer 不应该自己去搜索？

Writer 的输入应该是经过 Researcher 整理和验证的研究摘要。

如果 Writer 也能搜索：

- 可能绕过研究摘要，引入未经验证的新事实
- 报告事实来源不再单一，Reviewer 很难追溯
- 可能一边写一边搜，上下文膨胀、任务漂移
- 同一事实可能在两处得到不同结论
- 出错后责任边界模糊

正确分工：

```text
Researcher：负责找事实
Writer：负责把事实写成报告
Reviewer：负责检查报告有没有问题
```

---

### Q6：为什么 Reviewer 的输出必须是 JSON？

因为 Reviewer 的输出是给程序读的。

Supervisor 需要判断：

- 通过还是拒绝
- 问题类别是什么
- 是否还有修改额度
- 是否连续两轮卡在同一个问题

自由文本不可靠：

```text
我觉得还行吧
再改改结构会更好
pass!
```

强制输出：

```json
{
  "verdict": "pass|revise",
  "score": 0,
  "issue_type": "length|accuracy|structure|coverage|style|other|none",
  "comments": "给 Writer 的具体修改意见"
}
```

`issue_type` 使用固定枚举，才能做确定性的“卡住检测”：

```text
连续两轮 issue_type 相同
→ stuck_force_pass
```

解析失败时 fail-closed：

```text
解析失败 → 默认判 revise
```

因为“多改一轮”比“放走一份没审过的报告”代价更低。

---

## 3. 为什么用多 Agent 和如何通信

### Q7：为什么用多 Agent，而不是单 Agent？

单 Agent 的问题：

- system prompt 越来越长
- 一个 Agent 同时做研究、写作、审查，目标冲突
- 上下文切换到不同任务时成本高
- 没有独立制衡

多 Agent 的价值：

- 职责单一
- prompt 更短、更聚焦
- 可以独立审查
- 模块化，便于替换和评测

代价：

- Token 和延迟更高
- 协调复杂
- 错误会跨 Agent 传播
- 调试更难

判断标准：

```text
短任务、低风险、单一上下文 → 单 Agent
多阶段、需要审查、角色冲突 → 多 Agent
```

---

### Q8：多 Agent 之间怎么通信？为什么不共用一个 messages？

L5 采用 Supervisor 结构化交接：

```text
Researcher 输出研究摘要
→ Supervisor 交给 Writer

Writer 输出报告
→ Supervisor 交给 Reviewer

Reviewer 拒绝
→ Supervisor 把 研究摘要 + 上一版报告 + 评审意见 交给 Writer
```

为什么不用共享 messages：

- 上下文污染
- 角色混乱
- Token 膨胀
- 隐私和权限信息泄露
- 难以调试

共享的应该是状态，不是原始消息。

---

### Q9：Reviewer 一直不通过怎么办？

通过三道护栏控制：

| 护栏 | 防什么 | 处理 |
|---|---|---|
| `max_review_loops` | 无限修改 | 强制放行并标记 |
| `total_timeout` | 整体耗时失控 | 带草稿退出 |
| `stuck_force_pass` | 同一问题反复无进展 | 提前停止 |

还会进入人工确认闸门：

```text
未获确认 → ok(draft)
```

生产环境可以进一步区分：

- Reviewer 标准过严
- Writer 确实没改好
- 证据不足
- 任务本身不可完成

---

### Q10：三道护栏分别防什么？

```text
max_review_loops：管“改了几次”
total_timeout：管“花了多久”
stuck_force_pass：管“有没有进展”
```

它们不是同一件事。

---

### Q11：`stuck_force_pass` 和 `max_loops_force_pass` 有什么区别？

```text
max_loops_force_pass：修改次数用完了
stuck_force_pass：还没到上限，但连续两轮同一个 issue，说明没进展
```

为什么用 `issue_type` 而不是比较意见原文：

- 真实 Reviewer 每轮都会换一种说法讲同一件事
- 文本相似度不可靠
- 枚举比较是确定性操作

---

## 4. 评测和可观测性

### Q12：为什么 `online_results.md` 和 `online_traces` 要分开？

| 产物 | 用途 | 读者 |
|---|---|---|
| `online_results.md` | 结果总览 | 人 |
| `online_results.json` | 指标数据 | 程序 |
| `online_reports/` | 最终报告正文 | 人 |
| `online_traces/` | 完整执行轨迹 | 调试者 |

一句话：

```text
results = 结果怎么样
reports = 产出了什么
traces  = 过程发生了什么
```

如果混在一起，会导致：

- 指标被长文本淹没
- 无法自动做回归统计
- 失败时无法定位过程

---

### Q13：报告质量差，怎么从 trace 判断是谁的问题？

| 现象 | 问题可能在 |
|---|---|
| Researcher 搜索失败、结果为空、没调工具 | Researcher |
| 搜索有结果，但 Writer 报告没引用、事实丢失 | Writer |
| 报告事实正确但结构乱，Reviewer 第一次就 pass | Reviewer 标准过宽 |
| Reviewer 一直拒绝但意见模糊、多轮同一 issue | Reviewer 或 prompt |
| 触发 `max_loops_force_pass` | Writer 改不好，或 Reviewer 太苛刻 |
| 触发 `stuck_force_pass` | 评审和修改都没有实质进展 |
| `timeout`，报告明显不完整 | 网络、搜索或整体流程太慢 |

查看：

- Researcher 的 `tools/call` 结果
- Writer 的 `write/done`、`revise/done`
- Reviewer 的 `verdict`、`score`、`issue_type`、`comments`
- Supervisor 的 `review/round`、`review/max_loops`、`review/stuck`、`review/timeout`
- Human Gate 的 `gate/result`

一句话：

> Trace 把“最后报告不好”拆成“从哪一步开始变坏”。

---

### Q14：为什么离线测试 8/8 通过，仍然不能说明真实任务质量好？

离线测试用假模型，验证控制流和护栏：

✅ 正常通过  
✅ 先拒绝后通过  
✅ 改满上限  
✅ 卡住检测  
✅ 超时  
✅ 人工拒绝  
✅ 空输入  
✅ Trace 记录  

它不能验证：

- 真实 Reviewer 的审美和判断是否合理
- 真实搜索结果是否相关
- Writer 是否忠实、语言是否合格
- 真实模型是否幻觉、重复、跑题
- 实际 Token 和延迟是否可接受

所以：

```text
离线测试：证明机制正确
在线评测：证明质量可用
```

---

### Q15：为什么 `ok(stuck_force_pass)` 不能当成正常通过？

因为 `ok` 只表示交付流程完成，不表示质量合格。

状态语义：

```text
ok                     → Reviewer 正常通过
ok(max_loops_force_pass) → 改太多次，认输放行
ok(stuck_force_pass)   → 卡在同一个问题，强制放行
ok(timeout)            → 超时，带草稿退出
ok(draft)              → 没有获得交付确认
```

`stuck_force_pass` 应归类为：

- 降级交付
- 质量未达标
- 或单独一类失败

正确统计：

```text
正常通过：reason == passed
降级通过：reason in {max_loops_force_pass, stuck_force_pass, timeout}
未交付：status 带 draft
硬失败：bad_input / error
```

---

## 5. 扩展到更多 Agent

### Q16：如果扩展到 10 个 Agent，架构怎么改？

不能继续写死串行 Supervisor，需要升级为可编排的图和状态机。

四层改造：

1. **控制流**
   - 静态 Supervisor → 动态路由
   - 支持并行分支和汇总

2. **状态**
   - 内存变量 → 共享 State + Checkpointer
   - 支持中断恢复和审计

3. **通信**
   - 函数调用 → 消息总线 / 队列
   - 支持异步和失败重试

4. **治理**
   - 预算、步数、超时、权限
   - Trace、评测、回归

角色可以扩展为：

```text
Planner
Retriever
Writer
Reviewer
Critic
Router
Tool Executor
```

用 LangGraph 表达：

```text
节点 = Agent
边 = 控制流
条件边 = 路由
State = 共享状态
Checkpointer = 持久化
Human-in-the-loop = 人工闸门
```

---

## 6. 面试常见指标

### 结果指标

- 任务成功率
- 正常通过率
- 降级交付率
- 硬失败率

### 成本指标

- 总 Token
- 单任务 Token
- 平均耗时
- P95 延迟

### 质量指标

- Reviewer 通过率
- 平均修改轮数
- 护栏触发次数
- 人工介入率

### 过程指标

- 工具调用成功率
- 检索命中情况
- 超时次数
- 卡住次数

### 失败分类

```text
bad_input
researcher_failure
writer_failure
reviewer_failure
max_loops_force_pass
stuck_force_pass
timeout
permission_denied
tool_error
```

---

## 7. 当前 L5 证据

### 离线测试

```text
文件：test_l5_offline.py
结果：8 passed / 0 failed
耗时：0.011s
不调用真实模型
```

### 在线评测

```text
在线正常流程：3/3 已运行

#1 量子计算最新进展 500 字报告
状态：ok(stuck_force_pass)
原因：stuck_force_pass
修改轮数：1
耗时：21.12s
Token：8669
报告字数：821
结论：降级交付，不能算正常通过

#2 Python vs Go 后端开发对比
状态：ok
原因：passed
修改轮数：1
耗时：29.17s
Token：10466
报告字数：1696
结论：正常通过

#3 Docker 与 K8s 的关系
状态：ok
原因：passed
修改轮数：0
耗时：17.31s
Token：6314
报告字数：1999
结论：正常通过

审批方式：自动评测批准（未经人工确认）

### 任务 1 失败定位（stuck_force_pass）

从 `online_traces/01.json` 可见：

- 用户要求：500 字报告
- Writer 初稿：952 字
- Reviewer 第 1 轮：`issue_type=length`，要求压缩到 450–550 字
- Writer 改后：803 字
- Reviewer 第 2 轮：`issue_type=length`，仍超出 500 字要求
- Supervisor 连续两轮检测到同一问题 → `stuck_force_pass`

结论：

1. Researcher 搜索成功，资料充分。
2. Reviewer 判断一致且合理。
3. 真正的失败点是 Writer 没有严格遵守字数硬约束。
4. 护栏工作正常，但结果属于降级交付，不是正常通过。
```

注意：

> 在线正常流程 3/3 已跑完：任务 1 为降级交付，任务 2、3 为正常通过。降级交付必须在评测中单独归类。

---

## 8. L5 `main.py` 结构

> 对应文件：`hello-agent/projects/l5-multi-agent/main.py`  
> 当前结构约 596 行有效代码，按模块职责从上到下排列。

### 8.1 文件级结构

```text
main.py
├── 文件说明与导入（约 1-31 行）
│   ├── 核心认知：多 Agent = 角色拆分 + Supervisor 编排
│   ├── 标准库导入
│   └── MODEL / BASE_URL / _client_singleton
│
├── 模型连接与配置（约 33-72 行）
│   ├── _resolve_env_key()
│   ├── _resolve_api_key()
│   └── create_client()
│
├── 工具层（约 74-110 行）
│   └── web_search()
│
├── 可观测性（约 112-152 行）
│   └── TraceLogger
│       ├── log()
│       └── report()
│
├── 单 Agent 基类（约 155-293 行）
│   └── BaseAgent
│       ├── __init__()
│       ├── think()
│       ├── _call()
│       ├── _run_tool()
│       └── _log()
│
├── 三个角色（约 296-380 行）
│   ├── Researcher
│   ├── Writer
│   └── Reviewer
│
├── 评审辅助（约 382-419 行）
│   ├── _normalize_issue_type()
│   ├── _extract_length_limit()
│   └── _parse_verdict()
│
├── 人工闸门（约 421-434 行）
│   └── _default_ask_human()
│
├── 多 Agent 编排（约 436-657 行）
│   └── Supervisor
│       ├── __init__()
│       ├── run()
│       │   ├── 输入校验
│       │   ├── Researcher 调度
│       │   ├── Writer 调度
│       │   ├── Reviewer 修改循环
│       │   ├── 三道护栏
│       │   ├── 人工确认闸门
│       │   └── 汇总返回
│       └── _finish()
│
└── CLI 入口（约 659 行之后）
    └── main()
```

### 8.2 `BaseAgent`：单个 Agent 的封装

```text
BaseAgent
├── __init__：name / role / tools / model_fn / tracer / token 计数
├── think()：对外唯一入口，内部跑完整个 agent loop
├── _call()：调模型并规范化成 {content, tool_calls, tokens}
├── _run_tool()：执行工具，把异常转成可读文本
└── _log()：有 tracer 时记录一步 trace
```

关键设计：

- `model_fn` 依赖注入：真实运行时用 DeepSeek，评测时换成假模型。
- `tools` 结构与工具 schema 分离：`func` 给程序，`schema` 给模型。
- 工具调用协议：assistant → tool_calls → tool result → 再次调用模型。
- `MAX_TOOL_STEPS` 防止一个 Agent 无限调工具。

### 8.3 三个角色

| 类 | 职责 | 工具 |
|---|---|---|
| `Researcher` | 收集资料，输出研究摘要 | `web_search` |
| `Writer` | 根据摘要和需求写报告 | 无 |
| `Reviewer` | 审核报告，输出结构化裁决 JSON | 无 |

共同点：

- 都继承 `BaseAgent`
- 都从干净 messages 开始
- 都通过 `think()` 暴露能力

不同点：

- system prompt 不同
- 工具能力不同
- 输出格式不同

### 8.4 `Supervisor.run()`：多 Agent 编排主流程

```text
1. 重置 trace / token / llm_calls
2. 本地输入校验
   - 空输入
   - 只有符号/空白
   - 超过 2000 字
3. 提取用户字数要求
4. Researcher.think(clean)
5. Writer.think(clean, context=research)
6. 进入评审循环：
   a. 检查 max_review_loops
   b. 检查 total_timeout
   c. Reviewer.think(clean, context=report)
   d. 解析 verdict
   e. pass -> 结束
   f. 连续两轮同一 issue_type -> stuck_force_pass
   g. 否则 Writer.think(...) 改写
7. 人工确认闸门
8. 汇总 final_report / status / reason / trace / time / tokens
```

### 8.5 三道护栏和状态

```text
max_review_loops
  防无限修改

total_timeout
  防整体耗时失控

stuck_force_pass
  防同一问题反复无进展
```

最终 `status`：

```text
ok
ok(max_loops_force_pass)
ok(stuck_force_pass)
ok(timeout)
ok(draft)
bad_input
```

`reason`：

```text
passed
max_loops_force_pass
stuck_force_pass
timeout
bad_input
```

### 8.6 阅读顺序

面试复习时按这个顺序读：

```text
1. BaseAgent
2. Researcher / Writer / Reviewer
3. Supervisor.run()
4. TraceLogger
5. CLI main()
```

读完要能回答：

- 单 Agent 如何调用模型和工具？
- 三角色为什么这样分？
- Supervisor 如何传递上下文？
- Reviewer 不通过后发生什么？
- 三道护栏如何触发？
- 最终结果包含哪些状态字段？
- Trace 怎么辅助定位失败？
## 9. 面试 60 秒总结

> 我的多 Agent 系统核心不是堆角色，而是用 Supervisor 做结构化交接，用上下文隔离降低污染，用 Reviewer 做独立质检，再用最大修改次数、总超时和卡住检测三道护栏控制成本和质量。系统有完整 Trace，可以定位失败发生在检索、写作、评审还是编排层。评测分成离线控制和在线质量：离线用假模型验证机制，8 个用例全部通过；在线用真实模型跑任务并记录成功率、修改轮数、Token 和延迟。像 `stuck_force_pass` 这种降级交付不会算作正常通过，而是单独记录，保证评测结果真实。




