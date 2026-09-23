# 第 8 章 · 实验：用户级长期记忆 —— 跨会话持久化 + 用户隔离双验证
# 同一个 Agent：user-123 的线程 A 写偏好 → 线程 B 还能记得（跨会话持久）
#                user-456 的线程 C 读不到 user-123 的偏好（namespace 隔离）
import os
from dataclasses import dataclass

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


@dataclass(frozen=True)
class MemoryContext:
    user_id: str = "local-user"
    org_id: str = "default-org"


def user_namespace(rt):
    if rt.server_info and rt.server_info.user:
        return (rt.server_info.user.identity,)
    return (getattr(rt.context, "user_id", "local-user"),)


agent = create_deep_agent(
    model=model,
    context_schema=MemoryContext,
    memory=["/memories/preferences.md"],  # 启动时自动注入已有记忆
    backend=CompositeBackend(
        default=StateBackend(),
        routes={
            "/memories/": StoreBackend(namespace=lambda rt: (*user_namespace(rt), "memories")),
        },
    ),
    store=InMemoryStore(),  # StoreBackend 的底层存储（教程示例省略，缺了会 NoneType 报错）
    checkpointer=MemorySaver(),
    system_prompt="你是个人助理。回答偏好类问题时，优先依据 /memories/preferences.md 中的记忆；没有记忆就如实说不知道。",
)

CFG = "configurable"
THREAD_KEY = "thread_id"


def session(label, user_id, thread_id, question):
    result = agent.invoke(
        {"messages": [{"role": "user", "content": question}]},
        context=MemoryContext(user_id=user_id),
        config={CFG: {THREAD_KEY: thread_id}},
    )
    print(f"=== {label} ===")
    print("问:", question)
    print("答:", str(result["messages"][-1].content)[:220].replace(chr(10), " "))
    print()
    return result


# 会话 1：user-123 在线程 A 里写下偏好（写入 /memories/ → StoreBackend 持久化）
session("会话 1 · user-123 · thread-A（写入记忆）", "user-123", "t-A", "请记住我的偏好：我喜欢的代码风格是简洁风格，技术选型偏爱 Python 生态，汇报格式偏爱表格。请存入你的长期记忆。")

# 会话 2：user-123 换一个全新线程 B（记忆应跨线程可见）
session("会话 2 · user-123 · thread-B（跨会话读取）", "user-123", "t-B", "我的偏好是什么？")

# 会话 3：user-456 全新线程 C（namespace 隔离，应读不到 user-123 的记忆）
session("会话 3 · user-456 · thread-C（隔离验证）", "user-456", "t-C", "我的偏好是什么？")
