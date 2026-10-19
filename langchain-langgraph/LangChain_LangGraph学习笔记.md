# LangChain & LangGraph 学习笔记

> 学习目标：从手写 Agent Loop 过渡到使用 LangChain 和 LangGraph 构建 AI Agent。
>
> 当前进度：基础概念与 Agent 运行逻辑已学习，完整项目代码仍需动手验证。

---

# 第一部分：整体知识框架

## 1. 三者之间的关系

**Agent Loop → LangChain → LangGraph**

- **Agent Loop**：Agent 的基本运行机制，包括调用模型、判断工具调用、执行工具、返回结果、继续循环。
- **LangChain**：提供模型、提示词、工具、Agent 等标准化组件。
- **LangGraph**：使用图结构组织 Agent 的执行流程，并管理状态、分支、循环和持久化。

LangChain 和 LangGraph 不是互相替代的关系，可以配合使用。

## 2. 核心区别

| 对比   | LangChain                  | LangGraph         |
| ---- | -------------------------- | ----------------- |
| 主要解决 | 组件调用与封装                    | 流程编排与状态管理         |
| 核心概念 | Model、Prompt、Tool、Runnable | State、Node、Edge   |
| 执行方式 | Chain 或 Agent              | Graph             |
| 典型用途 | 调用模型、工具、构建 Agent           | 条件分支、循环、记忆、多步骤工作流 |

---

# 第二部分：LangChain

## L1：基础组件

### 1. Model（模型）

用于调用大语言模型。

```
from langchain_openai import ChatOpenAI

model = ChatOpenAI(model="你的模型名称")
response = model.invoke("你好")
print(response.content)
```

**关键理解：** `model.invoke()` 表示执行一次模型调用。

### 2. Prompt（提示词）

负责组织发送给模型的消息。

```
from langchain_core.prompts import ChatPromptTemplate

prompt = ChatPromptTemplate.from_messages([
    ("system", "你是一个数学助手"),
    ("human", "{question}")
])
```

- `system`：规定模型角色和行为。
- `human`：用户输入。
- `{question}`：可以动态替换的变量。

### 3. Runnable（可执行组件）

LangChain 中具有统一调用接口的组件。

可以使用 `|` 将组件连接起来：

```
chain = prompt | model
result = chain.invoke({"question": "123 + 456 等于多少？"})
```

执行顺序：

`输入 → Prompt → Model → 输出`

### 4. Output Parser（输出解析器）

用于将模型输出转换成程序更容易处理的格式。

例如将 AIMessage 转换为字符串。

**关键理解：** 解析器主要服务于程序的数据处理，不只是为了让人阅读。

---

## L2：工具调用

### 1. `@tool`

将普通 Python 函数包装成模型可调用的工具。

```
from langchain_core.tools import tool

@tool
def add(a: int, b: int) -> int:
    """计算两个数字的和"""
    return a + b
```

工具包含：

- 工具名称
- 功能描述
- 参数结构
- 实际执行逻辑

### 2. `bind_tools()`

```
model_with_tools = model.bind_tools([add])
```

**重点：`bind_tools()` 不会执行工具。**

它只是向模型提供工具定义，让模型知道可以使用哪些工具。

### 3. 工具调用流程

1. 用户提出问题。
2. 模型判断是否需要工具。
3. 模型生成 `tool_calls`。
4. 程序执行对应工具。
5. 工具结果通过 `ToolMessage` 返回模型。
6. 模型继续生成回答或请求其他工具。

### 4. MCP 与 Tool 的关系

- Tool 是 Agent 可以调用的功能。
- MCP 是连接和使用外部工具、资源的一种标准协议。
- Agent 调用工具不一定需要 MCP。

---

## L3：Agent

### 1. Agent Loop

我们之前学习过的核心逻辑：

```
用户问题
   ↓
调用 LLM
   ↓
是否需要工具？
   ├── 是 → 执行工具 → 返回 LLM
   └── 否 → 输出答案
```

Agent 的重要特点是：模型可以根据任务决定下一步行动。

### 2. `create_agent()`

LangChain 提供高级 Agent 封装。

```
from langchain.agents import create_agent

agent = create_agent(
    model=model,
    tools=[add]
)
```

