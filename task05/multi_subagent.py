# 第 5 章 · 主实验：两个职责不同的子 Agent 协作 + 上下文隔离取证
# 角色 A researcher：配 Tavily 搜索工具，负责深入调研（大量搜索发生在它的隔离上下文里）
# 角色 B analyst：  无搜索工具，专职整理材料、撰写对比报告
# 主 Agent：        只做协调，通过 task() 委派
import json
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
    # 注：当前网络环境对 Python TLS 连 api.tavily.com 有干扰（curl 正常），
    # 故通过 curl 子进程调用 Tavily REST API，返回结构与官方 SDK 一致。
    import json as _json
    import subprocess
    payload = _json.dumps({"api_key": os.environ["TAVILY_API_KEY"], "query": query, "max_results": max_results})
    out = subprocess.run(
        ["curl", "-sS", "-m", "30", "https://api.tavily.com/search",
         "-H", "Content-Type: application/json", "-d", payload],
        capture_output=True, text=True, check=True,
    )
    return _json.loads(out.stdout)


researcher = {
    "name": "researcher",
    "description": "深入研究特定技术主题：拆解搜索查询、多轮联网搜索、整理成精炼摘要。凡需要外部最新信息的调研都委派给它。",
    "system_prompt": """你是一位技术研究员。你的任务是：
1. 把研究问题拆解为多个具体的搜索查询
2. 用 internet_search 多轮搜索（中英文都可以）
3. 整理核心发现，列出信息来源
注意：最终返回给协调者的结果控制在 600 字以内，只返回核心发现，不要展开搜索过程。""",
    "tools": [internet_search],  # 显式指定：researcher 只有搜索工具
}

analyst = {
    "name": "analyst",
    "description": "把调研材料整理成结构化对比报告并写入文件系统。不做联网搜索，只基于收到的材料工作。",
    "system_prompt": """你是一位技术分析师。你收到的材料来自调研同事。
你的任务：
1. 基于材料提炼对比维度（定位、核心能力、模型绑定、适用场景等）
2. 用 write_file 把完整的对比分析报告写入 /workspace/report.md
3. 返回给协调者一段 100 字以内的完成确认（含报告要点）""",
    "tools": [],  # 显式置空：analyst 没有搜索工具，只用文件系统工具
}

agent = create_deep_agent(
    model=model,
    subagents=[researcher, analyst],
    system_prompt="""你是项目协调者。收到调研+写报告类任务时：
1. 先委派 researcher 完成资料调研
2. 把调研结果转交 analyst，由它撰写对比报告并存入 /workspace/report.md
3. 你自己不要直接联网搜索，也不要亲自撰写长报告，只做协调与汇总""",
)

TASK = "调研 LangGraph 与 CrewAI 两个框架的定位与能力差异，并产出一份对比分析报告保存下来。"

result = agent.invoke({"messages": [{"role": "user", "content": TASK}]})

print("=== 主 Agent 上下文中的工具调用时序 ===")
main_searches = 0
for m in result["messages"]:
    for tc in getattr(m, "tool_calls", None) or []:
        name = tc["name"]
        args = tc.get("args", {})
        if name == "task":
            print(f" -> task | {args}")
        elif name == "internet_search":
            main_searches += 1
            print(f" -> internet_search | {args.get('query')}")
        else:
            print(f" -> {name} | {str(args)[:70]}")

print()
print(f"=== 隔离证据：主 Agent 消息流中 internet_search 出现 {main_searches} 次 ===")
print("=== task() 的 ToolMessage：子 Agent 回传给主 Agent 的唯一内容 ===")
for m in result["messages"]:
    mtype = m.get("type") if isinstance(m, dict) else getattr(m, "type", "")
    mname = m.get("name") if isinstance(m, dict) else getattr(m, "name", "")
    if mtype == "tool" and mname == "task":
        content = str(m.get("content") if isinstance(m, dict) else getattr(m, "content", ""))
        print(f"[回传 {len(content)} 字符] {content[:150]}...")

files = result.get("files") or {}
report = files.get("/workspace/report.md")
if isinstance(report, dict):
    report = report.get("content", "")
print()
if report:
    with open("multi_agent_report.md", "w") as f:
        f.write(report)
    print(f"=== /workspace/report.md 已取出落盘 multi_agent_report.md（{len(report)} 字符） ===")
else:
    print("!!! State 中未找到 /workspace/report.md")
