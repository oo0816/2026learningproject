from main import run_agent

print("=== 测试1：数学计算 ===")
print(run_agent("1加2乘以3等于多少？用计算器算一下"))
print()

print("=== 测试2：天气查询 ===")
print(run_agent("北京和深圳今天天气怎么样？"))
print()

print("=== 测试3：无需工具 ===")
print(run_agent("你好，请用一句话介绍下Python语言"))
print()

print("=== 测试4：工具报错 — 计算器收到非法表达式 ===")
print(run_agent("帮我计算这个：abc + 123"))
print()

print("=== 测试5：超长输入 ===")
long_query = "请帮我计算：" + "1+1, " * 500 + "最后再加2"
print(run_agent(long_query))
