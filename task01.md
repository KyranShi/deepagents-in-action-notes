# Deep Agents 实战 · Task01 打卡：环境准备实践笔记

> 课程：[《Deep Agents 实战》](https://github.com/datawhalechina/deepagents-in-action)（Datawhale 开源课程，LangChain 官方大使 [@沧海九粟](https://space.bilibili.com/28357052) 出品）
> 对应章节：准备篇 [AgentSeek 生命周期工作流（上）](https://datawhalechina.github.io/deepagents-in-action/chapters/pre01-agentseek-create/) + [安装开发技能（下）](https://datawhalechina.github.io/deepagents-in-action/chapters/pre02-agentseek-skills/)
> 实践环境：macOS (Apple Silicon) · 系统 Python 3.14.6 · Node.js v24.16.0 · npm 12.0.2 · uv 0.11.26
> 实践日期：2026-09-14
> 实测版本：AgentSeek CLI v0.1.4 · AgentSeek API v0.2.3 · LangGraph 1.2.11 · DeepAgents 0.7.13 · Python (venv) 3.13.14

---

## 一、学习内容归纳

Task01 的目标是**在动手写 Agent 之前，先把可运行的研究型 DeepAgents 应用搭起来**。两章内容可以归纳为一条「模板 → 依赖 → 凭证 → 检查 → 运行」的生命周期链路：

**pre01：用 AgentSeek 启动 DeepAgents 模板**

- AgentSeek 是面向 AI 应用开发的「模板 + 生命周期」工具，5 个核心命令各管一个阶段：
  `create`（从模板生成项目）→ `info`（查看摘要）→ `task`（跑依赖安装等一次性任务）→ `doctor`（就绪检查）→ `dev`（启动本地服务）。
- 生成项目的生命周期声明集中在 `.agentseek/lifecycle.toml`：它声明需要的工具（uv/node/npm）、环境变量、一次性任务和两个本地服务（LangGraph 后端 `:2024`、React 前端 `:5174`）。AgentSeek 只读这份声明，不接管应用自身的框架代码。
- `deepagents/research` 模板 = DeepAgents 研究 Agent + Tavily 搜索 + React 前端，模型走 OpenAI 兼容接口（我用智谱 GLM 接入）。

**pre02：为 AI 编码助手安装开发技能**

- 通过 `npx skills add` 安装两个**编码助手开发技能**：`langchain-dev-guide`（LangChain/LangGraph/DeepAgents 工程陷阱与修复）和 `langsmith-trace`（Trace 查询调试）。
- 最重要的概念区分：**编码助手开发技能**（服务 Codex/Claude Code 等工具，`npx skills add` 安装到 `.agents/skills/`）≠ **DeepAgents 运行时 Skill**（服务你构建的 Agent，`create_deep_agent(skills=[...])` 加载）。两者都用 `SKILL.md`，但服务对象完全不同。

## 二、代码运行记录

按教程顺序逐步执行，以下均为 macOS 终端真实输出（节选）。

### 2.1 安装 uv 与 AgentSeek

系统已有 uv（Homebrew 安装），直接装 AgentSeek：

```bash
$ uv tool install --upgrade agentseek
Installed 1 executable: agentseek
warning: `~/.local/bin` is not on your PATH.

$ export PATH="$HOME/.local/bin:$PATH"
$ agentseek version
AGENTSEEK v0.1.4
```

### 2.2 查看模板并创建项目

```bash
$ agentseek create --list-templates --checkout main
  deepagents (7 templates)
    deepagents/default      Local create_deep_agent runnable ...
    deepagents/research     DeepAgents research agent with Tavily search, ...
    deepagents/mcp          DeepAgents MCP Tools app ...
    ...（共 bub/deepagents/langchain 等多组模板）

$ agentseek create deepagents/research --checkout main --no-input
Created research_deepagent

$ cd research_deepagent
```

生成项目结构与教程一致：

```text
research_deepagent/
├── .agentseek/lifecycle.toml   # version 2
├── .env.example
├── frontend/           # React + Vite 前端
├── langgraph.json      # graphs: research -> src/research_deepagent/agent.py:graph
├── pyproject.toml      # requires-python >= 3.12, deepagents>=0.5.3
└── src/research_deepagent/
    ├── agent.py
    ├── prompts.py
    └── tools.py
```

### 2.3 查看生命周期配置

```bash
$ agentseek info
Project
  Root: ~/projects/research_deepagent
  Name: Research DeepAgent
  Template: deepagents/research
  Lifecycle: .agentseek/lifecycle.toml / version 2

Entrypoints
  Langgraph: http://127.0.0.1:2024 (runtime: agentseek-api)
  Frontend:  http://127.0.0.1:5174 (runtime: vite)

Environment
  OPENAI_API_KEY: missing
  TAVILY_API_KEY: missing

$ agentseek task --list
  sync      Install Python dependencies with uv.
  frontend  Install frontend dependencies.
```

### 2.4 安装前后端依赖

```bash
$ agentseek task sync        # 实际执行 uv sync
+ deepagents 0.7.13  + langchain ... + tavily-python ...
（uv 按项目 requires-python 自动准备 Python 3.13.14 虚拟环境，共 118 个包）

$ .venv/bin/python --version
Python 3.13.14

$ agentseek task frontend    # 实际执行 npm install --prefix frontend
found 0 vulnerabilities
```

### 2.5 配置 `.env` 与 Key 验证

```bash
$ cp .env.example .env
$ cp frontend/.env.example frontend/.env
```

我的模型接入选择：**智谱 GLM（OpenAI 兼容接口）**。最终生效的配置：

```bash
AGENTSEEK_MODEL_PROVIDER=openai
AGENTSEEK_MODEL=glm-5.3-flash
OPENAI_API_BASE=https://open.bigmodel.cn/api/paas/v4
OPENAI_API_KEY=<已填入，格式为 id.secret>
TAVILY_API_KEY=<已填入>
LANGSMITH_TRACING=false
```

配置完成后先用一条 `curl` 直接打模型接口验证凭证，再跑应用——这一步帮我省了大量排障时间（见坑 5）：

```bash
$ curl https://open.bigmodel.cn/api/paas/v4/chat/completions \
    -H "Authorization: Bearer $OPENAI_API_KEY" -H "Content-Type: application/json" \
    -d '{"model":"glm-5.3-flash","messages":[{"role":"user","content":"只回复两个字：连通"}]}'
{"choices":[...],"model":"glm-5.3-flash","usage":{"total_tokens":49,...}}
```

> 有意思的观察：`glm-5.3-flash` 是推理模型，响应里会多一个 `reasoning_content` 字段装思考过程。小样本测连通时如果设了很小的 `max_tokens`，可能只看到思考、看不到最终回答，不是故障。

### 2.6 就绪检查与启动

```bash
$ agentseek dev --dry-run
Startup plan
  Langgraph: uv run agentseek-api dev --port 2024
  Frontend:  npm run dev

$ agentseek doctor
ok   lifecycle.toml: Lifecycle spec is present.
ok   uv / node / npm: available.
ok   pyproject.toml / langgraph.json / frontend/package.json: present.
ok   frontend/node_modules: present.
ok   .env: present.
ok   OPENAI_API_KEY / TAVILY_API_KEY: configured.
   ...（共 19 项，全部 ok）

$ agentseek dev
AgentSeek v0.2.3
- 🚀 API: http://localhost:2024
- 📚 Docs: http://localhost:2024/docs
  VITE v8.3.0  ready in 825 ms
  ➜  Local:   http://127.0.0.1:5174/
INFO:     Application startup complete.
INFO:     "GET /health HTTP/1.1" 200 OK

$ curl http://127.0.0.1:2024/health
{"status":"healthy"}

$ agentseek doctor --live
   ...（在 doctor 基础上追加两项）
ok   langgraph: http://127.0.0.1:2024/health is reachable.
ok   frontend: http://127.0.0.1:5174 is reachable.
（共 21 项，全部 ok）
```

### 2.7 端到端验证：跑一次真实研究任务

除了在网页输入研究问题，还可以直接调 LangGraph 兼容 API 留下可复现的记录：

```bash
# 1) 服务元信息
$ curl http://127.0.0.1:2024/info
{"version":"0.2.3","langgraph_py_version":"1.2.11",...,
 "checkpoint_backend":"langchain-oceanbase",...}

# 2) 创建线程并发起同步运行
$ curl -X POST http://127.0.0.1:2024/threads -d '{}' -H "Content-Type: application/json"
{"thread_id":"67919841-...","status":"idle",...}

# 3) 同步等待运行完成（实测 HTTP 200，总耗时 218.1 秒）
```

**实测结果（节选）**——研究 Agent 自主完成了「研究简报 → 委派子 Agent 搜索 → 写入文件系统 → 汇总报告」的完整流程：

```markdown
## Answer

**DeepAgents** (Python package: `deepagents`) is an open-source "agent harness"
from LangChain for building AI agents that can plan, spawn subagents, and use a
virtual file system to reliably execute complex, long-horizon, multi-step tasks.
Built on top of LangGraph, it packages four key capabilities — a detailed system
prompt, a planning/todo tool, subagent delegation, and a file system for context
management — following the same architecture behind products like OpenAI Deep
Research, Manus, and Claude Code.

**Source:** [Deep Agents overview — Docs by LangChain]
(https://docs.langchain.com/oss/python/deepagents/overview)

The full report has been saved to `/final_report.md`.
```

运行结束后查看线程状态，能找到研究 Agent 写入虚拟文件系统的两个文件，证明文件系统工具真实生效：

```text
$ GET /threads/<thread_id>/state → values.files
['/research_request.md', '/final_report.md', '/large_tool_results/...']
```

我的完整跑通记录：GLM `glm-5.3-flash` 模型调用 + Tavily 联网搜索 + DeepAgents 编排（子 Agent、虚拟文件系统、最终报告），全链路 218 秒无错误。前端界面运行截图见评论区补充图。

### 2.8 安装开发技能（pre02）

```bash
$ npx skills add ob-labs/agentseek --skill langchain-dev-guide --skill langsmith-trace --yes
◇  Installed 2 skills
│  ✓ langchain-dev-guide (copied) → .agents/skills/langchain-dev-guide
│  ✓ langsmith-trace (copied)     → .agents/skills/langsmith-trace

$ npx skills list
Project Skills
langchain-dev-guide  .agents/skills/langchain-dev-guide   Source: ob-labs/agentseek
langsmith-trace      .agents/skills/langsmith-trace       Source: ob-labs/agentseek
```

## 三、踩坑与填坑记录

**坑 1：Git 走了未启动的代理，克隆课程仓库失败。**
`git clone` 直接报 `Failed to connect to 127.0.0.1 port 7890`。原因是我之前给 Git 配置过全局代理 `http.proxy`，当时代理软件没开。开启代理后恢复正常。
填坑：这正是教程「网络问题排查」一节说的情况——先用 `git ls-remote` 或看报错端口判断是不是代理问题。另外教程提醒设置 `NO_PROXY=127.0.0.1,localhost` 避免本机前后端流量也走代理，这个细节很实用。

**坑 2：`uv tool install` 装完 agentseek 找不到命令。**
macOS 上同样会遇到教程里 Windows 小节提到的 PATH 问题：uv 装的工具在 `~/.local/bin`，不在当前 PATH。`export PATH="$HOME/.local/bin:$PATH"` 后立即可用（一劳永逸可以用 `uv tool update-shell`）。

**坑 3：教程版本与实际安装版本存在差异，输出对不上怎么办。**
教程验证时是 AgentSeek `0.1.2`，我装到的是 `0.1.4`；生成项目的 `lifecycle.toml` 已是 `version 2`，环境变量比教程示例多了 `SEEKDB_EMBED` 等持久化配置，`.env.example` 的默认模型也不同。教程开头的声明「如果任务名称与本文不同，以 `agentseek task --list` 的输出为准」就是为这种情况准备的——**以命令实际输出为准，而不是逐字对照教程截图**。

**坑 4（其实不算坑）：系统 Python 版本过高要不要降级？**
系统 Python 是 3.14.6，教程要求 3.12/3.13。实测完全不用手动降级：`uv sync` 按项目 `requires-python >= 3.12` 自动下载并使用 Python **3.13.14** 创建虚拟环境。

**坑 5：模型 API Key 一直 401「令牌已过期或验证不正确」。**
这是我这次花时间最多的坑，分三层：
1. **Key 复制不完整。** 智谱的 API Key 是 `{id}.{secret}` 格式（中间有个点），第一遍只复制了前半段，在所有端点都 401。重新生成并复制完整 Key 后解决。
2. **端点路径搞混。** 「Coding Plan」和「标准开放平台」的 OpenAI 兼容端点不同（`/api/coding/paas/v4` vs `/api/paas/v4`）。我的 Key 实测走标准端点。**先查开发文档确认端点，再用 curl 单测凭证，最后才去怀疑应用配置。**
3. **推理模型的「假故障」。** 换对 Key 后第一次测试仍「看不到回答」——其实是 `glm-5.3-flash` 的输出先写在 `reasoning_content` 里，`max_tokens` 太小只够思考不够作答。调大即可。

方法论总结：**把「凭证、端点、参数」三层拆开逐层用 curl 验证**，比盯着应用日志猜快得多。

## 四、学习心得

这次 Task01 最大的收获是理解了「环境准备」本身也是一门工程方法。以前搭环境是东拼西凑地装依赖，出了问题靠搜索碰运气；这套生命周期工作流把「创建 → 查看 → 准备 → 检查 → 运行」固化成 5 个命令，把工具版本、环境变量、服务端口这些隐性知识显式写进 `lifecycle.toml`，`doctor` 在启动前就把缺 Key、缺依赖一次性暴露出来，`doctor --live` 再把两个服务的连通性纳入体检。我踩的几个坑（代理没开、PATH 未配置、Key 三层问题、教程与模板版本漂移）恰恰验证了这套流程的价值：每个问题都能落到明确的检查项上，而不是散落在启动失败的日志里。pre02 对两类 Skill 的区分也纠正了我的误解——给编码助手装的「开发技能」和给 Agent 运行时装的「运行时技能」是两回事，安装方式和使用者完全不同。

## 五、对教程的意见及建议

整体评价：两章内容命令可复现、边界清晰（尤其是「AgentSeek 不接管框架代码」「两类 Skill 的区别」这些概念划定），网络排查一节直接救了我一次。四点小建议：

1. pre01 的 `.env` 示例变量（如 `AGENTSEEK_MODEL=zai-org/GLM-5.2`）与最新模板批次的 `.env.example`（默认 `gpt-4.1-mini`、新增 SeekDB 持久化段）已不完全一致，建议在文中加一句「变量以生成项目的 `.env.example` 为准」。
2. `uv tool update-shell` / PATH 提示目前放在 Windows 小节，macOS/Linux 新手同样会踩（我就踩了），建议扩展为通用提示。
3. 建议在 2.5 节加一句通用方法论：换任何模型供应商前，先各用一条 `curl` 验证「端点 + Key + 模型 ID」三要素（智谱 GLM、DeepSeek 等国产 OpenAI 兼容服务尤其适用），能省掉应用层排障的大半时间。
4. 教程默认写 SiliconFlow，可考虑补一段「其他国产模型供应商接入示例」（如智谱 GLM 的 OpenAI 兼容端点与 `id.secret` 格式 Key），方便没有 SiliconFlow 账号的学员。

## 六、引用资料来源

- 课程仓库：https://github.com/datawhalechina/deepagents-in-action
- 课程在线阅读（pre01/pre02）：https://datawhalechina.github.io/deepagents-in-action/
- 视频教程（B站）：https://space.bilibili.com/28357052/lists/7757577?type=season
- 智谱开放平台 OpenAI 接口开发文档：https://docs.bigmodel.cn/cn/guide/develop/openai/introduction
- AgentSeek 快速开始：https://github.com/ob-labs/agentseek/blob/main/docs/get-started/index.zh.md
- AgentSeek Templates（deepagents/research 模板）：https://github.com/agentseek-ai/agentseek-templates
- langchain-dev-guide / langsmith-trace 技能源码：https://github.com/ob-labs/agentseek/tree/main/skills
- Deep Agents 官方文档：https://docs.langchain.com/oss/python/deepagents/overview
- SiliconFlow OpenAI 兼容配置（课程默认方案，参考）：https://docs.siliconflow.cn/cn/usercases/use-siliconcloud-in-KiloCode
- Tavily：https://app.tavily.com/
- LangSmith Tracing Quickstart：https://docs.langchain.com/langsmith/observability-quickstart
