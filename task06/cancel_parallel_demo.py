# 第 6 章 · 补充实验：并行启动 + 取消恢复（评审要求：体验并行任务、追加指令、取消恢复）
import asyncio
import json
import time

from langgraph_sdk import get_client

client = get_client(url="http://127.0.0.1:2024")
ASSISTANT = "supervisor"


def show(state, only_async_tools=True):
    msgs = state.get("messages", [])
    for m in msgs:
        for tc in (m.get("tool_calls") if isinstance(m, dict) else None) or []:
            name = tc.get("name", "")
            if name.startswith(("start_", "check_", "update_", "cancel_", "list_")):
                print(f"   [工具] {name} -> {json.dumps(tc.get('args', {}), ensure_ascii=False)[:150]}")
    return msgs[-1].get("content", "") if msgs else ""


async def turn(thread_id, content, label):
    state = await client.runs.wait(thread_id, ASSISTANT, input={"messages": [{"role": "user", "content": content}]})
    print(f"\n=== {label} ===")
    text = show(state)
    print("   [回复]", text[:260].replace(chr(10), " "))
    return state


async def main():
    thread = await client.threads.create()
    tid = thread["thread_id"]
    print("thread_id =", tid)

    await turn(tid, "请同时启动两个后台调研任务交给 researcher：任务A 调研 context engineering 的关键手法；任务B 调研 multi-agent 编排模式。两个都要启动，然后把两个任务 ID 都告诉我。", "第 1 轮：并行启动 A、B 两个后台任务")

    await turn(tid, "任务B 不需要了，请取消它。然后用 list 查看所有任务的当前状态。", "第 2 轮：取消 B + 列出全部任务")

    print("\n（等待 A 完成……）")
    await asyncio.sleep(32)
    await turn(tid, "现在查看任务A 的结果。", "第 3 轮：确认 A 完成且不受 B 取消影响")

asyncio.run(main())
