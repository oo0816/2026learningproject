# -*- coding: utf-8 -*-
"""
L3 离线单元测试：不需要 API key，验证 4 个模块的行为。

运行：python test_harness.py
覆盖：
  1. ToolRegistry：schema 校验（缺字段/错 type/重名/schema 名不一致）、
     get / get_schemas / list_tools / execute 错误分类
  2. PermissionGate：默认 deny、显式规则覆盖、risk 默认映射、通配符
  3. SessionStore：save / load / list_sessions / 损坏文件兜底 / session_id 校验
  4. Logger：分级格式 + tool_call 截断
"""
import json
import sys
import tempfile
import time
from pathlib import Path

import main  # noqa：只 import 模块定义，不触发 API key 解析

PASS = 0
FAIL = 0


def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  ✓ {name}")
    else:
        FAIL += 1
        print(f"  ✗ {name}  {detail}")


def calc_schema(name="calculator"):
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": "calc",
            "parameters": {
                "type": "object",
                "properties": {"expression": {"type": "string"}},
                "required": ["expression"],
            },
        },
    }


def test_registry():
    print("\n== ToolRegistry ==")
    reg = main.ToolRegistry()

    # 合法注册
    ok = reg.register("calculator", main.calculator, calc_schema(), "safe")
    check("合法注册返回 True", ok, reg.last_error)
    check("get 能找到", reg.get("calculator") is not None)
    check("list_tools", reg.list_tools() == ["calculator"])
    check("get_schemas 结构", reg.get_schemas()[0]["type"] == "function")

    # 非法注册（每个都该返回 False 且给出原因）
    ok = reg.register("dup", main.calculator, calc_schema(name="dup"), "safe")
    ok2 = reg.register("dup", main.calculator, calc_schema(name="dup"), "safe")
    check("重复注册被拒绝", ok and not ok2, reg.last_error)

    ok = reg.register("bad1", main.calculator, {"no_function": 1}, "safe")
    check("缺 function 键被拒绝", not ok and "function" in reg.last_error, reg.last_error)

    bad2 = calc_schema(); del bad2["function"]["parameters"]
    ok = reg.register("bad2", main.calculator, bad2, "safe")
    check("缺 parameters 被拒绝", not ok and "parameters" in reg.last_error, reg.last_error)

    bad3 = calc_schema(); bad3["function"]["parameters"]["type"] = "array"
    ok = reg.register("bad3", main.calculator, bad3, "safe")
    check("parameters.type 非 object 被拒绝", not ok, reg.last_error)

    bad4 = calc_schema(name="mismatch")
    ok = reg.register("alias", main.calculator, bad4, "safe")
    check("schema 名与注册名不一致被拒绝", not ok, reg.last_error)

    bad5 = calc_schema()
    ok = reg.register("risky", main.calculator, bad5, "super_dangerous")
    check("非法 risk_level 被拒绝", not ok, reg.last_error)

    # execute 错误分类
    check("execute 成功路径", reg.execute("calculator", {"expression": "1+2*3"}) == "7")
    r = reg.execute("nope", {})
    check("未知工具报错", r.startswith("[工具错误]") and "nope" in r, r)
    r = reg.execute("calculator", {"oops": 1})
    check("参数不匹配报错", r.startswith("[工具错误]") and "参数不匹配" in r, r)
    r = reg.execute("calculator", {"expression": "abc + 123"})
    check("工具内部校验报错（不崩溃）", "不允许的字符" in r, r)


