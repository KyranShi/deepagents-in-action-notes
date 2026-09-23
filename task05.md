# Deep Agents 实战 · Task05 打卡：子 Agent 与上下文隔离（第 5 章）

> 课程：[《Deep Agents 实战》](https://github.com/datawhalechina/deepagents-in-action)（Datawhale 开源课程）
> 对应章节：[第 5 章 子 Agent 与上下文隔离 — 让 Agent 学会"委派"](https://datawhalechina.github.io/deepagents-in-action/chapters/ch05-subagents/)
> 实践环境：macOS · Python 3.13（独立 venv）· deepagents 0.7.16 · 模型：智谱 GLM `glm-5.3-flash`（OpenAI 兼容接口）· 搜索：Tavily
> 实践日期：2026-09-22（可复现脚本与多 Agent 协作产出的报告见 [task05/](./task05/) 目录）

---

## 一、学习内容归纳

**核心动机 Context Quarantine（上下文隔离）**：研究类子任务会产生大量中间过程（多轮搜索、写文件、回顾整理），这些细节堆进主 Agent 上下文只会造成膨胀。子 Agent 的解法：主 Agent 通过 `task` 工具委派 → 子 Agent 在**独立上下文**中执行 → 只把**最终结果**回传。项目经理不需要参加每一场技术讨论会。

**两种定义方式**：字典方式（最常用，`name/description/system_prompt/tools/model/middleware/skills/response_format/permissions` 九个字段）与 `CompiledSubAgent`（把预构建的 LangGraph 图包装成子 Agent，适合多步骤分支工作流）。

**继承规则是本章最易混淆处**（实验前专门梳理）：

| 字段 | 继承主 Agent？ | 说明 |
|---|---|---|
| `system_prompt` | ❌ 不继承 | 每个子 Agent 必须有专属指令 |
| `tools` | ✅ 默认继承；**指定后完全替换（不合并）** | 置空 `[]` 即"无自定义工具" |
| `model` | ✅ 默认继承 | 可为子 Agent 指定不同模型 |
| `middleware` | ❌ 不继承 | 子 Agent 要用 Todo 需自己启用 |
| `skills` | ❌ 不继承 | 主 Agent 的 skills 只传给 general-purpose |
| `response_format` | ❌ 不继承 | 设置后主 Agent 收到符合 Pydantic schema 的 JSON |

**general-purpose 子 Agent**：唯一例外，继承主 Agent 的 system_prompt/tools/model/skills，作用是"纯粹的上下文隔离"。禁用它不能靠 `excluded_middleware`（会抛 `ValueError`），要用 `GeneralPurposeSubagentProfile(enabled=False)`。

## 二、实验记录

### 实验 1（主实验）：两个职责不同的子 Agent 协作（`multi_subagent.py`）

**角色设计**：

| 角色 | 职责 | 工具集 | 隔离设计意图 |
|---|---|---|---|
| `researcher` | 联网调研，多轮搜索后返回 ≤600 字纪要 | `tools=[internet_search]`（显式指定，只有搜索工具） | 搜索的中间结果（数万字符）全部困在它的上下文里 |
| `analyst` | 基于调研材料撰写对比报告并 `write_file` 落盘 | `tools=[]`（显式置空，无搜索工具） | 结构上杜绝它联网——只能基于材料工作 |
| 主 Agent | 协调者：委派调研 → 转交材料 → 汇总确认 | — | 提示词明示"自己不要联网搜索、不亲自写长报告" |

**实际协作时序**（任务：调研 LangGraph 与 CrewAI 差异并产出对比报告）：

```text
 -> task | subagent_type='researcher'
     委派简报 2,059 字符（主 Agent 自行拟定的详细调研大纲）
 -> task | subagent_type='analyst'
     转交材料：把 researcher 的调研纪要全文嵌入 description
 -> read_file | /workspace/report.md（主 Agent 验收成果）
```

**子 Agent 回传给主 Agent 的唯一内容**（ToolMessage 全记录）：

```text
[researcher 回传 2,059 字符] # LangGraph vs CrewAI 调研纪要 —— 定位哲学/核心能力/差异对比/结论
[analyst 回传   181 字符] "报告已写入 /workspace/report.md。全文约 3200 字，含执行摘要、
                          14 维度对比表、选型决策指引…核心结论：LangGraph 强于控制/状态/HITL…"
```

主 Agent 消息流中 `internet_search` 出现 **0 次**；多次搜索全部发生在 researcher 的隔离上下文里。报告已取出落盘：[task05/multi_agent_report.md](./task05/multi_agent_report.md)（7,577 字符，含执行摘要与逐维度对比表）。

### 实验 2（取证实验）：委派 vs 亲自做的量化对比（`isolation_evidence.py`）

同一个研究子任务，两种执行方式，只统计**主 Agent 消息流**里的指标：

| 指标（主 Agent 上下文内） | A. 亲自做 | B. 委派 researcher | 变化 |
|---|---|---|---|
| `internet_search` 出现次数 | 10 | **0** | 全部隔离 |
| 收到的工具结果总字符量 | 109,511 | **16,158**（含文件工具结果） | **↓ 约 85%** |
| 消息总数 | 17 | 5 | ↓ 71% |

**结论**：隔离的意义不是少干活（子 Agent 里 10 轮搜索照常发生），而是搜索的中间结果不再堆进主 Agent 上下文——主 Agent 只收一份精炼摘要，省下的上下文预算可以服务更长的任务主线。

## 三、上下文隔离方式说明（评审要点）

本次实验中「隔离」体现在三个层面，且边界清晰：

1. **消息上下文硬隔离**：子 Agent 的全部工具调用与中间结果不进入主 Agent 消息流；两个上下文之间**唯一的通道是 `task` 的 description（下行）和 ToolMessage（上行）**。证据：researcher 返回 2,059 字符纪要后，主 Agent 上下文里看不到任何一条原始搜索结果（实验 2 中 A 场景的 109,511 字符在 B 场景缩到 16,158）。
2. **能力集隔离**：`tools` 指定后完全替换——researcher 只有搜索工具、analyst 工具集显式置空，职责边界由工具集物理保证，而非仅靠提示词约束。
3. **文件系统的边界（重要细节）**：默认 StateBackend 下，**主 Agent 与子 Agent 共享文件状态**（所以主 Agent 能直接 `read_file` 验收 analyst 写的 `/workspace/report.md`）——共享的是文件，隔离的是对话上下文。这与第 3 章「StateBackend 的文件在同一线程内主/子共享」完全对应。

## 四、踩坑与问题复盘

**坑 1：`task` 工具的参数键是 `subagent_type`，不是字段表里的 `name`。**
教程字段表写的是「`name`：主 Agent 通过它指定委派给谁」，但 0.7.16 实际工具调用参数为 `{'description': ..., 'subagent_type': 'researcher'}`。做观测脚本时按 `name` 取值拿到 None。语义相同、键名不同，解析 `task` 调用记录时要注意版本差异。

**坑 2：隔离的代价——材料传递只有一个单行通道。**
主 Agent 转交 analyst 时，把调研纪要**全文**塞进了 `task` 的 `description`（2,059 字符）。因为消息上下文不共享，这是唯一选择。好消息是文件系统共享，实践中更好的做法是让 researcher 把纪要 `write_file` 落盘、主 Agent 只传文件路径——既绕开 description 的体量限制，又利用了共享文件层。

**坑 3：当前网络下 Python TLS 连 Tavily 被干扰，工具实现层透明替换化解。**
实验时 Python `requests` 到 `api.tavily.com` 稳定 SSL EOF（curl 正常）。由于 Deep Agents 的工具就是普通 Python 函数，我把 `internet_search` 内部改为 curl 子进程调用 Tavily REST API，**Agent 侧零感知**。这反过来验证了本章的一个设计优点：工具集与 Agent 逻辑解耦，底层实现可以自由替换（也呼应第 4 章的 ToolRetryMiddleware——生产环境更优雅的做法是在中间件层做重试/降级）。

**复盘 4：委派没有发生时先查两处。**
对照教程「常见问题排查」：主 Agent 亲自干所有活，通常是 description 太模糊或提示词没有明确分工。本次两个子 Agent 的 description 都写清了「什么任务委派给它」，且主 Agent 提示词明示"自己不要联网搜索"，全程委派零失误——角色设计表在实验前写好是值得的。

## 五、学习心得

这一章最颠覆我认知的是那句"隔离的意义不是少干活"：取证实验里子 Agent 一样跑了 10 轮搜索，但 10 万字符的中间结果被拦在主 Agent 上下文之外，只剩一份两千字纪要——上下文预算从"记流水账"变成"只记结论"，这才是 Deep Agents 敢做长任务的底气。亲手设计两个角色后还体会到，子 Agent 的职责边界最好用工具集来物理保证（给 analyst 显式置空搜索工具），提示词约束只是第一道防线。而"文件共享、上下文隔离"这组不对称设计，让我把第 3、5 两章真正串了起来：文件系统是团队共享的白板，对话上下文才是各自独立的笔记本。

## 六、对教程的意见及建议

1. 建议在字段表中标注 `task` 工具运行时的实际参数名（`subagent_type`），或注明与字典 `name` 字段的对应关系——写观测/审计代码时会直接踩到。
2. 「多子 Agent 协作模式」一节可补一句材料传递的最佳实践：优先用共享文件系统传大段材料，`description` 只传路径与要点，避免单通道塞爆。
3. 「什么时候用子 Agent」的表格很好，建议补充一行「需要物理隔离职责（工具集不同）→ ✅」，这是字典方式 `tools` 替换语义最有价值的应用场景之一。

## 七、引用资料来源

- 课程仓库：https://github.com/datawhalechina/deepagents-in-action
- 第 5 章在线阅读：https://datawhalechina.github.io/deepagents-in-action/chapters/ch05-subagents/
- Deep Agents 官方文档（Subagents）：https://docs.langchain.com/oss/python/deepagents/subagents
- LangGraph 多 Agent 编排（supervisor/swarm）：https://docs.langchain.com/oss/python/langgraph/multi-agent
- 智谱开放平台 OpenAI 接口文档：https://docs.bigmodel.cn/cn/guide/develop/openai/introduction
- Tavily API 文档：https://docs.tavily.com/
- 前序笔记：[Task01](./task01.md) · [Task02](./task02.md) · [Task03](./task03.md) · [Task04](./task04.md)
