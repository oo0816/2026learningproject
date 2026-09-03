# L3 Nano Harness 代码精读 · 问答学习笔记

> 对象：`projects/l3-nano-harness/main.py`（模块化 agent harness，约 1250 行）
> 方式：通读 main.py → 课后自测 Q1–Q7 → 追问补漏
> 日期：2026-09-03

---

## 〇、背景速览：这个文件是什么

把「裸奔的 agent loop」拆成 5 个互不耦合的模块，再由 Agent 类组装（编排）：

```
Agent(Loop) ─┬─ ToolRegistry    工具有没有、怎么调（注册/校验/查找/执行）
             ├─ PermissionGate  现在能不能调（safe/ask/deny + 规则覆盖）
             ├─ SessionStore    历史存盘/恢复（sessions/*.json）
             ├─ Logger          分级日志（INFO/WARN/ERROR → 屏幕+logs/agent.log）
             └─ Context 压缩     超长时裁最老轮次（Agent 内方法）
```

**核心哲学（全文反复出现）**：每个类只做一件事，Registry 和 Gate 零耦合，Agent 只编排不实现。

**模块行号地图**：模块0 连接(96) · ToolRegistry(141) · PermissionGate(284) · SessionStore(419) · Logger(572) · 内置工具+TOOL_DEFINITIONS(650-812) · Agent(819) · CLI(1120) · 常见坑总结(1220)

---

## 一、课后自测 Q1–Q7

### Q1 主循环里模型有哪两种回应？各自走 continue 还是 return？

**我的回答**：需要调用工具 / 模型直接回答。
**点评**：两种回应对 ✅，但没答 continue/return 之分。

**标准答案**：

| 情况 | 处理 | 走向 |
|---|---|---|
| A. 要调工具（`msg.tool_calls`） | 执行工具、结果塞回 messages | `continue` → 回到循环再问一轮 |
| B. 直接给答案（`msg.content`） | 拼 footer、存会话 | `return` → 结束 run() |

**记忆点：要工具 → 没完，转回去再问；给答案 → 完事，return 收工。**
因为工具结果模型还没看到，必须喂回去让它决定下一步。`continue` 在 main.py:1074。

---

### Q2 加一个工具要改几处？为什么 run() 循环一行不用改？

**我的回答**：两处代码——新写入一个工具和 schema；因为 run 里用的是 tool、risk 这种变量代替，没有具体值。
**点评**：核心直觉对了（数据驱动 vs 写死）✅，但两处的说法要校准。

**标准答案**：改 **2 处**：
1. 写一个函数（工具真正干活的代码）
2. 在 `TOOL_DEFINITIONS` 列表里加一条记录：`{name, func, risk_level, schema}`
   （schema 是记录里的一个**字段**，不是第三处）

**为什么循环不用改**：因为通用代码操作的是**抽象**，从不出现具体工具名：
- 注册：`for td in TOOL_DEFINITIONS: register(td["name"], td["func"], ...)`
- 给模型的工具清单：`tools = self.tool_registry.get_schemas()`（自动含新工具）
- 执行：`tool["func"](**args)`（不认具体是谁）

「具体工具有什么」全用**数据**（列表字典）表达 → **加工具 = 加数据，不加逻辑**。

---

### Q3 check() 判断工具按什么优先级？不存在工具的 risk_level=None 返回什么？为何安全？

**追问**：什么叫「按什么优先级」？
→ 回答 check() 有三个「信息来源」可能打架（规则/等级默认/保底），优先级 = **听谁的、按什么顺序问**，先命中先赢。

**我的回答**：先显式规则 → 再 risk_level → 再保底 deny；返回 deny；因为默认拒绝不会放出有隐患的工具，需要人去补充确定。
**点评**：顺序、返回值、理由全对 ✅✅✅

