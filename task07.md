# Deep Agents 实战 · Task07 打卡：长期记忆与 Human-in-the-Loop（第 8、9 章）

> 课程：[《Deep Agents 实战》](https://github.com/datawhalechina/deepagents-in-action)（Datawhale 开源课程）
> 对应章节：[第 8 章 长期记忆 — 让 Agent 拥有跨对话的记忆](https://datawhalechina.github.io/deepagents-in-action/chapters/ch08-long-term-memory/) · [第 9 章 Human-in-the-Loop — 构建安全的人机协作流程](https://datawhalechina.github.io/deepagents-in-action/chapters/ch09-human-in-the-loop/)
> 实践环境：macOS · Python 3.13（独立 venv）· deepagents 0.7.18 · 模型：智谱 GLM `glm-5.3-flash`（OpenAI 兼容接口）
> 实践日期：2026-09-24（可复现脚本见 [task07/](./task07/) 目录）

---

## 一、学习内容归纳

**第 8 章 记忆的分层**：短期记忆 = checkpointer 保存的 thread 状态（thread-scoped，换线程即失）；长期记忆 = 跨线程持久的 Store 数据。核心方案是 `CompositeBackend` 按路径路由：`/workspace/` 等临时路径走 StateBackend，`/memories/` 走 StoreBackend。**namespace 决定记忆的作用域**：`(assistant_id, …)` 是 Agent 级（所有用户共享），`(user_id, …)` 是用户级（按人隔离）。`memory=["/memories/…"]` 参数让已有记忆在每次启动时自动注入。本地环境 `rt.server_info` 为空，namespace 函数必须写兜底分支。

**第 9 章 HITL**：`interrupt_on` 配置哪些工具需要人工审批（`True` / `False` / `{"allowed_decisions": [...]}` 三种值；approve / edit / reject / respond 四种决策）。运行时三要素：**必须配 checkpointer、必须用同一 thread_id 恢复、必须 `version="v2"`**。决策要点：不同意执行用 `reject` 并写清反馈；改参数用 `edit`；`respond` 只用于"工具本来就是问人"的场景。非工具边界的暂停点可在自定义 Middleware 的 Node-style Hook 中直接调 `interrupt()`。

## 二、实验记录

### 实验 1（第 8 章）：用户级记忆——跨会话持久化 + 用户隔离双验证（`memory_agent.py`）

一个 Agent，三个会话，`/memories/` 路由到用户级 namespace 的 StoreBackend：

| 会话 | 用户 / 线程 | 提问 | 结果 |
|---|---|---|---|
| 1 | user-123 / thread-A | 请记住我的偏好（简洁风格、Python 生态、表格汇报） | 写入 `/memories/preferences.md`，并回显确认 |
| 2 | user-123 / **thread-B（全新线程）** | 我的偏好是什么？ | **完整复述三条偏好** —— 跨会话持久化 ✅ |
| 3 | **user-456** / thread-C | 我的偏好是什么？ | 「记忆目录是空的……我还不知道你的偏好」 —— **namespace 隔离 ✅** |

比教程示例多验证的一维是会话 3：**持久化与隔离是同一套 namespace 机制的两面**——`user-123` 的记忆写在 `("user-123", "memories")` 下，user-456 的读取天然落在自己的空 namespace 里，Agent 如实回答"不知道"而不是幻觉编造。

### 实验 2（第 9 章）：edit 与 reject 两种决策的完整闭环（`hitl_agent.py`）

工具集：`send_email`（需审批）、`archive_file`（免审批）、内置文件系统 `delete`（需审批）。

**场景 A：edit——批准但修改参数**

```text
[中断] 工具: send_email | 参数: {to: 'boss@example.com', subject: '周报', …}
       可选决策: ['approve', 'edit', 'reject']
[人工决策] edit：收件人 boss@example.com → team@example.com
[最终回复] 审批环节调整了收件人…实际发送结果：收件人 team@example.com ✅
实际发送记录: [('team@example.com', '周报')]   ← 只发了一封，发给了编辑后的地址
```

**场景 B：reject——拒绝并给出反馈**

```text
[中断] 工具: delete | 参数: {file_path: '/workspace/draft_old.txt'}
[人工决策] reject："用户拒绝删除该文件。不要再次尝试删除，请改用 archive_file 归档它。"
[最终回复] ❌ 删除操作：审批被拒绝 ✅ 归档操作：已成功归档
（delete 未执行，Agent 按反馈自动改走免审批的 archive_file）
```

两次中断-恢复均严格遵循三要素（同 thread_id、v2、决策与 action_requests 一一对应），Agent 对 edit 的转述准确（"审批环节由人工审核调整"），对 reject 的行为改变真实发生。

## 三、踩坑与问题复盘

**坑 1：`memory=` 自动加载记忆时必须显式传 `store`。**
教程示例只写了 `backend=CompositeBackend(routes={"/memories/": StoreBackend(...)})` 就配 `memory=[...]`，实测在本地 `invoke()` 下 `MemoryMiddleware.before_agent` 直接 `AttributeError: 'NoneType' object has no attribute 'get'`——StoreBackend 底层的 `store` 是 None。补上 `store=InMemoryStore()` 后一次跑通。教程的 namespace 兜底写了，store 的兜底却漏了，属于同一类"本地环境与部署环境差异"。

**坑 2：`interrupt_on` 的键必须匹配模型实际会调用的工具名——内置工具会抢在自定义工具前面。**
场景 B 第一版自定义了 `delete_file` 工具并配置审批，实测**模型选择的是 FilesystemMiddleware 内置的 `delete` 工具**，`delete_file` 的审批配置完全没命中，删除静默执行（所幸目标是空文件）。把键改为 `"delete"` 后中断正常触发。这是本章文档没有覆盖的盲区：**审批配置要对准"模型的实际选择"，而不是"你定义了什么"**。

**坑 3：edit 决策的参数回填有两套字段名。**
中断信息里参数在 `arguments`（教程提醒兼容回退到 `args`），而 edit 恢复时 `edited_action` 用 `args`——同一轮交互里字段名不对称，写审批界面时极易拼错。实测按教程的"读 arguments、回填 args"组合可以一次通过。

**复盘 4：隔离的 Agent 表现出了正确的"无知"。**
会话 3 的 user-456 没有读到任何越权数据，也没有幻觉补全——它检查了记忆目录为空并如实说不知道。长期记忆的正确性不仅取决于写入，也取决于 namespace 隔离是否让"读不到"成为默认状态。

## 四、学习心得

这两章补上了 Deep Agents 作为"可交付系统"的最后两块拼图：记忆让它跨会话越来越懂你，HITL 让危险动作永远有一道人的闸门。实验 1 里最触动我的是会话 3——隔离机制让"读不到"成为默认，Agent 诚实的"我不知道"比任何正确回答都更能说明 namespace 设计对了。实验 2 的坑 2 则是很好的工程警示：审批系统如果对不准模型真实的工具选择，安全配置就只是纸面合规——**安全边界必须用运行时观察来验证，不能只看配置写了什么**。edit 决策的体验也让我看到了人机协作的产品形态：人不需要二选一的同意/拒绝，而是可以精准地改一个参数放行。

## 五、对教程的意见及建议

1. 第 8 章示例请补上 `store=InMemoryStore()`（或注明"部署环境可省略"）：本地跟跑的读者会直接撞上 NoneType 报错，且报错点在框架深处不易定位。
2. 第 9 章建议新增一节"审批键与内置工具同名/竞争"的说明：自定义 `delete_file` 会被内置 `delete` 抢调用，导致审批配置落空——这是安全相关功能，值得明确警示并给出"用运行日志验证中断确实触发"的检查清单。
3. 两章都建议给"本地 InMemory vs 持久部署"的对照表：InMemoryStore / MemorySaver 关进程即失，生产要换持久化实现——初学者很容易把实验代码直接带上线。

## 六、引用资料来源

- 课程仓库：https://github.com/datawhalechina/deepagents-in-action
- 第 8 章在线阅读：https://datawhalechina.github.io/deepagents-in-action/chapters/ch08-long-term-memory/
- 第 9 章在线阅读：https://datawhalechina.github.io/deepagents-in-action/chapters/ch09-human-in-the-loop/
- Deep Agents 官方文档（Memory / HITL）：https://docs.langchain.com/oss/python/deepagents/overview
- LangGraph Store / Interrupt 文档：https://docs.langchain.com/oss/python/langgraph/overview
- 智谱开放平台 OpenAI 接口文档：https://docs.bigmodel.cn/cn/guide/develop/openai/introduction
- 前序笔记：[Task01](./task01.md) · [Task02](./task02.md) · [Task03](./task03.md) · [Task04](./task04.md) · [Task05](./task05.md) · [Task06](./task06.md)
