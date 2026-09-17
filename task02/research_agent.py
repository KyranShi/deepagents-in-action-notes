# 第 2 章 · 实战：研究助手（Tavily 搜索 + TodoListMiddleware）
import os
from typing import Literal

from dotenv import load_dotenv
from tavily import TavilyClient
from langchain_openai import ChatOpenAI
from deepagents import create_deep_agent
from langchain.agents.middleware import TodoListMiddleware

load_dotenv()

model = ChatOpenAI(
    model=os.environ.get("MODEL_NAME", "glm-5.3-flash"),
    api_key=os.environ["GLM_API_KEY"],
    base_url="https://open.bigmodel.cn/api/paas/v4",
)

tavily_client = TavilyClient(api_key=os.environ["TAVILY_API_KEY"])


def internet_search(
    query: str,
    max_results: int = 5,
    topic: Literal["general", "news", "finance"] = "general",
    include_raw_content: bool = False,
):
    """Run a web search for the given query.

    Args:
        query: The search query string.
        max_results: Maximum number of results to return.
        topic: The topic category for the search.
        include_raw_content: Whether to include raw page content.
    """
    return tavily_client.search(
        query,
        max_results=max_results,
        include_raw_content=include_raw_content,
        topic=topic,
    )


research_instructions = """你是一位专业的研究员。
你的工作是进行深入研究，然后撰写一份完整的研究报告。

你可以使用 internet_search 工具搜索互联网获取信息。
"""

agent = create_deep_agent(
    model=model,
    tools=[internet_search],
    system_prompt=research_instructions,
    middleware=[TodoListMiddleware()],
)

if __name__ == "__main__":
    result = agent.invoke(
        {"messages": [{"role": "user", "content": "什么是 LangGraph？"}]}
    )

    print("=== 最终回答 ===")
    print(result["messages"][-1].content)
    print()
    print("=== 本次运行统计 ===")
    print("消息总数:", len(result["messages"]))
    todos = result.get("todos")
    print("write_todos 生效:", todos is not None, "| 计划步骤数:", len(todos) if todos else 0)
    tool_calls = [m for m in result["messages"] if getattr(m, "tool_calls", None)]
    for m in tool_calls:
        for tc in m.tool_calls:  # AIMessage 是对象，用属性访问而不是下标
            print("工具调用:", tc["name"], "| 参数:", str(tc.get("args", ""))[:60])