它可以帮助管理模型与工具之间的循环。

**关键理解：** Agent 的基本原理没有变化，只是框架替我们封装了部分运行逻辑。

---

# 第三部分：LangGraph

## L1：图结构基础

### 1. State（状态）

保存 Graph 执行过程中的数据。

```
from typing import TypedDict

class State(TypedDict):
    question: str
    answer: str
```

State 可以保存用户问题、模型回复、搜索结果、消息历史等。

### 2. Node（节点）

负责执行具体任务。

```
def answer_node(state: State):
    return {"answer": "你好！"}
```

**关键理解：**

Node 读取当前 State，执行工作，然后返回需要更新的字段。

不需要每次返回完整 State。

### 3. State 更新机制

原始状态：

```
{
    "question": "你好",
    "answer": ""
}
```

节点返回：

```
{"answer": "你好！"}
```

更新后的状态：

```
{
    "question": "你好",
    "answer": "你好！"
}
```

没有更新的 `question` 字段仍然保留。

### 4. Edge（边）

决定节点之间的执行路线。

```
builder.add_edge("A", "B")
```

表示 A 节点执行后进入 B 节点。

### 5. Conditional Edge（条件边）

根据条件决定下一步执行哪个节点。

```
builder.add_conditional_edges(
    "check",
    choose_path,
    {"big": "big", "small": "small"}
)
```

这里：

- `check`：条件判断发生在哪个节点之后。
- `choose_path`：负责选择路线的函数。
- 字典：将判断结果映射到目标节点。

条件边可以理解为图结构中的 `if/else`。

---

## L2：Graph 的创建和执行

### 1. `StateGraph()`

创建图的构建器。

```
builder = StateGraph(State)
```

### 2. `add_node()`

注册节点。

```
builder.add_node("work", work_node)
```

- `"work"` 是节点名称。
- `work_node` 是实际执行的 Python 函数。

### 3. `add_edge()`

连接节点。

```
builder.add_edge(START, "work")
builder.add_edge("work", END)
```

`START` 表示开始，`END` 表示结束。

### 4. `compile()`

```
graph = builder.compile()
```

将构建好的图编译成可执行对象。

### 5. `graph.invoke()`

```
result = graph.invoke({
    "question": "你好",
    "answer": ""
})
```

传入初始状态，执行整个图。

### 6. 完整生命周期

**定义 State → 定义 Node → 创建 Graph → 添加 Node → 连接 Edge → compile → invoke**

---

## L3：LangGraph Agent

### 1. LLM Node

在节点内部调用大模型。

```
def llm_node(state):
    response = model_with_tools.invoke(state["messages"])
    return {"messages": [response]}
```

注意：

- `model.invoke()`：执行一次模型调用。
- `graph.invoke()`：执行整个图，可能经过多个节点。

### 2. ToolNode

LangGraph 提供的工具执行节点。

```
from langgraph.prebuilt import ToolNode

tool_node = ToolNode([add])
```

用于执行模型请求的工具，并生成对应的工具结果消息。

### 3. `tools_condition`

```
from langgraph.prebuilt import tools_condition

builder.add_conditional_edges(
    "llm",
    tools_condition
)
```

根据最新 AI 消息是否包含工具调用请求，决定进入工具节点还是结束。

### 4. Agent 循环

```
builder.add_edge("tools", "llm")
```

这条边表示工具执行完成后返回模型。

完整流程：

```
START
  ↓
LLM
  ↓
tools_condition
  ├── 需要工具 → ToolNode → LLM
  └── 不需要工具 → END
```

**为什么工具执行后要返回 LLM？**

因为 LLM 需要理解工具结果、生成自然语言回答，也可能继续决定调用其他工具。

### 5. Reducer（状态合并规则）

普通 State 字段默认使用新值覆盖旧值。

但消息历史通常需要追加，因此可以使用：

```
from typing import Annotated
from langgraph.graph.message import add_messages

class State(TypedDict):
    messages: Annotated[list, add_messages]
```

`add_messages` 是消息状态的合并规则，通常会追加新消息，也支持根据消息 ID 更新已有消息。

---

## L4：记忆与状态持久化

### 1. Checkpointer

用于保存和恢复 Graph 的执行状态。