**标准答案**（main.py:348-373，从上到下先到先赢）：
```
① 显式规则 self.rules（匹配工具名或 risk_level 关键字）→ 命中即返回
② 没规则命中 → RISK_DEFAULT[risk_level]（safe→allow / needs_approval→ask / blocked→deny）
③ 连等级都没有（None）→ default_action（默认 deny）
```
**安全原理** = **fail-closed（关闭失败）**：权限系统出错宁可错杀（拒绝过度）不可错放（放行过度）。未知 → 不猜、直接拒，决定权交回给人。

**连锁细节**：模型调**不存在**的工具 → `tool_registry.get()` 返回 None → risk=None → Gate 返回 deny → 走 deny 分支，模型收到「[权限拒绝]」而非「未知工具」。（小瑕疵：not found 与 denied 未区分，模型可能误以为工具存在只是没权限——可改进，不算 bug。）

---

### Q4 deny 时为什么必须往 messages 塞一条 tool 消息？

**我的回答**：不塞的话空调用会引发一些混乱。
**点评**：「会出事」的直觉方向对 ✅，但「空调用」说法不准确，也没说清两个硬伤。

**标准答案**：拒绝归拒绝，但必须「回一条正式 tool 消息占住 tool_call_id」，两个理由：

1. **协议要求（硬报错）**：assistant 消息声明了 `tool_calls` 后，必须有人用同一 `tool_call_id` 回应。不回应 = **悬空的 tool call**，下一轮发 API 直接 400 报错、对话中断。（类比：问朋友密码他不答，对话卡死）
2. **沟通要求**：模型下一轮看不到被拒反馈，会**反复重试同一工具**，或无法向用户解释。

**注意**：deny 和「ASK 后用户拒绝」用同一套占位做法，只是内容不同（「[权限拒绝]」/「[用户拒绝]」）。

**一句话：assistant 说「我要调工具」后，无论执行没执行，都欠 API 一个 tool 消息回应。**

---

### Q5 上下文压缩后 while 弹头部 tool 消息：解决什么？为什么 while 不用 if？

**我的回答**：tool 没有相邻的 assistant 会悬空；while 因为可能有很多条工具调用都要删。
**点评**：两问全对 ✅✅

**标准答案**：
- **解决什么**：对话协议要求每条 tool 必须紧跟「声明它」的 assistant（靠 tool_call_id 配对）。切片从头裁，可能把 assistant 宣言裁掉、tool 结果却留在窗口里 → **孤儿 tool 悬空 → 下轮 API 报错**（与 Q4 同一铁律的另一面）。孤儿必须跟着主人一起删。
- **为什么 while**：run() 里模型一次要调 N 个工具时（`for tc in msg.tool_calls`）会**连着** append N 条 tool 消息；分界线切在一串前面时头部就是 N 条孤儿。`if` 只删一条，剩下照样悬空；`while` 删到「第一条不是 tool」为止。
- 加分点：`while kept and ...` 里的 `kept` 条件 = 防 kept 被删空后 `kept[0]` 报 IndexError。

**铁律（Q4+Q5 一体两面）：tool 消息必须和它的 assistant 成对出现。**

---

### Q6 综合：跑通整条调用链（填空）

`python main.py "帮我查北京天气"`，模型调 get_weather。

**我的回答**（乱序 + 部分错）：handle_tool_call / create_agent / run / save_session / tool_registry / toolregistry permissiongate **run**
**点评**：create_agent、run、_handle_tool_call、_save_session、tool_registry.get、permission_gate.check 都点到了 ✅；但 run/execute 混淆 ✗；空缺 sys.argv / get_schemas / continue。

**标准完整链路**：

