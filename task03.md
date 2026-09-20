# Deep Agents 实战 · Task03 打卡：虚拟文件系统与存储后端（第 3 章）

> 课程：[《Deep Agents 实战》](https://github.com/datawhalechina/deepagents-in-action)（Datawhale 开源课程）
> 对应章节：[第 3 章 虚拟文件系统 — Deep Agents 的 Context Engineering 核心](https://datawhalechina.github.io/deepagents-in-action/chapters/ch03-virtual-filesystem/)
> 实践环境：macOS · Python 3.13（独立 venv）· deepagents 0.7.15 · langchain 1.4.1 · 模型：智谱 GLM `glm-5.3-flash`（OpenAI 兼容接口）
> 实践日期：2026-09-18（可复现脚本见本仓库 [task03/](./task03/) 目录）

---

## 一、学习内容归纳

**核心命题**：传统 Agent 把文件内容、搜索结果、中间计算全部塞进 prompt，对话历史不断膨胀；Deep Agents 的解法是**给 Agent 一个文件系统**——像人一样分门别类存放、按需取用、搜索定位。

**7 个内置文件工具**（v0.7 新增 `delete`，共七件套）：

| 工具 | 用途 | 关键特性 |
|------|------|----------|
| `ls` | 列目录（含大小、修改时间） | 空目录返回 `No files found` |
| `read_file` | 读文件 | 分片读取（offset/limit，默认前 100 行）；原生多模态（图片/音视频/PDF） |
| `write_file` | 创建或**完整覆盖** | 只改局部应该用 `edit_file` |
| `edit_file` | 精确字符串替换 | 红笔改稿 |
| `delete` | 删除文件/目录 | v0.7 新增 |
| `glob` | 按模式找文件（`**/*.py`） | 可能截断，以 `truncated=True` 明示 |
| `grep` | 内容搜索 | 三种输出模式：files_with_matches / content / count |

**上下文自动管理两道防线**（文件系统的真正价值）：
1. **大结果自动卸载**：工具输出超 20K tokens → 完整内容写入虚拟文件系统，对话里只留路径引用 + 前 10 行预览，需要时按需读回；
2. **对话历史自动总结**：上下文达窗口 85% 且无可卸载内容 → LLM 生成结构化摘要替换旧消息，完整原始对话存入文件系统可回溯。

**可插拔存储后端**（本章实验重点）：

| 后端 | 落点 | 持久性 | 适用 |
|------|------|--------|------|
| `StateBackend`（默认） | LangGraph Agent State | 线程内持久（需 checkpointer）、跨线程丢失 | 草稿纸、单会话 |
| `FilesystemBackend` | 本地磁盘 | 永久、不可逆 | 编程助手、CI/CD |
| `LocalShellBackend` | 磁盘 + Shell 执行 | 同上，另有 `execute` 工具 | 个人开发机（高风险） |
| `StoreBackend` | LangGraph Store | **跨线程**持久，按 namespace 隔离 | 长期记忆 |
| `CompositeBackend` | 按路径前缀路由 | 混合 | 临时草稿 + 持久记忆并存 |
| 沙箱后端 | 远程隔离环境 | 安全执行 | 生产/多用户 |

## 二、实验记录

### 实验 1：让 Agent 亲手使用文件工具（`fs_tools_demo.py`）

一个提示词驱动 Agent 依次使用 write → ls → read → edit → grep 五个工具，全程一次 `invoke()`：

```text
=== 工具调用时序 ===
 -> write_file | /workspace/meetup.md（三行会议纪要）
 -> ls         | /workspace
 -> read_file  | /workspace/meetup.md
 -> edit_file  | 把「结论」行改为「结论：每周四同步，负责人待定」
 -> grep       | pattern=周四, path=/workspace, output_mode=content

=== 最终回答（节选）===
5 步文件工具操作均成功执行：写入、列目录、读回、修改、搜索各 1 次，
grep 在 /workspace 命中 1 处「周四」，正是修改后的第 3 行。

=== StateBackend 落点验证 ===
  /workspace/meetup.md (191 chars)   ← 文件确实存进了 Agent State
```

观察：`edit_file` 的精确替换依赖写入时的原文（`old_string` 必须逐字匹配），模型自己维护了这条一致性；grep 搜到的正是 edit 之后的最新内容，说明工具链共享同一份文件状态。

### 实验 2：StateBackend vs FilesystemBackend 对比（评审核心，`backend_compare.py`）

同样的写文件任务（创建 `/workspace/persist_test.txt`），两个后端各跑一遍，每个后端验证三问：**写到了哪 / 同线程还在吗 / 换新线程还在吗**。StateBackend 侧显式挂了 `MemorySaver` checkpointer 以兑现「线程内持久化」。

```text
A. StateBackend（默认，挂 MemorySaver checkpointer）
写入后  | thread-1 State files: ['/workspace/persist_test.txt'] | 磁盘文件存在: False
同线程  | thread-1 再 ls  : 共 1 个文件 /workspace/persist_test.txt
换线程  | thread-2 再 ls  : 该目录为空，没有任何文件   ← 文件随 State 丢失

B. FilesystemBackend(root_dir=".", virtual_mode=True)
写入后  | thread-1 State files: [] | 磁盘文件存在: True
        | 磁盘内容: 'hello backend\n'                    ← 真实落在磁盘
同线程  | thread-1 再 ls  : 共 1 个文件
换线程  | thread-2 再 ls  : 仍列出 /workspace/persist_test.txt ← 跨线程可见
```

**对比结论**：

| 维度 | StateBackend | FilesystemBackend |
|------|--------------|-------------------|
| 文件真实落点 | Agent State（内存） | 本地磁盘 `workspace/` |
| `result["files"]` 里能查到吗 | 能 | **不能**（检查落点要看磁盘） |
| 同线程再启动 | 可见（依赖 checkpointer） | 可见（读磁盘，天然持久） |
| 换全新线程 | 不可见，文件随 State 丢失 | 仍可见 |
| 适用场景 | 草稿纸 / 单会话任务 | 编程助手 / 需要落盘的产物 |

### 实验 3（评优加分）：CompositeBackend 混合路由（`composite_demo.py`）

`/memories/` 前缀路由到 `StoreBackend`（InMemoryStore + namespace 按用户隔离），其余路径走默认 `StateBackend`。一次 invoke 让 Agent 同时写两类文件，换全新线程再 `ls`：

```text
=== thread-1 写入 ===
 -> write_file | /memories/user_pref.txt（用户偏好：简洁风格）
 -> write_file | /drafts/idea.txt（一个临时的想法）

=== thread-2（全新线程）ls 结果 ===
- /memories/：还有 1 个文件 user_pref.txt        ← Store 持久生效
- /drafts/：目录为空，没有任何文件               ← State 临时生效
```

**同一个 Agent、同一次对话**写出的两个文件，因为路径前缀不同而命运不同——「临时草稿 + 持久记忆」的混合架构一次跑通，这就是 CompositeBackend 的价值。

## 三、踩坑与观察记录

**坑 1：`root_dir` 是 VFS 根的映射点，路径会「拼一层」。**
第一版脚本把 `root_dir` 设为 `"workspace"`，写入后检查磁盘 `workspace/persist_test.txt` 却是 False——排查后发现 Agent 的 `/workspace/persist_test.txt` 实际落在了 `workspace/workspace/persist_test.txt`。**后端把 Agent 的 `/` 映射到 `root_dir`**，Agent 路径会原样拼接在 root_dir 之后。后来改用 `root_dir="."`，Agent 路径与磁盘路径直观对应。Agent 侧的 `ls` 一直正常（它走后端抽象），**只有应用层的磁盘检查会暴露映射误解**。

**坑 2：「线程内持久化」不是免费的，依赖 checkpointer。**
教程一句「同一个对话线程内持久化」很容易让人以为开箱即得——实测 `StateBackend` 不挂 `MemorySaver`（或其他 checkpointer）时，连同线程的第二次 `invoke()` 都是全新 State，上次写的文件直接消失。**持久化 = 后端能力 + checkpointer 两者合作**。

**坑 3：不同后端下 `result["files"]` 语义不同。**
`FilesystemBackend` 写文件后 `result["files"]` 恒为空列表（文件根本不在 State 里），校验落点必须直接查磁盘。消费运行结果时要先问「这个后端的文件在哪」，不能假设统一的返回结构。

**坑 4（教程已预警，实测验证）：`StoreBackend.namespace` 本地必须兜底。**
本地 `invoke()` 时 `rt.server_info` 是 `None`，按教程加 `if rt.server_info else ("local-user",)` 兜底后一次跑通，没踩坑——但若照抄 LangSmith 部署版写法就会当场报错。

## 四、学习心得

这一章让我真正理解了「文件系统是 Context Engineering 的核心」这句标题：文件工具的价值不在存储本身，而在它和自动卸载、历史总结组成的**上下文分层机制**——热数据在对话里，温数据在文件里，冷数据在摘要里。三个实验做下来，最扎实的收获是把「持久性」从一句文档描述变成了可验证的三问：写到哪、同线程在不在、换线程在不在。State 与磁盘的对比、CompositeBackend 的路径路由，本质上都是在回答「什么数据值得活多久」——这也是我以后为自己的 Agent 选后端时会给出的判断框架。

## 五、对教程的意见及建议

1. 建议 3.2 节「线程内持久化」处明确补一句：需配合 checkpointer（如 `MemorySaver`）方能兑现，并给出两行示例——这是我本次最大的理解偏差点。
2. `FilesystemBackend` 的 `root_dir` 映射关系（Agent `/` → `root_dir`，Agent 路径逐层拼接）值得单独用一张路径对照表说明，「double workspace」这类映射误解非常容易发生。
3. 后端选择指南表格很好，建议再加一列「`result["files"]` 是否有内容」，提醒应用层消费运行结果时区分后端语义。

## 六、引用资料来源

- 课程仓库：https://github.com/datawhalechina/deepagents-in-action
- 第 3 章在线阅读：https://datawhalechina.github.io/deepagents-in-action/chapters/ch03-virtual-filesystem/
- Deep Agents 官方文档（backends）：https://docs.langchain.com/oss/python/deepagents/overview
- LangGraph Store / Checkpointer 文档：https://docs.langchain.com/oss/python/langgraph/overview
- 智谱开放平台 OpenAI 接口文档：https://docs.bigmodel.cn/cn/guide/develop/openai/introduction
- 前序笔记：[Task01](./task01.md) · [Task02](./task02.md)
