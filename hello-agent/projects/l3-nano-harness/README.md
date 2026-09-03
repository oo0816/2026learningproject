# L3 · Nano Harness

把 L1/L2 的"裸奔 agent loop"升级成模块化的 nano harness。

一个 agent 的能力大部分来自 harness：工具协议、权限、状态、日志。
L3 的目标是亲手把 4 个最核心的模块拆出来，再组装回去。

## 模块

| 模块 | 职责 | 对应真实 harness |
|------|------|------------------|
| `ToolRegistry` | 工具注册 / schema 校验 / 查找 / 执行 | 工具注册表 |
| `PermissionGate` | allow / ask / deny 三级权限 + 规则匹配 | 权限系统 |
| `SessionStore` | 会话存 JSON 文件，跨进程恢复 | 会话持久化 |
| `Logger` | 分级日志（时间戳/级别/模块）+ 工具调用留痕 | 日志 / trace |
| `Agent` | 只做编排：注册表 → 权限闸 → 执行 → 日志 → 喂回模型 | agent loop |

一次工具调用的完整链路：

```
模型说"调 web_search"
  → ToolRegistry.get()        这个工具有吗？schema 合法吗？
  → PermissionGate.check()    现在能调吗？
       allow → 直接执行
       ask   → request_approval() 问用户 y/n
       deny  → 返回 [权限拒绝]
  → ToolRegistry.execute()    真正执行（只做错误分类，不做权限）
  → Logger.tool_call()        记录 工具名/参数/结果前100字/耗时
  → 结果以 role=tool 塞回 messages → 下一轮
```

关键设计决策：

- **注册时校验 schema**（而非调用时）→ 配置错误在启动阶段暴露，更好排查
- **权限默认 deny**（白名单思维）→ safe 工具默认放行、needs_approval 问人、
  blocked 拒绝；用户显式规则永远压过默认。权限出错宁可拒绝过度，不可放行过度
- **每轮对话结束自动保存会话** → 崩溃最多丢当前轮中间过程；
  先保证正确性，量大再换增量存储
- **上下文压缩触发条件**：非 system 消息 > 12 轮 **或** 总字符 > 3 万；
  策略是丢最老的轮次（丢弃后若头部是孤立的 tool 消息则一并丢，防止 API 报错）

## 运行

```bash
python main.py                  # 交互模式（支持多会话）
python main.py "1+2*3等于几"    # 单次查询
python main.py --sessions       # 查看已保存会话
```

交互命令：`/new` `/sessions` `/load <id>` `/tools` `/rules`，`quit` 退出。

## 测试

```bash
python test_harness.py    # 离线单测（40 项，不需要 API key）
python test_agent.py      # 在线冒烟（跑 L1 的 3 条路径，需要 API key）
```

## 和真实 harness 对比（learn-claude-code / claw0）

读参考仓库的 agent loop，列出 3 点差异：

1. **loop 形态**：本文件 `Agent.run()` 是"过程式"——每步做什么写死在函数里；
   learn-claude-code 的 loop 是一组可组合的状态机/处理器，行为通过
   hook / 策略对象注入，可替换而不改 loop 本身。
2. **权限粒度**：L3 的 PermissionGate 只按工具名 + risk_level 判一次；
   真实 harness 会在**执行前后各验一次**，并支持按参数内容（路径、命令、
   域）做规则匹配，还会把一次决策记入会话供后续审计。
3. **上下文压缩**：L3 是"到阈值直接丢最老的轮"；真实 harness 会先对丢弃
   部分做**摘要压缩**（总结后放回 system），并在压缩后校验消息配对，
   把 token 预算当一等资源来管理。