| 阶段 | 发生什么 | 负责者 |
|---|---|---|
| ① | 判断「单次查询」模式 | 看 `sys.argv`（main.py:1132） |
| ② | 建 Agent（连 API + 注册内置工具） | `create_agent()` |
| ③ | 问题进主循环 | `Agent.run()` |
| ④ | 调模型时把工具清单一起发 | `tool_registry.get_schemas()` |
| ⑤ | 模型要调 get_weather → 逐个处理 | `_handle_tool_call()` |
| ⑥ | 查工具/问权限/真执行 | `tool_registry.get()` → `permission_gate.check()` → `tool_registry.execute()` |
| ⑦ | 结果塞回 messages → 再问一轮 | `continue`（主循环） |
| ⑧ | 模型直接答 → footer + 存盘 + return | `_save_session()` |

**易错点：run ≠ execute**
- `run()` = Agent 的方法 = **整条主循环**（管转几圈）
- `execute()` = ToolRegistry 的方法 = **执行一次具体工具**（main.py:242）
- 关系：**run 包含 execute**（run 大循环内部 → _handle_tool_call → tool_registry.execute）

**记忆版链路**：
```
main() 看 sys.argv → create_agent() 造 Agent
  → agent.run(query)
    → 循环每轮: _manage_context 压缩
      → chat.completions.create(model, messages, tools=get_schemas())
      → 模型要工具? → 逐个 _handle_tool_call()
          → tool_registry.get() 查存在
          → permission_gate.check() 问权限 (deny/ask → 拒绝并回 tool 消息占位)
          → 放行 → tool_registry.execute() 真跑 → logger.tool_call() 留痕
        → continue 再问
      → 模型直接答? → _save_session() 存盘 → return 答案 + footer
```

---

### Q7 思考题：Registry 和 Gate 若改成耦合版（Gate 直接调 Registry.get）会有什么麻烦？

**参考答案**（三个维度）：
1. **测试难**：Gate 单测时必须先造一个 Registry，无法独立验证权限逻辑。
2. **扩展僵**：要换 Registry 的实现、或工具来源变了（如查 OpenAI 工具清单），Gate 代码也得跟着动；新增一个依赖 Gate 的模块会牵一发动全身。
3. **职责混乱 + 耦合风险**：Gate 本应只回答「能不能调」，一旦依赖 Registry 就同时知道「工具有没有」，两个边界糊掉，未来容易出循环依赖或隐式牵制。

**所以**：risk_level 由外层 Agent 从 Registry 查出、作为参数传给 Gate——数据与使用者解耦，中间层负责组装。真实 harness 也是把工具定义作为上下文喂给 permission checker。

---

## 二、答题中追问的知识点速查

### 1. sys.argv 是什么？
Python 解释器启动时**自动填好**的命令行参数列表。`argv[0]` = 脚本名，`argv[1:]` = 你敲的空格分隔参数。
| 敲法 | sys.argv |
|---|---|
| `python main.py` | `["main.py"]` |
| `python main.py "1+1等于几"` | `["main.py","1+1等于几"]` |
| `python main.py --sessions` | `["main.py","--sessions"]` |

来源链条：**你敲的命令 → 操作系统拆成参数 → 解释器填进 sys.argv → 代码读它**（main.py:1132）。

### 2. _handle_tool_call() 是什么？
「处理**一个**工具调用请求的流水线」（main.py:952），run() 主循环里每个工具请求调一次：
```
解析参数(json.loads) → tool_registry.get() 查存在拿 risk
→ permission_gate.check() → deny/ask(用户拒) 则回"[拒绝]"tool消息, return (0,1)
→ 放行 → tool_registry.execute() 执行 → logger.tool_call() 留痕
→ tool 结果塞回 messages → return (1,0)   ← 报账
```

### 3. footer 是什么？
模型直接回答时拼在答案末尾的**统计页脚**（main.py:1080-1084）：
```
北京今天晴，25°C，适合跑步。

———
调用工具 1 次 | 权限拦截 0 次 | 耗时 2.3s | 步数 2
```
计数来自每次 `_handle_tool_call()` 返回的 (成功, 拦截) 累加（main.py:1071-1072）。类比：游戏关卡结算画面。

