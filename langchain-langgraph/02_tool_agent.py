#不能直接运行，还有模型没有配置
from typing import Annotated, TypedDict

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage
from langchain_core.tools import tool
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition


# 1. 定义工具
@tool
def add(a: int, b: int) -> int:
    """计算两个数字的和"""
    return a + b


# 2. 定义 State
class State(TypedDict):
    messages: Annotated[list, add_messages]


# 3. 创建 LLM，并绑定工具
model = ChatOpenAI(model="你的模型名称")
model_with_tools = model.bind_tools([add])


# 4. 定义 LLM 节点
def llm_node(state: State):
    response = model_with_tools.invoke(state["messages"])
    return {"messages": [response]}


# 5. 创建 Graph
builder = StateGraph(State)

builder.add_node("llm", llm_node)
builder.add_node("tools", ToolNode([add]))


# 6. 连接节点
builder.add_edge(START, "llm")

builder.add_conditional_edges(
    "llm",
    tools_condition
)

builder.add_edge("tools", "llm")


# 7. 编译
graph = builder.compile()


# 8. 执行
result = graph.invoke({
    "messages": [
        HumanMessage(content="123 + 456 等于多少？")
    ]
})

print(result["messages"][-1].content)
