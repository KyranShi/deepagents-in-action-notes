# 第 6 章 · SDK 验证异步生命周期：启动 → 查进度 → 追加约束 → 确认完成
import asyncio
import json

from langgraph_sdk import get_client

client = get_client(url="http://127.0.0.1:2024")
assistant_id = "supervisor"


def last_text(state):
    msgs = state.get("messages", [])
    return msgs[-1].get("content", "") if msgs else ""


async def turn(thread_id, content, label):
    state = await client.runs.wait(
        thread_id,
        assistant_id,
        input={"messages": [{"role": "user", "content": content}]},
    )
    print(f"\n=== {label} ===")
    for m in state.get("messages", []):
        calls = m.get("tool_calls") if isinstance(m, dict) else None
        for tc in calls or []:
            if str(tc.get("name", "")).startswith(("start_", "check_", "update_", "cancel_", "list_")):
                print(f"  [工具] {tc['name']} -> {json.dumps(tc.get('args', {}), ensure_ascii=False)[:120]}")
    print("  [回复]", last_text(state)[:400])
    return state


async def main():
    import time
    thread = await client.threads.create()
    thread_id = thread["thread_id"]
    print("thread_id =", thread_id)

    t0 = time.time()
    await turn(thread_id, "请把这个任务交给 researcher 异步处理：用后台任务总结 async subagent 的关键行为。", "第 1 轮：启动后台任务")
    print(f"  （第 1 轮耗时 {time.time()-t0:.1f}s —— 远小于 8s 即证明未阻塞）")

    await turn(thread_id, "刚才那个后台任务现在进展如何？", "第 2 轮：查询进度（预期 running）")

    await turn(thread_id, "补充约束：完成时请把答案写成 3 条 bullet。", "第 3 轮：向运行中的任务追加指令")

    await asyncio.sleep(32)  # 等 researcher 的 30s sleep 结束
    await turn(thread_id, "现在再查一次进度。", "第 4 轮：确认完成（预期 success）")


asyncio.run(main())
