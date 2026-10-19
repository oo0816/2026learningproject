from typing import TypedDict, Annotated
import operator

from langgraph.graph import StateGraph, START, END


# 1. 定义 State
class State(TypedDict):
    results: Annotated[list[str], operator.add]


# 2. 搜索网页节点
def search_web(state: State):
    print("正在搜索网页...")
    return {"results": ["网页资料"]}


# 3. 查询数据库节点
def search_db(state: State):
    print("正在查询数据库...")
    return {"results": ["数据库资料"]}


# 4. 汇总节点
def summarize(state: State):
    print("正在汇总...")
    print("收集到的资料：", state["results"])
    return {}


# 5. 创建 Graph
builder = StateGraph(State)

builder.add_node("web", search_web)
builder.add_node("db", search_db)
builder.add_node("summary", summarize)

# START 同时连接两个节点
builder.add_edge(START, "web")
builder.add_edge(START, "db")

# 等待两个节点完成，再进入 summary
builder.add_edge(["web", "db"], "summary")

builder.add_edge("summary", END)


# 6. 编译
graph = builder.compile()


# 7. 运行
result = graph.invoke({
    "results": []
})

print("最终结果：", result)