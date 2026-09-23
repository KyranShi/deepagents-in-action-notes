# 第 5 章 · 取证实验：同一个研究子任务，「主 Agent 亲自做」vs「委派子 Agent」
# 用主 Agent 消息流里的搜索次数与工具结果体量，量化上下文隔离（Context Quarantine）
import os

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from deepagents import create_deep_agent

load_dotenv(".env")

model = ChatOpenAI(
    model=os.environ.get("MODEL_NAME", "glm-5.3-flash"),
    api_key=os.environ["GLM_API_KEY"],
    base_url="https://open.bigmodel.cn/api/paas/v4",
)


def internet_search(query: str, max_results: int = 5) -> dict:
    """搜索互联网获取最新信息。"""
    # 注：当前网络环境对 Python TLS 连 api.tavily.com 有干扰，走 curl 子进程调用 Tavily。
    import json as _json
    import subprocess
    payload = _json.dumps({"api_key": os.environ["TAVILY_API_KEY"], "query": query, "max_results": max_results})
    out = subprocess.run(
        ["curl", "-sS", "-m", "30", "https://api.tavily.com/search",
         "-H", "Content-Type: application/json", "-d", payload],
        capture_output=True, text=True, check=True,
    )
    return _json.loads(out.stdout)


SUBJECT = "LangGraph 的核心概念、典型应用场景，以及它与 LangChain 的关系"


def analyze(label, result):
    searches, tool_chars = 0, 0
    for m in result["messages"]:
        for tc in getattr(m, "tool_calls", None) or []:
            if tc["name"] == "internet_search":
                searches += 1
        content = m.get("content") if isinstance(m, dict) else getattr(m, "content", "")
        if (m.get("name") if isinstance(m, dict) else getattr(m, "name", "")):
            tool_chars += len(str(content))  # ToolMessage（工具结果）体量
    print(f"[{label}]")
    print(f"  主 Agent 消息流中 internet_search 次数 : {searches}")
    print(f"  主 Agent 收到的工具结果总字符量        : {tool_chars}")
    print(f"  消息总数                               : {len(result['messages'])}")
    print()
    return searches, tool_chars


# 场景 A：主 Agent 亲自做，明示不要委派
agent_direct = create_deep_agent(
    model=model,
    tools=[internet_search],
    system_prompt="你是研究助手。请亲自使用 internet_search 多轮搜索，亲自整理并回答，不要委派给其他 Agent。",
)
r_a = agent_direct.invoke({"messages": [{"role": "user", "content": f"请深入调研：{SUBJECT}"}]})
analyze("A. 主 Agent 亲自做（3 轮搜索级任务）", r_a)

# 场景 B：委派给 researcher 子 Agent（上下文隔离）
researcher = {
    "name": "researcher",
    "description": "深入研究特定技术主题并返回精炼摘要",
    "system_prompt": "你是研究员：多轮搜索、整理核心发现，返回 400 字以内摘要给协调者，不要展开搜索过程。",
    "tools": [internet_search],
}
agent_delegated = create_deep_agent(
    model=model,
    tools=[internet_search],
    subagents=[researcher],
    system_prompt="你是协调者。调研任务一律委派给 researcher，你只汇总它的返回，自己不要联网搜索。",
)
r_b = agent_delegated.invoke({"messages": [{"role": "user", "content": f"请深入调研：{SUBJECT}"}]})
analyze("B. 委派给 researcher（上下文隔离）", r_b)

print("结论：隔离的意义不是少干活（子 Agent 里搜索照常发生），")
print("      而是搜索的中间结果不再堆进主 Agent 的上下文——主 Agent 只收精炼摘要。")
