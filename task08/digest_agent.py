# Task08 · 综合实战：每周技术情报员（Weekly Digest Agent）
# 一个 Agent 串起课程核心能力：
#   第 3 章 文件系统   → 草稿写 /workspace/draft.md，终稿经审批写入正式路径
#   第 4 章 任务规划   → TodoListMiddleware，先拆解再执行
#   第 5 章 子 Agent   → 调研委派给 researcher（上下文隔离）
#   第 8 章 长期记忆   → /memories/ 路由到用户级 StoreBackend，周报偏好跨会话生效
#   第 9 章 HITL       → publish_digest 必须人工审批后才正式发布
import json
import os
import uuid
from dataclasses import dataclass

from dotenv import load_dotenv
from langchain.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import MemorySaver
from langgraph.store.memory import InMemoryStore
from langgraph.types import Command
from deepagents import create_deep_agent
from deepagents.backends import CompositeBackend, StateBackend, StoreBackend

load_dotenv(".env")

model = ChatOpenAI(
    model=os.environ.get("MODEL_NAME", "glm-5.3-flash"),
    api_key=os.environ["GLM_API_KEY"],
    base_url="https://open.bigmodel.cn/api/paas/v4",
)

def internet_search(query: str, max_results: int = 5) -> dict:
    """搜索互联网获取最新信息。"""
    # 注：网络对 Python TLS 不稳定，走 curl 子进程调用 Tavily REST API（与官方 SDK 返回结构一致）
    import json as _json
    import subprocess
    payload = _json.dumps({"api_key": os.environ["TAVILY_API_KEY"], "query": query, "max_results": max_results})
    out = subprocess.run(
        ["curl", "-sS", "-m", "30", "https://api.tavily.com/search",
         "-H", "Content-Type: application/json", "-d", payload],
        capture_output=True, text=True, check=True,
    )
    return _json.loads(out.stdout)


PUBLISHED = []


@tool
def publish_digest(title: str, content: str) -> str:
    """将周报终稿正式发布（写入发布目录并通知订阅者）。只有草稿经确认后才应调用。"""
    PUBLISHED.append(title)
    return f"周报《{title}》已正式发布（{len(content)} 字符），并已通知订阅者。"


@dataclass(frozen=True)
class MemoryContext:
    user_id: str = "local-user"


def user_namespace(rt):
    if rt.server_info and rt.server_info.user:
        return (rt.server_info.user.identity,)
    return (getattr(rt.context, "user_id", "local-user"),)


agent = create_deep_agent(
    model=model,
    tools=[publish_digest],
    middleware=[__import__("langchain.agents.middleware", fromlist=["TodoListMiddleware"]).TodoListMiddleware()],
    backend=CompositeBackend(
        default=StateBackend(),
        routes={"/memories/": StoreBackend(namespace=lambda rt: (*user_namespace(rt), "memories"))},
    ),
    memory=["/memories/preferences.md"],
    store=InMemoryStore(),
    checkpointer=MemorySaver(),
    subagents=[
        {
            "name": "researcher",
            "description": "联网调研最新技术动态：多轮搜索、整理成精炼纪要返回",
            "system_prompt": "你是技术情报研究员：用 internet_search 多轮搜索指定领域本周动态，返回 500 字以内要点纪要（每条附来源 URL）。",
            "tools": [internet_search],
        },
    ],
    interrupt_on={"publish_digest": {"allowed_decisions": ["approve", "reject"]}},
    system_prompt="""你是「每周技术情报员」，负责产出技术领域周报。
标准流程：
1. 用 write_todos 制定计划
2. 把资料调研委派给 researcher
3. 结合用户记忆中的周报偏好，把草稿用 write_file 写入 /workspace/digest_draft.md
4. 草稿完成后调用 publish_digest 提交发布（会触发人工审批）
用户偏好以 /memories/preferences.md 为准。""",
)

TASK = "请产出本期周报，主题：Deep Agents / LangGraph / Agent Harness 领域本周值得关注的动态。"


def extract_interruptions(result):
    v2 = getattr(result, "interrupts", None)
    if v2:
        return [i.value for i in v2]
    if isinstance(result, dict):
        return [i.get("value", {}) for i in result.get("__interrupt__", [])]
    return []


def show_tools(result, since=0):
    msgs = result["messages"] if isinstance(result, dict) else result.value["messages"]
    for m in msgs[since:]:
        for tc in getattr(m, "tool_calls", None) or []:
            args = tc.get("args", {})
            brief = args.get("query") or args.get("file_path") or args.get("description") or str(args)[:60]
            print("   ->", tc["name"], "|", str(brief)[:90])
    return len(msgs)


print("=== 会话 1：写入周报偏好到长期记忆（thread-pref） ===")
r0 = agent.invoke(
    {"messages": [{"role": "user", "content": "请记住我的周报偏好：只保留 5 条最重要动态，中文撰写，每条必须附来源 URL，结尾给一段 50 字以内的趋势点评。请存入长期记忆。"}]},
    context=MemoryContext(user_id="user-123"),
    config={"configurable": {"thread_id": "thread-pref"}},
)
print("[回复]", str(r0["messages"][-1].content)[:200].replace(chr(10), " "))

print()
print("=== 会话 2：全新线程执行周报任务（thread-work，记忆自动加载） ===")
config = {"configurable": {"thread_id": str(uuid.uuid4())}}
result = agent.invoke({"messages": [{"role": "user", "content": TASK}]},
                      context=MemoryContext(user_id="user-123"), config=config, version="v2")
n = 0
print("[工具时序]")
n = show_tools(result)

interrupts = extract_interruptions(result)
if interrupts:
    iv = interrupts[0]
    for action in iv.get("action_requests", []):
        args = action.get("arguments") or action.get("args") or {}
        print()
        print(f"[🛑 HITL 中断] {action['name']} | title={args.get('title')!r} | content {len(str(args.get('content','')))} 字符")
    print("[人工决策] approve（周报偏好已按记忆执行，批准发布）")
    result = agent.invoke(Command(resume={"decisions": [{"type": "approve"}]}),
                          context=MemoryContext(user_id="user-123"), config=config, version="v2")
    print("[恢复后工具时序]")
    show_tools(result, since=n)

print()
print("[最终回复]", str((result["messages"] if isinstance(result, dict) else result.value["messages"])[-1].content)[:400].replace(chr(10), " "))
print()
print("发布记录:", PUBLISHED)

st = result if isinstance(result, dict) else getattr(result, "value", None) or {}
files = st.get("files") if isinstance(st, dict) else {}
files = files if isinstance(files, dict) else {}
for path in ("/workspace/digest_final.md", "/workspace/digest_draft.md"):
    content = files.get(path)
    if isinstance(content, dict):
        content = content.get("content", "")
    if content:
        out = "digest_final.md" if "final" in path else "digest_draft.md"
        with open(out, "w") as f:
            f.write(str(content))
        print(f"已落盘 {out}（{len(content)} 字符）")
