# L4 · Skill / Tool / MCP / A2A 概念问答学习笔记

> 方式：与 Claude 一轮对话追问「skill tool mcp a2a 有什么区别」→ 逐层追问到 MCP Server、MCP 协议线格式、MCP vs API、skill 加载机制
> 对应路线图 [README.md L4](README.md) 的 B线验证题
> 日期：2026-09-07

---

## 〇、背景速览：四个词根本不在同一层

> 一句话区分：**Tool 是最小能力单元，Skill 是"怎么做事"的知识包，MCP 是"智能体↔工具/数据"的接入标准，A2A 是"智能体↔智能体"的互操作标准。**

**最容易的误解**：以为它们四选一、是同一种东西的变体。实际上它们是**不同抽象层**的产物，size 差着好几级：

```
                    ┌─────────────────────────┐
                    │        A2A 协议           │   连接其他智能体（找谁干）
                    └─────────────────────────┘
                    ┌─────────────────────────┐
                    │    Skill（方法论/知识）    │   教模型怎么干
                    └───────────┬─────────────┘
                    ┌───────────▼─────────────┐
                    │        MCP 协议           │   标准化接入工具/数据
                    └───────────┬─────────────┘
              ┌─────────────────▼──────────────────┐
              │       Tool（具体动作：读/写/调API）    │
              └────────────────────────────────────┘
```

**一个贯通例子**：让 Claude Code "用日语复习 skill 出卷" → Skill 加载出题方法论 → 其中读取 `exams/` 考点库是 MCP 提供的 resource/tool → 排版 PDF 是内置 tool → 如果哪天有另一个 agent 也要调你这套复习能力，就靠 A2A 暴露给它。

---

## Q1：skill / tool / mcp / a2a 有什么区别？（一图+一表）

### 对比表

| 概念 | 本质 | 解决什么问题 | 谁连接谁 | 类比 |
|---|---|---|---|---|
| **Tool（工具）** | 一个可被模型调用的函数 | 让模型能执行某个具体动作 | 模型 → 单个能力 | 乐高零件 |
| **Skill（技能）** | 一套指令 + 参考资料的打包 | 教模型"这类任务该怎么做" | 人 → 模型（加载指导） | 说明书 |
| **MCP** | 一种开放**协议** | 标准化接入外部工具和数据 | 智能体 → 各种工具/数据源 | USB-C 接口标准 |
| **A2A** | 一种开放**协议** | 让独立智能体互相发现、协作 | 智能体 → 智能体 | 让两个人对话的协议 |

### 逐个拆解

**Tool —— 最底层的"能力"**
就是给模型用的函数：名字 + 描述 + 参数 schema。模型读到后决定"要不要调用、传什么参"。Claude Code 里的 Read/Edit/Bash/Grep 是内置 tool；自己写的 function-calling 也算 tool。它**不做判断，只提供动作**。

**Skill —— "怎么做"的知识**
在 Claude Code / Agent Skills 里，Skill 是一个目录，核心是 `SKILL.md`（含描述 + 指令），可能带脚本、模板、参考文件。它**本身不执行任何东西**，而是被触发时把这段"方法论"塞进模型上下文，让模型接下来按这套规范去调用 tool。
用自己的例子：`japanese-exam-review` skill 不会直接生成 PDF，它告诉你"按这套版式、走 A/B 双通路、按考点模式输出"——具体排版动作还是靠 tool 完成的。**Tool 给你手，Skill 给你章法。**

**MCP —— 工具和数据的"标准化插口"**
Anthropic 提出的开放协议。MCP 服务器可以向任何兼容客户端注册 **tools（动作）、resources（数据）、prompts（模板）**。价值在于"一次接入、到处复用"。**Tool 是"模型能调的东西"，MCP 是"把第三方的东西接进来的标准通道之一"。** 注意 MCP 也管数据（resources），不只是工具。

**A2A —— 智能体和智能体之间说话**
Google 发起、后来捐给 Linux 基金会的开放协议。对象**不是工具，而是另一个完整的 agent**。解决：我怎么发现你有能力？任务委派后怎么跟踪进度、取结果？通常配套一个 `agent-card`（JSON，描述 agent 的能力/身份/接口）。**MCP 问"agent 能用什么"，A2A 问"agent 能找谁帮忙、怎么对接"。**

### 记忆点
- 大小关系：**一个 Skill 内部会指导调用一堆 Tool；MCP 决定这些 Tool 从哪来；A2A 站在最高层，让整个 agent（连同它的 Skill 和 MCP 工具）能被别的 agent 调用。**
- Skill 是导演（章法），Tool/MCP 是导演手里的演员和道具（能力）。

---

## Q2：MCP Server 是什么？

