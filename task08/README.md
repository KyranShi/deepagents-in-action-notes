# Weekly Digest Agent · 每周技术情报员

> 《Deep Agents 实战》Task08 综合实战项目 —— 一个替你追踪 Agent 领域动态、按你的偏好产出周报、发布前必须经你审批的 Deep Agent。
> 详细实践笔记见 [../task08.md](../task08.md)。

## 它能做什么

给它一个主题（如「Deep Agents / LangGraph 本周动态」），它会：

1. 制定周报产出计划（Todo 可见）
2. 把联网调研委派给专职 `researcher` 子 Agent（上下文隔离）
3. 结合它记住的你的偏好，起草周报到 `/workspace/digest_draft.md`
4. 提交发布前**暂停等你审批**（HITL），批准后才正式发布

## 综合的课程能力（5 项 ≥ 评审要求的 3 项）

| 能力 | 来源章节 | 在本项目中的体现 |
|---|---|---|
| 虚拟文件系统 | 第 3 章 | 草稿/终稿写入 State 文件系统，与对话历史解耦 |
| 任务规划 | 第 4 章 | `TodoListMiddleware`，write_todos 全程状态流转 |
| 子 Agent 隔离 | 第 5 章 | researcher 只配搜索工具，多轮搜索不膨胀主上下文 |
| 长期记忆 | 第 8 章 | `/memories/` → 用户级 StoreBackend，偏好跨会话生效 |
| Human-in-the-Loop | 第 9 章 | `publish_digest` 必须人工 approve 才发布 |

## 快速开始

```bash
# 1) 环境（Python 3.13+）
uv venv --python 3.13 && uv pip install deepagents langchain-openai tavily-python python-dotenv

# 2) 配置 .env（同目录）
#    GLM_API_KEY=你的智谱Key        （https://open.bigmodel.cn）
#    TAVILY_API_KEY=你的TavilyKey   （https://tavily.com）
#    MODEL_NAME=glm-5.3-flash

# 3) 运行
python digest_agent.py
```

脚本会依次演示：写入偏好记忆 → 全新线程执行周报任务 → HITL 中断（脚本自动以 approve 恢复）→ 发布完成，并把周报草稿落盘为 `digest_draft.md`。

## 演示记录（真实运行摘录）

```text
=== 会话 1：写入周报偏好到长期记忆（thread-pref） ===
[回复] 周报偏好已保存至 /memories/preferences.md：只保留 5 条最重要动态、
      全中文、每条附来源 URL、结尾 50 字趋势点评 …

=== 会话 2：全新线程执行周报任务（thread-work，记忆自动加载） ===
 -> write_todos    | 制定计划（后续多次调用推进 in_progress → completed）
 -> task           | 委派 researcher 联网调研（上下文隔离）
 -> write_file     | /workspace/digest_draft.md
 -> publish_digest | 提交发布 …
[🛑 HITL 中断] publish_digest | content 1,517 字符 | ['approve','reject']
[人工决策] approve
[恢复后] write_todos 收尾 → 全部 completed
[最终回复] 本期周报已正式发布，订阅者已收到通知 …
发布记录: ['技术周报 · Deep Agents / LangGraph / Agent Harness 本周动态']
```

发布产物示例见 [digest_draft.md](./digest_draft.md)：严格 5 条动态、每条带来源 URL、结尾 50 字趋势点评 —— 与记忆中的偏好逐条对应。

## 设计要点

- **审批工具签名即审批体验**：`publish_digest(title, content)` 让审批界面直接展示标题与全文字数，10 秒可做出有依据的决策。
- **韧性**：搜索工具内部走 curl 子进程调用 Tavily REST（网络对 Python TLS 不稳时的兜底），对 Agent 透明。
- **记忆验证方式**：检查产物特征（恰好 5 条、带 URL、有点评）而非口头问 Agent"你记得吗"。
