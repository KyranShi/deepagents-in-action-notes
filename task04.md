# Deep Agents 实战 · Task04 打卡：任务规划与分解（第 4 章）

> 课程：[《Deep Agents 实战》](https://github.com/datawhalechina/deepagents-in-action)（Datawhale 开源课程）
> 对应章节：[第 4 章 任务规划与分解 — 让 Agent 学会拆解复杂任务](https://datawhalechina.github.io/deepagents-in-action/chapters/ch04-task-planning/)
> 实践环境：macOS · Python 3.13（独立 venv）· deepagents 0.7.16 · 模型：智谱 GLM `glm-5.3-flash`（OpenAI 兼容接口）· 搜索：Tavily
> 实践日期：2026-09-20（可复现脚本与 Agent 生成的研究报告见 [task04/](./task04/) 目录）

---

## 一、学习内容归纳

**为什么需要规划**：复杂任务不拆解就会漏步骤、重复劳动、半途而废。v0.7 中 `TodoListMiddleware` 需显式传入——它一次性注入三样东西：`write_todos` 工具、`todos` 状态通道、规划提示词。

**`write_todos` 数据模型**：每个任务是 `{content, status}`，状态机为 `pending → in_progress → completed`；清单持久化在 Agent State 中，即使对话历史被总结压缩也不丢。两条边界要记住：子 Agent 中 `subagents=[...]` 声明者有独立 Middleware 栈，要用规划必须自己启用；**工具存在不代表必然调用**——由模型、提示词、任务复杂度共同决定（本章实验给出了直接证据）。

**引擎盖下的中间件机制**：`write_todos` 的真身是 `TodoListMiddleware`。LangChain 中间件分两类 Hook：**Node-style**（`before_agent/before_model/after_model/after_agent`，编译为图中独立节点，适合校验/状态更新/人工中断）与 **Wrap-style**（`wrap_model_call/wrap_tool_call`，包裹单次调用，适合重试/缓存/转换）。人工中断应优先放在 Node-style——第 9 章预告。

**能力版图**：`create_deep_agent()` = 框架默认层（Filesystem/Summarization 等）+ 条件层（`subagents=`/`skills=`/`memory=`/`interrupt_on=`）+ 可选层（`middleware=[...]`：Todo、PII、Retry、CallLimit、ContextEditing 等）。v0.7 支持同名 Middleware 原位置换，但不自动合并新旧配置。

## 二、实验记录

### 实验 1（主实验）：Todo 机制驱动复杂研究任务（`todo_research_agent.py`）

按教程实战示例：Tavily 搜索 + `TodoListMiddleware` + 研究员提示词，任务为「调研 Deep Agents、Claude Agent SDK、Codex SDK 三大 Harness 框架，对比核心能力，撰写分析报告」。全程 **19 次工具调用**，其中 `write_todos` 6 次，完整观察到教程描述的三个阶段：

**阶段一：制定计划**（第 01 次调用，5 项全 pending）

```text
□ 调研 Deep Agents 框架（LangChain）的核心能力
□ 调研 Claude Agent SDK 的核心能力
□ 调研 Codex SDK（OpenAI）的核心能力
□ 整理搜索结果到文件系统
□ 撰写对比分析报告并写入 /workspace/report.md
```

**阶段二：状态流转**（第 02→12 次，`in_progress → completed` 随执行逐步推进，穿插 7 次 `internet_search`）

**阶段三：动态调整**（最有价值的观察——第 06 次调用，Agent 自行**新增**了一项计划外任务）：

```text
✓ 调研 Deep Agents 框架（LangChain）的核心能力
✓ 调研 Claude Agent SDK 的核心能力
▶ in_progress 调研 Codex SDK（OpenAI）的核心能力
□ 补充调研：三者差异对比与定位（模型绑定、开源、适用场景） ← 计划外新增！
```

**执行结果**：最终清单 6/6 全部 completed；Agent 还自主把三个框架的调研笔记分别写入 `/workspace/research/*.md`（3 次 write_file + 1 次 edit_file 修正），最后把报告写入 `/workspace/report.md`。

**研究报告文档**：实验后从 Agent State 中取出 `/workspace/report.md` 落盘为 [task04/agent_report.md](./task04/agent_report.md)（6,596 字符），内容含背景、三框架对比总表、逐项能力分析和来源链接——「小型研究报告文档」交付完成。

### 实验 2（问题复盘）：简单 vs 复杂任务的 A/B 对比（`simple_vs_complex.py`）

同一个 Agent（都启用 TodoListMiddleware），只换任务复杂度：

```text
[简单任务] 什么是 Deep Agents？    → write_todos 调用 0 次，清单 0 条
[复杂任务] LangGraph vs CrewAI 调研 → write_todos 调用 3 次，清单 5 条（全部完成）
```

## 三、问题复盘

**复盘 1：Task02 的困惑，本章拿到了答案。**
Task02 时我观察到「启用了 `TodoListMiddleware`，模型却不调用 `write_todos`」，当时归因于 v0.7 的按需设计但缺乏对照。本章 A/B 实验证实：**同一个 Agent，触发与否由任务复杂度决定**——教程的启用建议表（单步问答关闭 / 长程多阶段启用）背后正是这个机制。规划是模型的能力选择，不是框架的强制流程。

**复盘 2：`write_todos` 是全量覆盖，不是增量更新。**
6 次调用中每次都传**完整清单**（改一条也要把所有条目重发一遍）。这由数据结构决定——`todos` 是状态通道的整体快照。理解这一点后就能解释为什么中间件要注入规划提示词：引导模型维护快照的一致性（状态、顺序、新增项都要在重发时保持正确）。实验中模型做得很好，新增项插在了正确位置。

**复盘 3：强提示词确实能稳定触发规划。**
主实验的提示词按教程明确写了「先用 write_todos 制定研究计划」，复杂任务下模型第一次调用就是 `write_todos`；而复盘实验的简单提示词在简单任务下零触发。提示词是调节「规划意愿」的直接旋钮，代价是简单任务可能产生「计划比任务还长」的浪费——这与教程建议表完全一致。

**复盘 4：产物交付要多想一步「从哪拿」。**
报告写在 `/workspace/report.md`（StateBackend），实验结束后它只存在于 Agent State——我在脚本里主动把它取出落盘为 `agent_report.md`。这延续了 Task03 的教训：**先问后端的文件在哪，再设计交付路径**。

## 四、学习心得

本章把 Task02 遗留的「模型为什么不规划」之问彻底闭环了：write_todos 是能力不是流程，触发与否由任务复杂度和提示词共同决定。最震撼的是阶段三的动态调整——Agent 搜完三个框架后自己意识到「缺一个横向对比」，往计划里插了一项新任务，这一下让「计划」从静态清单变成了 Agent 的Working Memory。引擎盖部分同样关键：看懂 Node-style 与 Wrap-style 两类 Hook、以及 create_deep_agent 的中间件三层版图之后，前几章的 SummarizationMiddleware、FilesystemMiddleware 都有了统一的解释框架——Deep Agents 的全部能力原来就是一组组织良好的中间件。

## 五、对教程的意见及建议

1. 实战示例直接给了一句「先用 write_todos 制定研究计划」的提示词，建议补一段说明：去掉这句时简单任务的触发率会明显下降（附 A/B 数据更佳），让读者理解这句提示词不是可有可无的样板话。
2. `write_todos` 全量覆盖的调用方式值得点名：模型每次重发完整清单，任务很多时这是潜在的 token 开销点，可提示配合 `ToolCallLimitMiddleware` 或上下文管理使用。
3. 建议给「任务清单的持久化」补一个与 checkpointer 关系的小注（延续 Task03 的坑）：State 中跨轮次可见仍依赖 checkpointer 配置。

## 六、引用资料来源

- 课程仓库：https://github.com/datawhalechina/deepagents-in-action
- 第 4 章在线阅读：https://datawhalechina.github.io/deepagents-in-action/chapters/ch04-task-planning/
- Deep Agents 官方文档：https://docs.langchain.com/oss/python/deepagents/overview
- LangChain Middleware 文档：https://docs.langchain.com/oss/python/langchain/middleware
- 智谱开放平台 OpenAI 接口文档：https://docs.bigmodel.cn/cn/guide/develop/openai/introduction
- Tavily API 文档：https://docs.tavily.com/
- 前序笔记：[Task01](./task01.md) · [Task02](./task02.md) · [Task03](./task03.md)
- 报告中三家框架的官方资料来源已由 Agent 附于 [task04/agent_report.md](./task04/agent_report.md) 文末