顺着 Q1 往下讲：**MCP Server 就是"把工具/数据打包成一个标准服务的那个进程"**。

### MCP 是 Client–Server 结构

```
你（Claude Code / IDE / 你的 agent 程序）
      │
   ┌──▼──────────┐    标准协议    ┌──────────────┐
   │ MCP Client  │ ◄────────────► │ MCP Server   │
   │ (调用方/宿主) │   JSON-RPC 2.0  │ (提供服务方)    │
   └─────────────┘    (stdio/SSE)  └──────────────┘
                                        │ 通过真实 API
                                   ┌────▼─────┐
                                   │  业务系统  │  (数据库/网页/GitHub...)
                                   └──────────┘
```

- **MCP Client**：跑在宿主程序里（Claude Code 就是一个 client），负责跟模型交互、把"模型想调工具"的请求转发给 server。
- **MCP Server**：一个**独立进程或程序**，知道怎么连真实外部系统，然后把能力**暴露成标准化的东西**让 client 调用。

### 一个 server 能暴露三类能力

| 类型 | 含义 | 例子 |
|---|---|---|
| **Tools** | 可执行的动作（模型调用、有参数） | `search_web()`、`query_db()` |
| **Resources** | 可读取的数据 | 一份文件、一段数据库记录 |
| **Prompts** | 现成的提示词模板 | "按这个格式总结PDF" |

Claude Code 启动时拉起配置好的 MCP server，把它的 tools 注册进自己的工具列表——**模型用起来跟内置 Read/Edit 没区别**，只是背后干活的是另一个程序。

### 关键点：server 只是个"翻译/接线员"

1. **封装**：把某外部系统的真实 API 包起来（GitHub API、数据库、浏览器……）。
2. **标准化**：对外只按 MCP 协议说话，**任何 MCP client 都能用**——同一 server，Claude Code 能用、别的兼容 IDE 也能用（一次写好、到处复用）。
3. **隔离**：server 通常跑在自己进程里（甚至远程），出问题只影响那个工具，不搞崩整个 agent。

### Claude Code 里长什么样

```json
{
  "mcpServers": {
    "filesystem": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "C:/notes"]
    }
  }
}
```

启动后 Claude Code 执行 `npx ...server-filesystem` 拉起进程当 MCP server，对话里就多了一组能读写 `C:/notes` 的工具。

### 记忆点
- **区分两个名字**：**MCP 是协议（标准），MCP Server 是遵守该协议的那个程序**。类比：HTTP 是协议，Nginx 是跑在 HTTP 上的一个服务器程序。

---

## Q3：MCP 协议是长什么样子的？

> **协议"长得"就是一行行的 JSON**。MCP 底层是 **JSON-RPC 2.0**，传输走 stdio 或 HTTP，但**每个消息都是一段 JSON**。

