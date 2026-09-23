# Deep Agents 实战 · Task08 打卡：综合实战 —— 每周技术情报员（Weekly Digest Agent）

> 课程：[《Deep Agents 实战》](https://github.com/datawhalechina/deepagents-in-action)（Datawhale 开源课程）
> 实战目标：把核心篇与进阶篇的能力组装成一个可交付的完整 Agent，跑通「记忆 → 规划 → 委派 → 起草 → 审批 → 发布」全闭环
> 实践环境：macOS · Python 3.13（独立 venv）· deepagents 0.7.18 · 模型：智谱 GLM `glm-5.3-flash`（OpenAI 兼容接口）· 搜索：Tavily
> 实践日期：2026-09-25（可复现脚本与周报草稿见 [task08/](./task08/) 目录）

---

## 一、Agent 设计：能力拼图

「每周技术情报员」——一个替我追踪 Agent 领域动态、按我的偏好出周报、发布前必须经我审批的助理。每个课程能力都有不可替代的职责：

| 课程章节 | 能力 | 在本 Agent 中的角色 |
|---|---|---|
| 第 3 章 虚拟文件系统 | 文件七件套 + State 后端 | 调研草稿写入 `/workspace/digest_draft.md`，与对话历史解耦 |
| 第 4 章 任务规划 | `TodoListMiddleware` | 先拆解「调研 → 起草 → 提交发布」再逐步推进 |
| 第 5 章 子 Agent | 字典式 `subagents` | `researcher`（只配搜索工具）承担多轮联网调研，中间结果隔离在子上下文 |
| 第 8 章 长期记忆 | CompositeBackend + 用户级 namespace | `/memories/` 持久化周报偏好，跨会话自动注入 |
| 第 9 章 HITL | `interrupt_on` | `publish_digest` 发布动作必须人工审批，防未经确认的对外输出 |

## 二、运行记录

**会话 1（thread-pref）：写入偏好到长期记忆**

```text
[回复] 周报偏好已保存至 /memories/preferences.md：1) 只保留 5 条最重要动态
      2) 全中文撰写 3) 每条必须附来源 URL 4) 结尾附 50 字以内趋势点评
```

**会话 2（全新 thread-work，记忆自动加载）：执行周报任务**

```text
[工具时序]
 -> write_todos   | 制定计划（后续多次调用推进 in_progress → completed）
 -> task          | 委派 researcher：调研 Deep Agents / LangGraph / Harness 本周动态
 -> write_file    | /workspace/digest_draft.md（结合记忆偏好起草）
 -> publish_digest | 提交发布 …
[🛑 HITL 中断] publish_digest | title='技术周报 · Deep Agents / LangGraph / Agent Harness 本周动态'
              | content 1,517 字符 | 可选决策 ['approve','reject']
[人工决策] approve（偏好已由记忆执行，批准发布）
[恢复后] write_todos 收尾 → 全部 completed
[最终回复] 本期周报已正式发布，订阅者已收到通知。草稿存于 /workspace/digest_draft.md…
发布记录: ['技术周报 · Deep Agents / LangGraph / Agent Harness 本周动态']  ← 恰好发布一次
```

产物已落盘：[task08/digest_draft.md](./task08/digest_draft.md)——**严格 5 条动态、每条带来源、结尾 50 字趋势点评**，与记忆中的偏好逐条对应。发布的周报内容本身也很“应景”：头条就是 Deep Agents 大版本更新与 Harness 的产品化趋势。

## 三、踩坑与问题复盘

**坑 1：`version="v2"` 的 invoke 返回对象与 dict 混用。**
恢复执行后想取出 `/workspace/digest_draft.md` 落盘，`result.get("files")` 静默失败——v2 接口返回的是带 `.value` 的对象而非 dict（消息可以用 `result["messages"]` 兼容访问，files 却不行）。最终按 `result if isinstance(result, dict) else result.value` 归一化后取出。同一份返回值两套访问语法，是 v2 接口最容易踩的暗坑。

**坑 2：网络对 Python TLS 的干扰会随时间漂移。**
第一次跑通后重跑时 Tavily SDK 突然 ProxyError（前一轮还正常）。沿用 Task05 的结论：工具实现层换成 curl 子进程调用 Tavily REST，Agent 行为零变化。综合实战级别的项目必须假设**外部依赖不可靠**，把韧性做在工具实现里（框架层的正解是第 4 章提到的 ToolRetryMiddleware）。

**坑 3：审批工具的参数设计决定了审批体验。**
`publish_digest(title, content)` 让中断界面能直接展示「发布标题 + 全文字数」，人可以在 10 秒内做出有依据的决策。如果工具只收一个 `draft_path`，审批者就得自己去读文件——**HITL 的可用性一半取决于工具签名设计**。

**复盘 4：记忆让「多次运行」变成「同一个助理」。**
会话 2 是全新线程，但偏好不用重说——`memory=[...]` 启动注入 + Store 持久让两次调用之间形成了连续人格。验证方法是检查产物特征（恰好 5 条、带 URL、有点评）而不是问 Agent“你记得吗”，这比口头问询更接近真实验收。

## 四、学习心得

这个综合实战最大的收获是看清了 Deep Agents 各能力之间的**分层关系**：文件系统是底座，Todo 和子 Agent 是执行架构，记忆是纵向的时间轴，HITL 是横向的安全闸门——它们不是并列的功能点，而是一个可交付 Agent 的必要剖面。把 `publish_digest` 卡在审批后面那一下尤其有产品感：Agent 能力再强，对外发布动作的所有权始终在人手里。另外整个搭建过程几乎没遇到框架阻力，遇到的问题全在外部依赖（网络）和接口细节（v2 返回值）——说明这套 Harness 的抽象确实到了可组合的成熟度。

## 五、对教程的意见及建议

1. 建议官方补一个「综合实战」参考章节：把 Todo、子 Agent、记忆、HITL 组装起来的**配置顺序与验证清单**（先记忆后规划？审批工具签名怎么设计？）——本次组装的决策过程没有现成文档可依。
2. `version="v2"` 返回对象的属性/字典混合访问建议在文档中给出统一的取值示例（messages、files、interrupts 三样各一行），避免静默失败。
3. 教程各章示例的网络工具均为直连实现，建议加一节「工具韧性」：重试（ToolRetryMiddleware）、超时、降级（如 curl 兜底）作为生产标配。

## 六、引用资料来源

- 课程仓库：https://github.com/datawhalechina/deepagents-in-action
- 各章在线阅读：https://datawhalechina.github.io/deepagents-in-action/chapters/ （第 3-9 章为本实战依赖）
- Deep Agents 官方文档：https://docs.langchain.com/oss/python/deepagents/overview
- LangGraph 文档（Interrupt / Store / Checkpointer）：https://docs.langchain.com/oss/python/langgraph/overview
- 智谱开放平台 OpenAI 接口文档：https://docs.bigmodel.cn/cn/guide/develop/openai/introduction
- Tavily API 文档：https://docs.tavily.com/
- 前序笔记：[Task01](./task01.md) · [Task02](./task02.md) · [Task03](./task03.md) · [Task04](./task04.md) · [Task05](./task05.md) · [Task06](./task06.md) · [Task07](./task07.md)
