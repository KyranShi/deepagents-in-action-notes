# 第 7 章 · Skills 实验：验证渐进式加载（元数据 → SKILL.md 正文 → references 资源）
# FilesystemBackend + skills=["/skills/"]，两个技能做匹配排他性对照
import os

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from deepagents import create_deep_agent
from deepagents.backends import FilesystemBackend

load_dotenv("../.env")

model = ChatOpenAI(
    model=os.environ.get("MODEL_NAME", "glm-5.3-flash"),
    api_key=os.environ["GLM_API_KEY"],
    base_url="https://open.bigmodel.cn/api/paas/v4",
)

agent = create_deep_agent(
    model=model,
    backend=FilesystemBackend(root_dir=".", virtual_mode=True),
    skills=["/skills/"],
    system_prompt="你是一位严谨的写作助手，严格按可用技能中的规范完成任务。",
)


def run(label, question):
    result = agent.invoke(
        {"messages": [{"role": "user", "content": question}]},
        config={"configurable": {"thread_id": label}},
    )
    print(f"=== {label} ===")
    print("问题:", question[:60])
    for m in result["messages"]:
        for tc in getattr(m, "tool_calls", None) or []:
            args = tc.get("args", {})
            print("  ->", tc["name"], "|", str(args.get("file_path") or args.get("path") or str(args)[:50]))
    print("  [回复]", str(result["messages"][-1].content)[:260].replace("\n", " "))
    print()


# 场景 A：笔记类请求 → 应命中 notes-style（读 SKILL.md → 读 references）
run("A-skill-hit", "请按团队的笔记规范，帮我写一段 Task06 的学习心得（我做的是异步子 Agent 实验）。")

# 场景 B：无关请求 → 不应读取任何 SKILL.md（排他性对照）
run("B-skill-miss", "1+1 等于几？")
