
from typing import TypedDict
from langgraph.graph import StateGraph, START, END


# 1. 定义 State：整个图共享的数据结构
class State(TypedDict):
    message: str


# 2. 定义 Node：处理数据的函数
def hello_node(state: State):
    print("节点收到：", state["message"])
    return {"message": state["message"] + "，欢迎学习 LangGraph！"}


# 3. 创建 Graph
builder = StateGraph(State)

# 注册节点
builder.add_node("hello", hello_node)

# 连接节点
builder.add_edge(START, "hello")
builder.add_edge("hello", END)

# 4. 编译成可运行的 Graph
graph = builder.compile()

# 5. 执行
result = graph.invoke({"message": "你好"})

print("最终结果：", result)
