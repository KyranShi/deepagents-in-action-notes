# Deep Agents 实战 · Task02 打卡：认知篇实践笔记（第 1–2 章）

> 课程：[《Deep Agents 实战》](https://github.com/datawhalechina/deepagents-in-action)（Datawhale 开源课程）
> 对应章节：[第 1 章 从 Agent Framework 到 Agent Harness](https://datawhalechina.github.io/deepagents-in-action/chapters/ch01-agent-harness/) + [第 2 章 快速上手 — 5 分钟构建你的第一个 Deep Agent](https://datawhalechina.github.io/deepagents-in-action/chapters/ch02-quickstart/)
> 实践环境：macOS · Python 3.13（独立 venv）· deepagents 0.7.15 · langchain 1.4.1 · langchain-openai · tavily-python
> 模型接入：智谱 GLM `glm-5.3-flash`（OpenAI 兼容接口）· 搜索：Tavily
> 实践日期：2026-09-14

---

## 一、第 1 章概念归纳：Agent 开发的三个层次

第 1 章回答了一个问题：框架已经那么多，Deep Agents 为什么还要存在？答案是它站在一个不同的层次上。LangChain 技术栈把 Agent 开发分为三层：

| 层次 | 代表 | 解决的问题 | 同层其他选手 |
|------|------|-----------|--------------|
| **Runtime（运行时层）** | LangGraph | Agent 怎么**可靠地运行**：持久化执行、流式输出、人机协作、状态管理 | Temporal、Inngest |
| **Framework（框架层）** | LangChain（1.0 构建在 LangGraph 之上） | 开发体验：模型抽象、工具接口、Agent 循环、中间件 | Vercel AI SDK、CrewAI、OpenAI Agents SDK 等 |
| **Harness（工具层）** | **Deep Agents** | **开箱即用**：预置一整套经过验证的工具接口与中间件框架 | Claude Agent SDK、Manus |

教程的类比很形象：Runtime 给你工作台和电源，Framework 给你锤子锯子，**Harness 直接给你一个装好的工具间**——常用工具挂在墙上，工作流程贴在白板上。

Deep Agents 预置的四类 Harness 能力：

| 能力 | 说明 |
|------|------|
| 虚拟文件系统 | `read_file` / `write_file` / `edit_file` / `delete` / `ls` / `glob` / `grep` 七件套 |
| 任务规划 | **v0.7 起按需启用**：显式加入 `TodoListMiddleware` 才有 `write_todos` |
| 子 Agent 委派 | 内置 `task` 工具 |
| 长期记忆 | 基于 LangGraph Memory Store |

一个重要的 v0.7 设计变化：**Harness 不再替所有应用默认打开每一种策略**。短任务不必为计划工具支付固定成本，长任务主动选择这层脚手架——这个设计在本章实操里给了我一个真实的观察（见坑 2）。

## 二、第 2 章实操记录

本章不依赖第 0 章的 AgentSeek 模板，是纯 Python 最小实践。我按教程新建了独立虚拟环境：

```bash
$ uv venv --python 3.13
$ uv pip install deepagents langchain-openai tavily-python python-dotenv
$ .venv/bin/python -c "import deepagents, langchain; ..."
deepagents 0.7.15 | langchain 1.4.1
```

**模型接入（与教程的唯一差异）**：教程默认硅基流动 + Qwen2.5-7B，我改用智谱 GLM。只换了三个参数就跑通了全部示例，实测验证了本章「`base_url` 模式是接入国内平台的通用方法——换个 URL 和 Key 就能切换平台」的论点：

```python
model = ChatOpenAI(
    model=os.environ.get("MODEL_NAME", "glm-5.3-flash"),
    api_key=os.environ["GLM_API_KEY"],
    base_url="https://open.bigmodel.cn/api/paas/v4",   # 智谱开放平台 OpenAI 兼容端点
)
```

### 2.1 Hello World：第一个 Deep Agent

`create_deep_agent(model, tools, system_prompt)` + 一个假的天气工具，问「北京今天天气怎么样？」：

```text
$ .venv/bin/python hello_agent.py    # 实测 12.4s
北京今天天气晴朗☀️ 是个适合外出活动的好日子！
```

一行 invoke 的背后：模型识别出需要天气信息 → 调用 `get_weather("北京")` → 拿到工具结果再组织回答。工具调用全流程对使用者透明。

### 2.2 自定义工具的三要素

教程总结的工具定义三要素，在本章两个例子里都得到了验证：

| 要素 | 作用 | 缺失的后果 |
|------|------|-----------|
| **参数类型标注** | 告诉 Agent 每个参数该传什么类型 | 可能传入错误类型 |
| **Docstring** | 告诉 Agent 工具的用途 | Agent 不知道何时该用它 |
| **默认值** | 标记可选参数，减少必填项 | Agent 每次都要填全参数 |

`calculate` 用字符串承接整个表达式（类型标注决定输入形态）、`convert_currency` 的 `to_currency` 设默认值——这些细节直接决定了 Agent 调用是否顺畅。

### 2.3 计算器 Agent

两个自定义工具（四则运算 + 固定汇率换算），组合提问「把 100 美元换算成人民币，再乘以 1.08 的通胀系数」：

```text
$ .venv/bin/python calc_agent.py     # 实测 17.8s
计算完成！结果如下：
1. 货币换算：100 美元 = 720.00 元人民币
2. 通胀调整：720.00 × 1.08 = 777.60 元人民币
最终约为 777.6 元人民币。
```

模型正确地**串联了两个工具**：先 `convert_currency(100, "USD")` 得 720，再 `calculate("720 * 1.08")` 得 777.6，数学链路无误差。

### 2.4 实战：研究助手（Tavily 搜索）

按教程 Step 1–4 构建：`internet_search` 工具（Tavily）+ 研究员人设系统提示词 + 显式 `middleware=[TodoListMiddleware()]`，提问「什么是 LangGraph？」。

**实测运行统计**（两次运行结果一致）：

```text
=== 本次运行统计 ===
消息总数: 5
write_todos 生效: False
工具调用: internet_search | 参数: {'query': 'LangGraph 是什么 框架 介绍', 'max_results': 5}
工具调用: internet_search | 参数: {'query': 'What is LangGraph framework features agents', ...}
```

有个亮眼的细节：模型自己**用中英文各搜了一次**（先查中文介绍、再用英文查特性），然后综合两边结果写出带小结表格的完整报告——多轮搜索策略完全是模型自主决策的，我只写了一次 `invoke()`。最终报告以「LangGraph 是一个基于图结构的低层级智能体编排框架……」收尾，还给出了 LangChain vs LangGraph 的选型经验法则。

## 三、踩坑与观察记录

**坑 1：LangChain 消息是对象，不是字典。**
统计工具调用时我写了 `m["tool_calls"]`，直接 `TypeError: 'AIMessage' object is not subscriptable`。消息对象要用属性访问 `m.tool_calls`。习惯了对 JSON 化的消息结构写法就容易踩这个——**遍历 `result["messages"]` 时，容器是字典、元素是对象**，两层结构要分清。

**坑 2：`write_todos` 给了，但模型一次都没调用。**
我在运行结果里检查 `todos` 状态，发现即使是教程原样启用了 `TodoListMiddleware`，模型面对「什么是 LangGraph？」这种单一问题也**选择不规划、直接干**。这恰好印证了本章 v0.7 提醒：「即使已经启用，模型也会根据任务决定是否实际调用工具，不能把图中的每一步当成固定执行协议」。换一个真正复杂的研究问题，规划工具才会被用起来——工具是能力，不是流程。

**坑 3：推理模型接入工具链的两个体感。**
一是 `glm-5.3-flash` 属于推理模型，响应里带 `reasoning_content`，多步工具链的耗时会比非推理小模型长一些（前两个脚本实测 12.4s / 17.8s，研究任务含 2 次真实搜索为分钟级）；二是做连通性测试时 `max_tokens` 给太小会「只见思考不见回答」，不是故障。

## 四、学习心得

Task02 用三个由小到大的例子把「Harness」这个抽象概念落了地：最惊讶的体验是 Hello World 那一行 `invoke()`——我没有写任何循环、重试、消息拼接逻辑，工具调用就自然发生了，这正是第 1 章说的「框架层和运行时替你处理了执行细节」；而计算器例子让我体会到工具定义三要素（类型标注、docstring、默认值）本质上是在**为模型写接口文档**，写得越清楚 Agent 用得越准。最有价值的是坑 2 的观察：启用的规划工具模型可以不用——这让我理解了 v0.7「按需启用」设计的意图，也纠正了我把 Agent 执行流程当固定管线的心态。

## 五、对教程的意见及建议

1. 第 2 章示例完整可复现，`create_deep_agent()` 参数表和 v0.7 提醒写得很到位。建议在「Agent 在背后做了什么」一节加一个**打印本次运行工具调用清单的调试片段**（如遍历 `messages` 输出 `tool_calls`），学员能直观看到「10+ 次工具调用」到底发生了什么。
2. 模型选择表很实用。既然本章强调「换 base_url 就能切平台」，可考虑补充一个智谱/DeepSeek 官方平台的接入示例（含端点写法），覆盖不用硅基流动的学员。
3. 建议给「研究助手」实战加一句预期管理：简单问题可能不会触发 `write_todos`（v0.7 行为），想观察完整规划流程需要换更复杂的问题——我就是在这里产生了一回困惑。

## 六、引用资料来源

- 课程仓库：https://github.com/datawhalechina/deepagents-in-action
- 第 1 章在线阅读：https://datawhalechina.github.io/deepagents-in-action/chapters/ch01-agent-harness/
- 第 2 章在线阅读：https://datawhalechina.github.io/deepagents-in-action/chapters/ch02-quickstart/
- Deep Agents 官方文档：https://docs.langchain.com/oss/python/deepagents/overview
- LangGraph 文档：https://docs.langchain.com/oss/python/langgraph/overview
- 智谱开放平台 OpenAI 接口文档：https://docs.bigmodel.cn/cn/guide/develop/openai/introduction
- Tavily API 文档：https://docs.tavily.com/
- Task01 笔记（环境准备）：https://github.com/KyranShi/deepagents-in-action-notes/blob/main/task01.md
