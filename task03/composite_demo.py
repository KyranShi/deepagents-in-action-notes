# 第 3 章 · 实验 3（评优加分）：CompositeBackend 混合路由
# /memories/ 前缀路由到 StoreBackend（跨线程持久），其余路径走 StateBackend（临时）
import os

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import MemorySaver
from langgraph.store.memory import InMemoryStore
from deepagents import create_deep_agent
from deepagents.backends import CompositeBackend, StateBackend, StoreBackend

load_dotenv(".env")

model = ChatOpenAI(
    model=os.environ.get("MODEL_NAME", "glm-5.3-flash"),
    api_key=os.environ["GLM_API_KEY"],
    base_url="https://open.bigmodel.cn/api/paas/v4",
)

TASK = "请创建两个文件：/memories/user_pref.txt 内容为「用户偏好：简洁风格」；/drafts/idea.txt 内容为「一个临时的想法」。完成后用一句话确认。"

agent = create_deep_agent(
    model=model,
    backend=CompositeBackend(
        default=StateBackend(),
        routes={
            "/memories/": StoreBackend(
                # 教程提示：本地 invoke 时 rt.server_info 为 None，需要兜底
                namespace=lambda rt: (
                    (rt.server_info.user.identity,) if rt.server_info else ("local-user",)
                ),
            ),
        },
    ),
    store=InMemoryStore(),
    checkpointer=MemorySaver(),
)


def ask(thread_id, task):
    cfg = {"configurable": {"thread_id": thread_id}}
    return agent.invoke({"messages": [{"role": "user", "content": task}]}, config=cfg)


r1 = ask("thread-1", TASK)
print("=== thread-1 工具调用 ===")
for m in r1["messages"]:
    for tc in getattr(m, "tool_calls", None) or []:
        print(" ->", tc["name"], "| 参数:", str(tc.get("args", ""))[:80])

r2 = ask("thread-2", "请用 ls 分别查看 /memories/ 和 /drafts/ 目录，报告哪些文件还在。")
print()
print("=== thread-2（全新线程）ls 结果 ===")
print(r2["messages"][-1].content)

print()
print("=== 结论 ===")
print("/memories/ 路由到 StoreBackend（Store 持久）→ 换线程仍在")
print("/drafts/   走默认 StateBackend（State 临时）→ 换线程即失")