```
from langgraph.checkpoint.memory import InMemorySaver

checkpointer = InMemorySaver()

graph = builder.compile(
    checkpointer=checkpointer
)
```

### 2. `thread_id`

用于标识不同的对话线程。

```
config = {
    "configurable": {
        "thread_id": "conversation_001"
    }
}
```

使用相同的 `thread_id`，可以继续读取同一线程保存的状态。

不同 `thread_id` 默认不会自动共享聊天历史。

### 3. Store（长期记忆存储）

用于保存可以跨对话使用的数据。

```
from langgraph.store.memory import InMemoryStore

store = InMemoryStore()

store.put(
    ("users", "001"),
    "preferences",
    {"language": "Python"}
)
```

读取：

```
item = store.get(
    ("users", "001"),
    "preferences"
)

print(item.value)
```

### 4. Checkpointer 与 Store 对比

| <br> | Checkpointer | Store      |
| ---- | ------------ | ---------- |
| 主要用途 | 保存执行状态       | 保存跨对话数据    |
| 数据组织 | thread_id    | 命名空间 + Key |
| 常见场景 | 多轮聊天、恢复执行    | 用户偏好、长期信息  |

注意：`InMemorySaver` 和 `InMemoryStore` 都使用当前进程内存，程序结束后不会自动永久保留数据。

### 5. Runtime

节点可以通过 Runtime 访问运行上下文和 Store 等资源。

```
from langgraph.runtime import Runtime

def my_node(state, runtime: Runtime):
    memory = runtime.store.get(
        ("users", "001"),
        "preferences"
    )
    return {}
```

实际使用前需要为图配置相应的 Store。

---

# 第四部分：当前学习进度

## 已通过问答确认理解

- State 的部分更新不会删除其他字段。
- Node 负责工作，Edge 负责串联执行流程。
- Conditional Edge 可以根据条件选择节点。
- `compile()` 和 `invoke()` 的作用不同。
- ToolNode 执行后需要将结果返回 LLM。
- 不同 `thread_id` 对应独立的对话状态。
- 跨对话用户偏好更适合使用 Store。

## 已讲解，但还需要动手实践

- LangChain 的 Prompt、Model、Runnable、Parser。
- `@tool`、`bind_tools()`、`create_agent()`。
- 创建并运行完整的 StateGraph。
- ToolNode 与 `tools_condition`。
- Reducer 与消息历史管理。
- Checkpointer 和 Store 的实际使用。
- Runtime 的具体配置与调用。

**实践记录：**

此前尝试运行 `01_first_graph.py`，遇到文件不存在的路径错误，因此不能算作已经成功运行 LangGraph。

## 尚未正式学习

1. Human-in-the-loop：`interrupt()`、`Command(resume=...)`。
2. SQLite、PostgreSQL 等持久化 Checkpointer。
3. 长期记忆的提取、检索与更新策略。
4. 多 Agent：Supervisor、Worker、Reviewer。
5. Graph 的调试、可视化和测试评估。
6. 完整 AI Agent 项目实战。

---

# 第五部分：核心速记

**LangChain：**

- `Prompt`：组织输入。
- `Model`：调用模型。
- `Runnable`：统一执行接口。
- `Parser`：处理输出。
- `Tool`：提供可执行能力。
- `Agent`：让模型决定下一步动作。

**LangGraph：**

- `State`：保存数据。
- `Node`：执行任务。
- `Edge`：控制路线。
- `Reducer`：控制状态合并。
- `ToolNode`：执行工具。
- `Checkpointer`：保存和恢复图状态。
- `Store`：保存跨对话数据。

**最重要的一句话：**

LangChain 提供构建 Agent 的组件，LangGraph 用图结构组织这些组件的执行流程；两者都建立在 Agent Loop 的基本原理之上。

---

# 第六部分：下一步学习方向

先在 VS Code 中真正运行一个简单 Graph，再逐步运行工具调用 Agent。

之后依次学习：

1. Human-in-the-loop。
2. Checkpoint 持久化。
3. Store 长期记忆实践。
4. 多 Agent 协作。
5. 完整 Agent 项目。

每学完一部分，就更新这份笔记，并标记是否已经独立运行验证。
