# 第 3 章 · 实验 1：让 Agent 亲手使用文件工具七件套
# 与教程差异：模型用智谱 GLM（OpenAI 兼容），其余按教程默认（StateBackend）
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

TASK = """请在你的虚拟文件系统中完成以下操作，每一步都使用对应的文件工具：
1. 用 write_file 创建 /workspace/meetup.md，写入三行会议纪要（主题、时间、结论各一行）；
2. 用 ls 查看 /workspace/ 目录；
3. 用 read_file 读回 /workspace/meetup.md 全文确认内容；
4. 用 edit_file 把「结论」那一行修改为「结论：每周四同步，负责人待定」；
5. 用 grep 在 /workspace 里搜索关键词「周四」；
6. 最后用一句话汇报以上每步是否成功。
"""

agent = create_deep_agent(model=model)  # 默认 StateBackend

result = agent.invoke({"messages": [{"role": "user", "content": TASK}]})

print("=== 工具调用时序 ===")
for m in result["messages"]:
    for tc in getattr(m, "tool_calls", None) or []:
        print(" ->", tc["name"], "| 参数:", str(tc.get("args", ""))[:90])

print()
print("=== 最终回答 ===")
print(result["messages"][-1].content)

print()
print("=== StateBackend 落点验证：Agent State 中的 files ===")
files = result.get("files") or {}
for path, content in (files.items() if isinstance(files, dict) else []):
    text = content if isinstance(content, str) else str(content)
    print(f"  {path} ({len(text)} chars)")