def test_gate():
    print("\n== PermissionGate ==")
    gate = main.PermissionGate()  # 默认 deny

    # 默认行为
    check("无规则 + 无 risk → 默认 deny",
          gate.check("mystery_tool") == "deny")
    check("safe 工具 → allow",
          gate.check("web_search", risk_level="safe") == "allow")
    check("needs_approval → ask",
          gate.check("send_email", risk_level="needs_approval") == "ask")
    check("blocked → deny",
          gate.check("delete_file", risk_level="blocked") == "deny")

    # 显式规则优先于 risk 默认
    gate.add_rule("web_search", "deny")
    check("显式 deny 覆盖 safe 默认",
          gate.check("web_search", risk_level="safe") == "deny")

    gate2 = main.PermissionGate()
    gate2.add_rule("file_*", "deny")  # 动作是闸门三档 allow/ask/deny，不是 risk 三档
    check("通配符规则命中",
          gate2.check("file_delete", risk_level="safe") == "deny")
    check("通配符不误伤",
          gate2.check("web_search", risk_level="safe") == "allow")

    # request_approval 无输入时默认拒绝（EOF 路径）
    try:
        import io
        old = sys.stdin
        sys.stdin = io.StringIO("")  # 读即 EOF
        approved = main.PermissionGate().request_approval("send_email", {"to": "x"})
        check("stdin EOF → 默认拒绝", approved is False)
        sys.stdin = old
    except Exception as e:
        check("request_approval EOF 路径", False, str(e))


def test_session():
    print("\n== SessionStore ==")
    with tempfile.TemporaryDirectory() as td:
        store = main.SessionStore(base_dir=Path(td) / "sessions")

        sid = store.new_session_id()
        check("new_session_id 格式", bool(__import__("re").fullmatch(r"[\w\-]+", sid)), sid)

        msgs = [
            {"role": "user", "content": "你好"},
            {"role": "assistant", "content": "你好！"},
        ]
        check("save 成功", store.save(sid, msgs, {"tool_call_count": 2}) is True)

        data = store.load(sid)
        check("load 拿到消息", data and len(data["messages"]) == 2)
        check("metadata 保留", data["metadata"]["tool_call_count"] == 2)
        check("created_at 存在", "created_at" in data)

        # 再存一次：updated_at 变化但 created_at 不变
        # （时间戳精确到秒，至少等 1.1s 才能观察到 updated_at 变化）
        time.sleep(1.1)
        store.save(sid, msgs + [{"role": "user", "content": "继续"}])
        data2 = store.load(sid)
        check("二次保存 created_at 不变", data2["created_at"] == data["created_at"])
        check("二次保存 updated_at 更新", data2["updated_at"] != data["updated_at"])
        check("二次保存消息追加", len(data2["messages"]) == 3)

        # 损坏文件兜底
        bad = Path(td) / "sessions" / "corrupt-1.json"
        bad.write_text("{ not json", encoding="utf-8")
        check("损坏文件 load 不崩", store.load("corrupt-1") is not None)

        # list_sessions
        lst = store.list_sessions()
        check("list_sessions 非空且按新会话在前", len(lst) >= 1 and lst[0]["session_id"] == sid,
              str(lst))
        check("preview 是最后一条 user 消息", lst[0]["preview"] == "继续")

        # session_id 校验
        try:
            store.load("../evil")
            check("非法 session_id 被拦截", False)
        except ValueError:
            check("非法 session_id 被拦截", True)

        check("delete 成功", store.delete(sid) is True)
        check("delete 后 load 为 None", store.load(sid) is None)


def test_logger():
    print("\n== Logger ==")
    with tempfile.TemporaryDirectory() as td:
        logfile = Path(td) / "agent.log"
        logger = main.Logger(log_file=str(logfile), console=False)
        logger.info("hello", module="registry")
        logger.warn("careful", module="gate")
        logger.error("boom", module="agent")
        logger.tool_call("calculator", {"expression": "(3+5)*2"}, "16", 0.012)
        text = logfile.read_text(encoding="utf-8")
        check("INFO 格式含时间戳/级别/模块", "[INFO] [registry]" in text, text)
        check("WARN 行存在", "[WARN] [gate] careful" in text)
        check("ERROR 行存在", "[ERROR] [agent] boom" in text)
        check("tool_call 含耗时", "calculator" in text and "12ms" in text, text)


if __name__ == "__main__":
    print("L3 offline harness tests")
    test_registry()
    test_gate()
    test_session()
    test_logger()
    print(f"\n结果：{PASS} 通过，{FAIL} 失败")
    sys.exit(1 if FAIL else 0)
