# 第 4 章 · 复盘实验：同一个 Agent，简单任务 vs 复杂任务的 write_todos 触发对比
# 呼应 Task02 的观察：工具存在 ≠ 必然调用（v0.7 按需启用设计）
import os

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from deepagents import create_deep_agent
from langchain.agents.middleware import TodoListMiddleware

load_dotenv(".env")

model = ChatOpenAI(
    model=os.environ.get("MODEL_NAME", "glm-5.3-flash"),
    api_key=os.environ["GLM_API_KEY"],
    base_url="https://open.bigmodel.cn/api/paas/v4",
)

agent = create_deep_agent(
    model=model,
    middleware=[TodoListMiddleware()],
    system_prompt="你是一位专业的技术研究员，面对复杂研究任务时会先用 write_todos 制定计划再逐步执行。",
)

CASES = [
    ("简单任务", "什么是 Deep Agents？用两句话回答。"),
    ("复杂任务", "调研 LangGraph 与 CrewAI 两个框架的定位差异、各自适合的场景，并给出选型建议，输出一份结构化小结。"),
]

for label, task in CASES:
    result = agent.invoke({"messages": [{"role": "user", "content": task}]})
    writes = sum(
        1
        for m in result["messages"]
        for tc in (getattr(m, "tool_calls", None) or [])
        if tc["name"] == "write_todos"
    )
    todos = result.get("todos") or []
    print(f"[{label}] write_todos 调用次数: {writes} | 最终清单条目数: {len(todos)}")
    for t in todos:
        print(f"   [{t.get('status')}] {t.get('content')}")
    print()