### 一个消息的样子（最核心）

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "要调用的方法名",
  "params": { "参数": "..." }
}
```

- 回复不带 `method`、带 `result`
- 通知没有 `id`（不需要答复）
- 就这么三个变体。

### 完整对话过程（假设 server 只暴露一个工具 add）

**① Client 先打招呼（initialize 握手）**
```json
{
  "jsonrpc": "2.0", "id": 1,
  "method": "initialize",
  "params": {
    "protocolVersion": "2024-11-05",
    "capabilities": { "roots": { "listChanged": true } },
    "clientInfo": { "name": "claude-code", "version": "1.0.0" }
  }
}
```

**② Server 回自己的能力和协议版本**
```json
{
  "jsonrpc": "2.0", "id": 1,
  "result": {
    "protocolVersion": "2024-11-05",
    "capabilities": { "tools": {} },
    "serverInfo": { "name": "demo-server", "version": "0.1.0" }
  }
}
```

**③ Client 补"我初始化完了"的通知**（没 id，不需要回）
```json
{ "jsonrpc": "2.0", "method": "notifications/initialized" }
```

**④ Client 问"你有哪些工具？"**
```json
{ "jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {} }
```

**⑤ Server 列出工具的 JSON Schema**（决定模型怎么用、参数怎么校验）
```json
{
  "jsonrpc": "2.0", "id": 2,
  "result": {
    "tools": [
      {
        "name": "add",
        "description": "两个数相加",
        "inputSchema": {
          "type": "object",
          "properties": {
            "a": { "type": "number" },
            "b": { "type": "number" }
          },
          "required": ["a", "b"]
        }
      }
    ]
  }
}
```

**⑥ Client 说"调用 add，a=1，b=2"**
```json
{
  "jsonrpc": "2.0", "id": 3,
  "method": "tools/call",
  "params": { "name": "add", "arguments": { "a": 1, "b": 2 } }
}
```

**⑦ Server 返回结果——注意 `content` 是数组，每项带 `type`**
```json
{
  "jsonrpc": "2.0", "id": 3,
  "result": {
    "content": [ { "type": "text", "text": "3" } ],
    "isError": false
  }
}
```

### 从这段对话读出的设计要点
1. **方法名固定英文**：`initialize`、`notifications/initialized`、`tools/list`、`tools/call`、`resources/read`、`prompts/list`……协议核心就是几十个方法名 + 规定参数。
2. **工具描述用 JSON Schema**（第⑤步），不是自定义格式——任何能解析 JSON Schema 的模型/客户端都能适配，这是"通用"的来源。
3. **`id` 用来配对**：client 发请求带自增 id，server 回同样 id，一问一答乱序也能对上。
4. **`content` 是通用返回格式**：除 `text`，还可以 `{"type":"image","data":...,"mimeType":"..."}` 或 `{"type":"resource",...}`。"返回一段文本/一张图/一段数据"都是同一套结构。

### 记忆点
MCP Server"只是接线员"——**协议层面只做一件事：听懂这几句 JSON、把 `tools/call` 转成对真实系统的调用、再把结果包成 `content` 回出去**。真正的加法逻辑（查数据库、调 GitHub API）藏在 server 内部，协议里根本看不到。

---

## Q4：MCP 和普通 API 调用的区别在哪里？

> 先给结论：**API 调用是"一个问题对应一套接口"；MCP 是把"接入这件事"本身标准化了**。MCP 底层其实也是 API（JSON-RPC），所以区别不在"有没有 HTTP 请求"，而在**谁去适配谁**。

### 模型"想查天气"的两种做法

**直接调 API（function calling 原始做法）**——为每个服务手写适配器：
```python
def get_weather(city):
    url = f"https://api.openweather.com/?q={city}&key=MY_KEY"
    resp = requests.get(url)          # 天气 API 自己的 URL/鉴权/参数格式
    return parse_weather_json(resp)   # 自己解析它的返回格式

def query_db(sql):                    # 换个数据库，又是完全另一套
    ...
```
模型的视角没变（还是"看到一个叫 get_weather 的工具可调"），但**接入每个新服务都要写新代码**：处理它独有的鉴权、端点、字段名。

**走 MCP**——client **只认一种协议**：问 `tools/list` → server 给工具名字和 JSON Schema；调 `tools/call` → server 自己负责翻译成天气 API 的格式、加鉴权、解析返回。**不用为各服务各写 handler**——配置里多一行启动哪个 MCP server 就行。

### 核心区别表

| 维度 | 直接调 API | MCP |
|---|---|---|
| 接口 | 每个服务**自定义**（URL、鉴权、字段都不同） | 全部是**固定那几个方法**：`tools/list`、`tools/call`… |
| 谁做适配 | **你（agent 代码）**为每个服务各写一份 | **server** 自己适配，client 只认协议 |
| 工具发现 | 写死在代码里 | 运行时用 `tools/list` **动态发现** |
| 复用性 | N 服务 × M AI 客户端 = N×M 份代码 | N+M：接一次 server，所有 MCP 客户端都能用 |
| 接入成本 | 单次简单，多了爆炸 | 单次稍重，多了反而省 |
| 传输 | 基本是远程 HTTP | 可以 **stdio（本地进程）**，也能 HTTP |

### 两个容易忽略的加分点
1. **本地 stdio 模式 = 私密数据不用出本机**。MCP server 可以是本地进程、走 stdin/stdout 通信——Claude Code 访问本地文件/数据库时，数据不经过网络，也**不用把 API key 交给模型厂商**。这是很多人选 MCP 的真实原因。
2. **MCP 不只"动作"，还管"读数据"**：普通 API 顶多暴露函数；MCP 还标准化 `resources/read`（给模型开一个可浏览的文件系统视角）和 prompts。等于把"能干什么 + 能看什么 + 有哪些现成指令"一起管起来。

### 那为什么不全用 MCP？
因为**多了协议开销**：握手、JSON-RPC 包装、版本协商，比直连 REST 啰嗦。如果只给 agent 加**一个**简单能力、没有跨客户端复用需求，直接写函数调 API 更干净——MCP 的价值在"接入多个服务 / 被多个 AI 工具复用 / 想碰本地私密数据"时才体现。

### 历史类比（帮助记忆）
MCP 之于 AI 工具接入，就像 **JDBC/ODBC 之于数据库**：当年每个数据库都有自己的连接方式，程序连 MySQL、Oracle 要写两套代码；JDBC 定了统一接口，各家数据库自己写驱动，程序就只认一种。

---

## Q5：一个 SKILL.md 被 agent 加载后，agent 的 system prompt 里加了什么？

> 这是路线图 L4 的 B线验证题。先纠正一个误解，再分两层。

### 前提：加载 ≠ 塞进"系统提示词"本体

skill 加载后，通常**不会改写 Claude 的底座 system prompt**（那部分是模型出厂设定，改不了）。它是**作为一段高优先级指令注入当前回合的上下文**，效果上"像系统提示一样被遵守"，但技术上走的是 skill 装载通道。装载分**两层**。

### 第一层：常驻的"目录条目"——只有名字 + 一句话

skill **还没被触发时**，上下文里就已有一行，从 frontmatter 的 `description` 来：
```yaml
description: 为软件工程中日合办学生，根据日语CS课件和试卷生成复习文档PDF
```
模型眼里是一条目录项：
> - japanese-exam-review: 为软件工程中日合办学生，根据日语CS课件和试卷生成复习文档PDF

**这一层的作用是路由**：模型每轮都知道"有哪些技能可用、各管什么"，读到相关请求时判断"该触发哪个"。**`description` 就是触发契约**——模型只能靠它判断相关性，写太笼统它就不触发。（frontmatter 里的 `display_name`、`short_description` 是给"目录/斜杠命令展示"的美化字段；`description` 才是模型真正读的。）

### 第二层：触发后加载的"操作手册"——SKILL.md 正文

用户 `/japanese-exam-review` 或模型判定该用并调用 Skill 工具后，**整篇 SKILL.md 正文**进入当前上下文，成为这回合模型必须照做的指令。对 `japanese-exam-review` 来说：

| 正文区块 | 加载后变成 agent 的行为约束 |
|---|---|
| `## 触发条件` | 只在"日语 + CS 专业课"同时满足时启动 |
| `## 前置确认` | 动手前必须先问那三个问题（🔴 强制检查点） |
| `## 统一版式` | 只用这 7 个元件、不许发明新排版 |
| `## 工作流程` | 通路 A 直写 / B JSON 怎么选、各跑哪些脚本 |
| `## 质量要求 / 失败模式` | 验收标准、遇 0 页/缺字体时不许硬闯的兜底 |

**本质上：skill 加载 = 把你写的一本"操作规程"交给 agent，要求它按这个章程干活**——把"该怎么做、什么能做、什么禁止、失败了怎么办"一次性教会。跟 MCP 那种"多出几个可调用函数"是两码事：**skill 不改能力清单，改的是行为方式。**

### 第二层最重要的设计：不把整个文件夹倒进来

对比目录结构：
```
japanese-exam-review/
├── SKILL.md                 ← 加载时就进上下文，只有这一份
├── scripts/guide_style.py   ✗ 不加载
├── scripts/path_b_render.py ✗ 不加载
├── output/sample_a.pdf      ✗ 不加载
└── examples/*.json          ✗ 不加载
```
配套文件**全部留在磁盘上**，模型按需读。SKILL.md 里到处是这种"指针"：
- "参照 `scripts/build_sample_a.py` 学习写法" → 用到时才 Read
- "排版引擎是 `scripts/guide_style.py`" → 需要方法签名时才读
- "示例见 `examples/content_b_example.json`" → 写 JSON 前才翻

**这就是 skill 的上下文经济学**：若把脚本/样例/参考全塞进来，一次调用可能吃掉几万 token。设计成"**正文常驻、附件按需**"，让模型像人查资料一样需要哪份读哪份。

### 一句话回答
> 加载 skill 后：**常驻层**加了 name+description（路由用，本来就一直在）；**触发层**把整份 SKILL.md 正文作为必须遵守的指令注入当前回合，配套文件不进来、只在正文指挥下按需读取。

---

## 高频易错点清单（复习用）

1. **四者不在同一层**：Tool=最小能力，Skill=方法论知识包，MCP=接工具/数据的协议，A2A=agent↔agent 的协议。别拿它们做"四选一"。
2. **Skill 不改能力，改行为**：它注入的是"操作规程"文本；没有脚本和附件进上下文，只有 SKILL.md 正文 + 按需读的指针。
3. **MCP = 协议，MCP Server = 守约程序**：一个是标准，一个是进程。
4. **MCP vs API 的分界是"谁去适配谁"**：普通 API 要 agent 为每服务写 handler；MCP 由 server 自适配，client 只认固定方法。
5. **MCP 的 value 场景**：多服务接入、跨客户端复用、本地私密数据（stdio）。单次简单接入直接用 API 更干净。
6. **MCP 底层就是 JSON-RPC 2.0**：`jsonrpc`/`id`/`method`/`params`→`result`；`id` 配对、通知无 id、工具描述用 JSON Schema、`content` 是通用返回数组。