### 4. `if len(sys.argv) > 1 and not sys.argv[1].startswith("-"):` 怎么读？
`main()` 的**第一道分流闸门**（单次查询 vs 选项 vs 聊天）：
- `len(sys.argv) > 1` = 除脚本名外还敲了东西
- `not sys.argv[1].startswith("-")` = 第一个参数不是 `-` 开头的**选项**（`--sessions` 之类）
- 两个都成立 = 「你带了问题」→ `create_agent()` → `print(agent.run(" ".join(sys.argv[1:])))` → return
- `" ".join(sys.argv[1:])` = 把被空格拆开的参数**拼回完整一句话**（问题可能含空格）

| 敲法 | 走哪 |
|---|---|
| `python main.py` | 跳过 → 交互聊天模式 |
| `python main.py "1+1等于几"` | 单次查询 |
| `python main.py --sessions` | 跳过 → 列会话分支（main.py:1138） |
| `python main.py 帮我 查 天气` | join 拼回「帮我 查 天气」再问 |

---

## 三、通读阶段概念速查（更早的问答浓缩）

| 概念 | 一句话 |
|---|---|
| **URL** | 网络资源地址 = 协议(https) + 主机(api.deepseek.com) + 路径。BASE_URL 告诉 OpenAI 客户端请求发给 DeepSeek。 |
| **`-> bool`** | 返回类型注解：这函数返回 True/False。只给人和 IDE 看，运行时**不强制**。register 返回成败标志。 |
| **`self.last_error`** | 失败原因中转站：register 失败时把具体原因存这、返回 False；调用方读它打日志。与 `-> bool` 配套。 |
| **CLI** | Command-Line Interface 命令行界面。main() + `if __name__ == "__main__"` 就是命令行大门。 |
| **`sys.argv`** | 见上。 |
| **`if __name__ == "__main__"`** | 「只有被**直接运行**时才启动 main()」；被 import 当库时不自动跑（`__name__` 直接跑="__main__"，import=模块名）。 |
| **schema** | 结构化说明书/契约：name/description/parameters(字段+类型+必填) 描述函数怎么被调用。**写给模型看、教它调用工具**；注册时校验保证能过 API。 |
| **序列化** | 把内存对象变文本存盘。别序列化「整个 Agent」——函数(代码)存不了、动态状态还原不了、改代码后存档失效。只存 messages + metadata，机器每次重建。 |
| **模块4 Logger** | 分级日志(INFO/WARN/ERROR) + 时间戳/级别/模块 → 屏幕 + logs/agent.log。tool_call() 记「谁/给了啥/结果前100字/耗时」。日志失败绝不影响主流程。 |
| **模块3 SessionStore** | 会话存 sessions/{id}.json；_valid_session_id 防路径穿越；原子写防损坏；只存 messages + 必要 metadata。 |
| **请求审批** | PermissionGate.request_approval：打印工具名+参数，input 等 y/n；EOF(无终端) 默认拒绝。 |

---

## 四、高频易错点清单（复习用）

1. **run vs execute**：run = Agent 整条主循环；execute = ToolRegistry 执行一次工具。run 包含 execute。
2. **tool 消息成对铁律**：每条 tool 必须紧跟声明它的 assistant（tool_call_id 配对）。→ 拒绝时要补答（Q4）、裁剪时孤儿要连删（Q5）。
3. **加工具 = 加数据不加逻辑**：只写函数 + TOOL_DEFINITIONS 加一行；通用代码不认具体工具名。
4. **权限优先级**：显式规则 > risk_level 默认 > 保底 deny。特殊压过一般；未知一律拒绝（fail-closed）。
5. **不存在工具 = 被 deny**（走权限拒绝分支），不会走到 execute 的「未知工具」提示。
6. **压缩先保护 system，tool 消息头部连删**（while 不是 if）。
7. **CLI 分流三模式**：带非"-"参数=单次查询 / `--sessions`=列会话 / 否则交互聊天。
