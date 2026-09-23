# 第 9 章 · 实验：Human-in-the-Loop 完整中断-恢复流程
# 场景 A：send_email 触发中断 → 人工 edit（改收件人）→ 放行执行
# 场景 B：delete_file 触发中断 → 人工 reject（附反馈）→ Agent 改用归档方案
import os
import uuid

from dotenv import load_dotenv
from langchain.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command
from deepagents import create_deep_agent

load_dotenv(".env")

model = ChatOpenAI(
    model=os.environ.get("MODEL_NAME", "glm-5.3-flash"),
    api_key=os.environ["GLM_API_KEY"],
    base_url="https://open.bigmodel.cn/api/paas/v4",
)

SENT = []


@tool
def send_email(to: str, subject: str, body: str) -> str:
    """发送邮件。"""
    SENT.append((to, subject))
    return f"邮件已发送至 {to}（主题：{subject}）"


@tool
def archive_file(path: str) -> str:
    """把文件归档而不是删除。"""
    return f"已将 {path} 归档"


agent = create_deep_agent(
    model=model,
    tools=[send_email, archive_file],
    interrupt_on={
        "send_email": {"allowed_decisions": ["approve", "edit", "reject"]},
        "delete": {"allowed_decisions": ["approve", "edit", "reject"]},  # 内置文件系统的 delete 工具
        "archive_file": False,
    },
    checkpointer=MemorySaver(),  # HITL 必须配 checkpointer
    system_prompt="你是运维助理。涉及发邮件、删文件的操作必须走审批工具；被拒绝后按反馈调整方案。",
)


def extract_interruptions(result):
    v2 = getattr(result, "interrupts", None)
    if v2:
        return [i.value for i in v2]
    if isinstance(result, dict):
        return [i.get("value", {}) for i in result.get("__interrupt__", [])]
    return []


def get_final(result):
    value = getattr(result, "value", None)
    if value is not None:
        return value["messages"][-1].content
    return result["messages"][-1].content


def run(label, first_input, decisions, decision_note):
    print(f"===== 场景 {label} =====")
    config = {"configurable": {"thread_id": str(uuid.uuid4())}}
    result = agent.invoke({"messages": [first_input]}, config=config, version="v2")

    interrupts = extract_interruptions(result)
    if not interrupts:
        print("!! 未触发中断，实际工具调用：")
        for m in result["messages"]:
            for tc in getattr(m, "tool_calls", None) or []:
                print("   ->", tc["name"], tc.get("args"))
        return
    iv = interrupts[0]
    for action in iv.get("action_requests", []):
        args = action.get("arguments") or action.get("args") or {}
        cfg_next = next((c for c in iv.get("review_configs", []) if c.get("action_name") == action["name"]), {})
        print(f"[中断] 工具: {action['name']} | 参数: {args} | 可选决策: {cfg_next.get('allowed_decisions')}")

    print(f"[人工决策] {decision_note}")
    result = agent.invoke(Command(resume={"decisions": decisions}), config=config, version="v2")
    print("[最终回复]", str(get_final(result))[:280].replace(chr(10), " "))
    print()


# 场景 A：批准但要改参数（edit：收件人换成团队公共邮箱）
run(
    "A · edit 后放行",
    {"role": "user", "content": "请给 boss@example.com 发一封邮件，主题「周报」，内容：本周完成 Deep Agents 课程实验。"},
    [{"type": "edit", "args": {"to": "team@example.com", "subject": "周报", "body": "本周完成 Deep Agents 课程实验。"}, "edited_action": {"name": "send_email", "args": {"to": "team@example.com", "subject": "周报", "body": "本周完成 Deep Agents 课程实验。"}}}],
    "edit：收件人 boss@example.com → team@example.com",
)
print("实际发送记录:", SENT, "\n")

# 场景 B：拒绝并给出反馈（Agent 应改走归档）
run(
    "B · reject + 反馈",
    {"role": "user", "content": "删除 /workspace/draft_old.txt。"},
    [{"type": "reject", "message": "用户拒绝删除该文件。不要再次尝试删除，请改用 archive_file 归档它。"}],
    "reject：删除改为归档",
)
print("[最终确认] SENT 列表长度应为 1（场景 B 不发邮件）:", len(SENT) == 1)
