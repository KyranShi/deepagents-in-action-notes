# 第 4 章 · 主实验：让 Agent 用 Todo 机制规划并执行一个复杂研究任务
# 教程实战示例：调研三大 Harness 框架并撰写对比分析报告
# 亮点设计：最终报告写入 /workspace/report.md，实验后从 Agent State 取出落盘为文档
import json
import os

from dotenv import load_dotenv
from tavily import TavilyClient
from langchain_openai import ChatOpenAI
from deepagents import create_deep_agent
from langchain.agents.middleware import TodoListMiddleware

load_dotenv(".env")

model = ChatOpenAI(
    model=os.environ.get("MODEL_NAME", "glm-5.3-flash"),
    api_key=os.environ["GLM_API_KEY"],
    base_url="https://open.bigmodel.cn/api/paas/v4",
)

tavily_client = TavilyClient(api_key=os.environ["TAVILY_API_KEY"])


def internet_search(query: str, max_results: int = 5) -> dict:
    """搜索互联网获取最新信息。"""
    return tavily_client.search(query, max_results=max_results)


agent = create_deep_agent(
    model=model,
    tools=[internet_search],
    middleware=[TodoListMiddleware()],
    system_prompt="""你是一位专业的技术研究员。
面对复杂研究任务时，你会：
1. 先用 write_todos 制定研究计划
2. 逐步执行每个步骤，每完成一步就及时更新任务状态
3. 将搜索结果写入文件系统整理
4. 最终把完整的研究报告用 write_file 写入 /workspace/report.md，并在回复中给出报告全文
""",
)

TASK = "请调研 Agent 开发领域的三大 Harness 框架（Deep Agents、Claude Agent SDK、Codex SDK），对比它们的核心能力差异，写一份简要分析报告。"

result = agent.invoke({"messages": [{"role": "user", "content": TASK}]})

print("=== 工具调用时序（重点观察 write_todos 的状态流转） ===")
step = 0
for m in result["messages"]:
    for tc in getattr(m, "tool_calls", None) or []:
        step += 1
        name = tc["name"]
        if name == "write_todos":
            print(f"{step:02d}. write_todos ↓")
            for t in tc["args"].get("todos", []):
                mark = {"pending": "□", "in_progress": "▶", "completed": "✓"}.get(t.get("status"), "?")
                print(f"      {mark} [{t.get('status')}] {t.get('content')}")
        else:
            args = tc.get("args", {})
            brief = args.get("query") or args.get("file_path") or str(args)[:60]
            print(f"{step:02d}. {name} | {brief}")

print()
print("=== 最终 todos 状态 ===")
print(json.dumps(result.get("todos") or [], ensure_ascii=False, indent=1))

files = result.get("files") or {}
report = files.get("/workspace/report.md")
if isinstance(report, dict):
    report = report.get("content", "")
if report:
    with open("agent_report.md", "w") as f:
        f.write(report)
    print()
    print(f"=== 研究报告已从 State 取出并落盘 agent_report.md（{len(report)} 字符） ===")
else:
    print("!!! /workspace/report.md 不在 State 中")

print()
print("=== 回复末尾 400 字 ===")
print(result["messages"][-1].content[-400:])
