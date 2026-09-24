# Deep Agents 实战 · Task06 打卡：异步子 Agent 与 Skills（第 6、7 章）

> 课程：[《Deep Agents 实战》](https://github.com/datawhalechina/deepagents-in-action)（Datawhale 开源课程）
> 对应章节：[第 6 章 异步子 Agent](https://datawhalechina.github.io/deepagents-in-action/chapters/ch06-async-subagents/) · [第 7 章 Skills — 可复用的 Agent 能力包](https://datawhalechina.github.io/deepagents-in-action/chapters/ch07-skills/)
> 实践环境：macOS · Python 3.13（独立 venv）· deepagents 0.7.16 · langgraph-cli 0.4.31 · 模型：智谱 GLM `glm-5.3-flash`（OpenAI 兼容接口）
> 实践日期：2026-09-23（可复现文件见 [task06/](./task06/) 目录：`async_demo/` 按教程 7 步搭建，`skills_demo/` 自建技能包）

---

## 一、学习内容归纳

### 第 6 章：异步子 Agent

同步子 Agent（`task` 工具）是阻塞的：主 Agent 要等子任务跑完才能继续。`AsyncSubAgent` 把子任务变成**后台进程**：主 Agent 拿到 5 把"遥控器"——`start_async_task`（立即返回 task_id）/ `check_async_task`（查状态与结果）/ `update_async_task`（向运行中任务注入新指令，同 thread 中断重跑）/ `cancel_async_task`（取消）/ `list_async_tasks`（任务总览）。判定法则：**5 秒内能完成的用同步；数分钟以上且过程需可交互的用异步**。

两个设计点值得划线：
- `AsyncSubAgent` 不传 `url` 走 **ASGI 进程内传输**（零网络开销，子 Agent 仍跑在独立 thread 上）；传 `url` 则切 HTTP 远程传输；
- 任务元数据存在独立的 `async_tasks` state channel 而非消息历史——否则对话被自动压缩后主 Agent 会"忘掉"自己派过的任务。这是 Deep Agents 的一致哲学：**会被截断的放消息历史，必须长存的进 state channel**。

### 第 7 章：Skills

Skill = 一个含 `SKILL.md`（YAML frontmatter + Markdown 剧本）的目录，可选 `scripts/ references/ assets/`。核心机制 **Progressive Disclosure（渐进式披露）** 三级加载：

| 层级 | 加载内容 | 时机 |
|---|---|---|
| L1 元数据 | name + description + 路径 | 启动时进系统提示词 |
| L2 正文 | SKILL.md body | Agent 判断相关后 `read_file` |
| L3 资源 | references/ assets/ 等 | 指令引用到时 LLM 自行读取 |

**description 是唯一路由依据**：写得太模糊会漏召回/误召回。20 个 Skills 的启动成本只是 20 条 description，扩展性由此而来。

## 二、实验记录

### 实验 1（第 6 章）：本地最小异步子 Agent 全生命周期（`task06/async_demo/`）

按教程 7 步搭建单部署 + ASGI：`langgraph.json` 注册 `supervisor`（create_deep_agent + AsyncSubAgent，GLM）与 `researcher`（固定 sleep 30s 的 LangGraph 图，**故意放慢**让异步效果稳定可见），`langgraph dev --n-jobs-per-worker 4` 启动后用 SDK 在同一 thread 上连续对话四轮：

| 轮次 | 用户动作 | Supervisor 行为 | 观察到的证据 |
|---|---|---|---|
| 1 | 请求后台调研 | `start_async_task` → 立即返回 task_id | 本轮 17.8s 结束时 researcher 的 30s 任务**尚未完成**，主对话未被拖住 |
| 2 | 问进度 | `check_async_task` | 状态 **running**：「后台研究员还在处理，尚未返回结果」 |
| 3 | 补充约束 | `update_async_task` | 「3 条 bullet」新指令注入，同一 thread、任务 ID 不变 |
| 4 | 再查 | `check_async_task` | **success**，最终答案已按追加约束重排为 3 条 bullet |

第 2 轮是最硬的非阻塞证据：主对话在第 1 轮结束后立刻继续，此刻后台任务仍在 sleep——同步模式下主 Agent 此刻必然还卡在 `task` 调用里。

### 实验 2（第 7 章）：Skills 渐进式加载与匹配排他性（`task06/skills_demo/`）

自建两个技能做对照：`notes-style`（打卡笔记六段式规范，含 `references/structure.md`）与 `red-team`（无关领域干扰项），FilesystemBackend + `skills=["/skills/"]` 接入：

**场景 A：笔记类请求 → 命中 notes-style**

```text
问题: 请按团队的笔记规范，帮我写一段 Task06 的学习心得
 -> read_file | /skills/notes-style/SKILL.md            ← L2 正文按需加载
 -> read_file | /skills/notes-style/references/structure.md ← L3 资源按需加载
 -> ls / glob / read_file（Agent 主动找真实实验材料佐证）
回复: 已按 notes-style 技能流程完成：先读取 SKILL.md，再读取 structure.md…
     （且 Agent 拒绝编造「实验记录」，如实说明该段需填入真实输出）
```

**场景 B：无关请求 → 零技能加载**

```text
问题: 1+1 等于几？
（无任何工具调用）回复: 1+1 = 2
```

三级加载（L1 元数据启动注入 → L2 正文 → L3 资源）与 description 路由的排他性全部得到验证。

### 补充实验（第 6 章）：并行启动与取消恢复（`async_demo/cancel_parallel_demo.py`）

对照评审要求补做的两个场景，SDK 驱动同一 thread 三轮对话：

**并行启动**：一条用户消息要求同时调研两个主题，Supervisor 在**同一轮内连续调用两次 `start_async_task`**，返回两个独立 task_id，两任务后台并行：

```text
[工具] start_async_task -> 任务A：Context Engineering 关键手法  → id …25f2
[工具] start_async_task -> 任务B：Multi-Agent 编排模式          → id …0fd
[回复] 两个后台调研任务已成功启动 … 两个任务正在后台并行运行
```

**取消恢复**：要求取消 B 并列出全部任务，`cancel_async_task` + `list_async_tasks` 返回表格化总览；随后确认 A 不受影响：

```text
[工具] cancel_async_task -> {task_id: …0fd（B）}
[工具] list_async_tasks
[回复] 任务A 🟢 running（仍在运行中） | 任务B ⚪ cancelled
（等待 32s 后第 3 轮）[工具] check_async_task -> 任务A ✅ success
```

至此评审要求的关键词全部有真实运行记录覆盖：**并行任务、追加指令（update）、取消恢复（cancel + list）、自定义 SKILL.md**。

> 复盘：`list_async_tasks` 的价值在并 plurality 场景才真正显现——单任务时 check 就够，两个以上任务时它是唯一的全局视图，且已结束任务从缓存返回、未结束的并发拉取实时状态，正好对上教程"任务元数据独立 channel"的设计。

## 三、踩坑与问题复盘

**坑 1：GLM flash 的推理延迟会「吃掉」短 sleep 的异步证据。**
第一版 researcher 只 sleep 8s（教程原值），第 1 轮耗时 19.7s——GLM 的多步推理比 8s 还长，等主 Agent 回复完任务已经 done 了，"非阻塞"证据被时间线掩盖。把 sleep 提到 30s 后，第 2 轮干净落在 running。**验证异步机制时，后台任务的时长必须显著大于模型推理延迟**，否则现象不可分辨。

**坑 2：SDK 拿回的是全量消息历史，统计工具调用要去重。**
`client.runs.wait` 返回的 state 包含整个 thread 的累积消息，直接遍历会把前几轮的 `start_async_task` 也打出来，造成"模型每轮都在重复派任务"的假象。按轮次做增量（或按 message id 去重）才能看到真实行为：模型实际只在第 1 轮 start，后续全部是 check/update。

**坑 3：`langgraph dev` 下不能传 `checkpointer`。**
教程在第 5 步明确预警：平台已内置持久化，`create_deep_agent(checkpointer=InMemorySaver())` 会直接 `ValueError`。本地 `python supervisor.py` 快速调试时才需要手动挂——同一个参数在两种运行方式下语义相反，容易被上一章的肌肉记忆坑到。

**坑 4（补充实验）：macOS 系统代理会被 Python 静默继承。**
补充实验中途 GLM 突发 OpenAIConnectionError，shell `env` 里却没有任何 proxy 变量——是**系统级代理**被 requests/urllib 自动读取，而代理本身处于半可用状态（curl 直连一切正常）。`export no_proxy='*' NO_PROXY='*'` 重启 server 与客户端后恢复。教训：直连可用时，Python 进程要显式 `no_proxy='*'` 才能不被系统代理劫持。

**坑 5：Skills 的 `skills=` 路径是"父目录"而不是 SKILL.md 文件。**
`skills=["/skills/"]` 对应 `/skills/notes-style/SKILL.md`；传成 `skills=["/skills/notes-style/SKILL.md"]` 不会报错但扫描不到任何技能（目录约定是静默匹配）。排障时先确认路径层级，再怀疑 frontmatter。

## 四、学习心得

这两章合起来看特别有味道：第 6 章解决"长任务把对话焊死"的问题，第 7 章解决"能力多了把提示词撑爆"的问题，而它们的答案是同构的——**把不急着用的东西挪出当前上下文**。异步子 Agent 把等待中的子任务挪到后台、只留一个 task_id；Skills 把沉睡的领域知识挪到磁盘、只留一行 description。配合第 3 章的文件卸载和第 4 章的任务清单外置，Deep Agents 的上下文工程图谱完整了：热上下文只留"现在需要的东西"。亲手跑 update_async_task 那一下印象最深——对着一个 running 状态的后台任务追加约束，几分钟后它带着完整历史按新要求重跑完成，这才理解为什么教程说异步子 Agent"拥有自己的线程、会话持续累积"。

## 五、对教程的意见及建议

1. 第 6 章 `sleep 8s` 的示例值在强推理模型（GLM/o 系列）下会掩盖非阻塞证据，建议正文加一句：**sleep 时长应大于所用模型的单轮推理延迟**，并给出本轮 8s→30s 的实测对照。
2. 第 7 章「description 是最重要的字段」一节很好，建议补一个可操作的负面清单（如"避免『处理各种任务』『A helpful skill』这类无触发信号的写法"集中呈现），方便读者自查存量 Skill。
3. 两章都涉及部署形态（ASGI/HTTP、三种拓扑），建议给一张"本地开发 → 自托管 → LangSmith 部署"的迁移路径图，标注每一步要改的配置点（url、headers、鉴权），降低进阶门槛。

## 六、引用资料来源

- 课程仓库：https://github.com/datawhalechina/deepagents-in-action
- 第 6 章在线阅读：https://datawhalechina.github.io/deepagents-in-action/chapters/ch06-async-subagents/
- 第 7 章在线阅读：https://datawhalechina.github.io/deepagents-in-action/chapters/ch07-skills/
- Deep Agents 官方文档：https://docs.langchain.com/oss/python/deepagents/overview
- LangGraph Platform / Server 文档：https://docs.langchain.com/oss/python/langgraph/platform
- Agent Protocol：https://github.com/langchain-ai/agent-protocol
- 智谱开放平台 OpenAI 接口文档：https://docs.bigmodel.cn/cn/guide/develop/openai/introduction
- 前序笔记：[Task01](./task01.md) · [Task02](./task02.md) · [Task03](./task03.md) · [Task04](./task04.md) · [Task05](./task05.md)
