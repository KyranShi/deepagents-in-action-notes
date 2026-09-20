# 第 3 章 · 实验 2：StateBackend vs FilesystemBackend 对比实验（评审核心）
# 同样的写文件任务，回答三个问题：
#   Q1 文件写到了哪里（Agent State 还是真实磁盘）？
#   Q2 同一线程再启动还能看到吗（线程内持久化，需要 checkpointer）？
#   Q3 换一个全新线程还能看到吗（跨线程持久化）？
import os
import shutil

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import MemorySaver
from deepagents import create_deep_agent
from deepagents.backends import FilesystemBackend

load_dotenv(".env")

model = ChatOpenAI(
    model=os.environ.get("MODEL_NAME", "glm-5.3-flash"),
    api_key=os.environ["GLM_API_KEY"],
    base_url="https://open.bigmodel.cn/api/paas/v4",
)

WRITE_TASK = "请用 write_file 创建 /workspace/persist_test.txt，内容为一行文字：hello backend"
LIST_TASK = "请用 ls 查看 /workspace/ 目录下有哪些文件，并直接报告结果。"
DISK_TARGET = "workspace/persist_test.txt"  # root_dir="." 时，Agent 的 /workspace/x 落在磁盘 ./workspace/x


def ask(agent, thread_id, task):
    cfg = {"configurable": {"thread_id": thread_id}}
    return agent.invoke({"messages": [{"role": "user", "content": task}]}, config=cfg)


def state_files(result):
    files = result.get("files") or {}
    return list(files.keys()) if isinstance(files, dict) else []


print("=" * 62)
print("A. StateBackend（默认，挂 MemorySaver checkpointer）")
print("=" * 62)
agent_state = create_deep_agent(model=model, checkpointer=MemorySaver())

r1 = ask(agent_state, "thread-1", WRITE_TASK)
print("写入后  | thread-1 State files:", state_files(r1), "| 磁盘文件存在:", os.path.exists(DISK_TARGET))

r2 = ask(agent_state, "thread-1", LIST_TASK)
print("同线程  | thread-1 再 ls  :", r2["messages"][-1].content.strip()[:80])

r3 = ask(agent_state, "thread-2", LIST_TASK)
print("换线程  | thread-2 再 ls  :", r3["messages"][-1].content.strip()[:80])

print()
print("=" * 62)
print('B. FilesystemBackend(root_dir=".", virtual_mode=True)')
print("=" * 62)
shutil.rmtree("workspace", ignore_errors=True)  # 清空磁盘工作区，保证结论干净
agent_fs = create_deep_agent(
    model=model,
    # root_dir="." 时 Agent 的 /workspace/x 对应磁盘 ./workspace/x，路径映射直观
    backend=FilesystemBackend(root_dir=".", virtual_mode=True),
)

r4 = ask(agent_fs, "thread-1", WRITE_TASK)
print("写入后  | thread-1 State files:", state_files(r4), "| 磁盘文件存在:", os.path.exists(DISK_TARGET))
if os.path.exists(DISK_TARGET):
    print("        | 磁盘内容:", repr(open(DISK_TARGET).read()))

r5 = ask(agent_fs, "thread-1", LIST_TASK)
print("同线程  | thread-1 再 ls  :", r5["messages"][-1].content.strip()[:80])

r6 = ask(agent_fs, "thread-2", LIST_TASK)
print("换线程  | thread-2 再 ls  :", r6["messages"][-1].content.strip()[:80])

print()
print("=" * 62)
print("对比结论")
print("=" * 62)
rows = [
    ("文件真实落点", "Agent State（内存）", "本地磁盘 workspace/"),
    ("同线程再启动", "可见（依赖 checkpointer）", "可见（读磁盘，天然持久）"),
    ("换全新线程", "不可见，文件随 State 丢失", "仍可见"),
    ("适用场景", "草稿纸 / 单会话任务", "编程助手 / 需要落盘的产物"),
]
print(f"{'维度':<12} | {'StateBackend':<28} | FilesystemBackend")
for a, b, c in rows:
    print(f"{a:<12} | {b:<28} | {c}")
