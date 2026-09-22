# Agent Harness 三大框架对比分析报告
## Deep Agents vs. Claude Agent SDK vs. Codex SDK

> 调研日期：2026-07 | 详细资料来源见文末及 `/workspace/research/` 目录下的分框架调研笔记

---

## 1. 背景：什么是 Agent Harness

当前 Agent 领域的核心算法其实非常简单：**LLM 在循环中调用工具（tool-calling loop）**。真正拉开产品差距的，是包裹这个循环的"执行框架"（harness）——即上下文管理、文件系统、子智能体、权限审批、沙箱、记忆、评估等工程能力。行业普遍观察到："模型不再是产品，harness 才是"。实证之一：LangChain 团队仅替换 harness、不换模型，Terminal Bench 2.0 得分即从 52.8% 升至 66.5%。

三大框架分别代表三种出身：
- **Deep Agents**（LangChain）：第三方通用 harness，把 Claude Code / Deep Research / Manus 的共性模式抽象成库；
- **Claude Agent SDK**（Anthropic）：Claude Code 的库形态，模型厂商把自家编码智能体的 harness 开放为编程接口；
- **Codex SDK**（OpenAI）：同一路线的 OpenAI 版本，把开源 Codex CLI/agent 封装为可嵌入组件。

---

## 2. 三框架概览

| 维度 | Deep Agents | Claude Agent SDK | Codex SDK |
|---|---|---|---|
| 维护方 | LangChain | Anthropic | OpenAI |
| 定位 | 通用"带电池"agent harness | Claude Code 的可编程库形态 | Codex 编码智能体的嵌入式 SDK |
| 语言 | Python + JS/TS | Python + TypeScript | TypeScript（@openai/codex-sdk）+ Python（JSON-RPC 控制 app-server） |
| 底层实现 | LangChain 1.0 抽象 + LangGraph 运行时 | 包装 Claude Code agent loop（驱动 CLI） | 包装 codex CLI（stdin/stdout JSONL 事件）/ app-server（JSON-RPC） |
| 模型绑定 | **任意模型供应商**（模型无关） | **深度绑定 Claude 系模型** | 深度绑定 GPT-5.x 系（与 Codex 联合优化） |
| 开源 | 开源（langchain-ai/deepagents） | SDK 开源，harness/模型闭源 | Codex CLI 开源（Rust），SDK 随仓库发布 |
| 认证 | 任意供应商 API key | ANTHROPIC_API_KEY 等 | ChatGPT 账户或 OpenAI API key |
| 理论依据 | 官方提出"深度智能体四要素"：计划工具、文件系统、子智能体、详细提示词 | 生产级编码 agent loop 的直接产品化 | "把 Codex agent 嵌入你的工作流与应用" |

---

## 3. 核心能力逐项对比

### 3.1 计划与任务分解
- **Deep Agents**：内置 Todo list 计划工具（与 Claude Code 同源），任务带 `pending / in_progress / completed` 状态并持久化在 agent state 中。计划是**一等公民**。
- **Claude Agent SDK**：无独立计划工具，计划能力内嵌于 Claude Code 的系统提示词与 TodoWrite 工具中，随 harness 自动获得。
- **Codex SDK**：计划由 Codex 自身的 prompt 与工作流承载；SDK 层面暴露的是 Thread/turn 模型，无独立计划工具配置点。

**差异本质**：Deep Agents 把"四要素"做成可配置组件；两个厂商 SDK 把这些能力"焊死"在经过自家模型调优的 harness 里。

### 3.2 文件系统与上下文管理
- **Deep Agents**：最灵活。0.2 版引入可插拔 **Backend 抽象**——LangGraph State（虚拟 FS）、LangGraph Store（跨线程持久化）、本地文件系统、外部沙箱均可作为"文件系统"。另有长线程摘要、工具输出转存磁盘、prompt caching。
- **Claude Agent SDK**：内置完整文件工具（Read/Write/Edit/Glob/Grep/Bash/WebSearch/WebFetch/AskUserQuestion），上下文管理依靠 **compaction**（SDK 监控 token 用量、自动摘要替换历史）与 server 侧 context editing（clear_thinking / clear_tool_uses 选择性剪枝）。
- **Codex SDK**：文件操作沿用 Codex 的 shell + `apply_patch` 原语；线程持久化在本地文件系统；`AGENTS.md` 提供项目级自定义指令；v0.145+ 提供分页线程历史（`thread/turns/list`、`thread/revert` 等）与 memories。

### 3.3 子智能体
- **Deep Agents**：内置 `task` 工具生成临时子智能体，独立上下文窗口，适合隔离、长时、并行任务。
- **Claude Agent SDK**：`AgentDefinition` 定义专用子智能体，子智能体在各自上下文工作、仅回传摘要；社区评测称 2026 年线已支持层级式子智能体（有深度与数量上限）。
- **Codex SDK**：子智能体支持随 Codex 近期版本（v0.145+）落地，开放程度和文档成熟度暂落后于前两者；OpenAI 更激进的子智能体能力放在通用 Agents SDK 路线图上。

### 3.4 扩展机制（自定义工具 / MCP）
- **Deep Agents**：自定义工具与内置组件并存；依托 LangChain 生态，任意供应商的 tool/MCP 集成方式一致。
- **Claude Agent SDK**：MCP 为一等公民（`mcp_servers`/`mcpServers`），被多个第三方评测称为业界最深 MCP 集成；可从项目 `.claude/`、`~/.claude/` 自动加载 Skills/Commands/Memory，Plugins 可打包分发。
- **Codex SDK**：MCP 通过 Codex 配置接入（`codex mcp-server` 亦可将 Codex 本身暴露为 MCP server）；配置覆盖以 JSON→TOML 点路径方式透传 CLI。

### 3.5 安全、权限与沙箱
- **Deep Agents**：human-in-the-loop（批准/编辑/拒绝工具调用）+ 可选沙箱；架构上同时支持"agent 跑在沙箱内"与"agent 在外、沙箱当工具"两种模式，可按用户/助手配置沙箱与 scoped threads，天然利于多租户隔离。
- **Claude Agent SDK**：细粒度权限系统（哪些工具自动执行、哪些需批准；权限规则直接引用工具名），hooks 提供生命周期拦截（PreToolUse/PostToolUse/SessionStart 等）。但**只支持 agent-in-sandbox 一种模式**，且 agent 与沙箱绑定——每用户隔离需自行搭建 wrapper 管理沙箱生命周期。
- **Codex SDK**：继承 Codex CLI 的沙箱档位（如 workspace-write / danger-full-access）与审批策略（untrusted / on-failure / never）。非交互场景下 MCP 工具调用与审批策略的交互曾是显著痛点（需 `--dangerously-bypass-approvals-and-sandbox` 或等价配置）。

### 3.6 会话、记忆与运维
- **Deep Agents**：可插拔 state/store 后端实现跨会话记忆；LangSmith 提供可观察性、评估、部署闭环。
- **Claude Agent SDK**：Sessions 可跨轮次维持上下文并 resume/fork；`fallback_model` 按序降级、`max_turns`、`max_budget_usd`、`task_budget` 等生产化参数齐全。
- **Codex SDK**：`startThread / run / resumeThread` 极简模型，线程本地持久化；支持多模态输入（图片）与流式事件；云版 Codex 提供 Automations（无人值守的 issue 分诊、告警监控、CI/CD）。

---

## 4. 核心差异总结

1. **"可配置组件" vs "联合调优整体"**。Deep Agents 把 harness 四要素做成可插拔组件，换取灵活性；两个厂商 SDK 的卖点恰相反——harness 与自家前沿模型联合训练/调优，开箱即用的任务完成率更高，但黑盒程度也更高（Claude Agent SDK 的 compaction 等能力一度只能通过 issue 请求一等参数暴露）。
2. **模型与生态锁定**。Claude Agent SDK 绑 Anthropic 产品面，Codex SDK 绑 GPT-5.x 与 Codex 运行时；Deep Agents 是三者中唯一的**模型无关**方案，且接入 LangSmith 可观察性/评估体系——跨模型、自托管、企业数据机密性场景的唯一选择。
3. **沙箱架构哲学不同**。Deep Agents 支持 agent-in-sandbox 与 sandbox-as-tool 双模式并原生支持多租户隔离；Claude Agent SDK 只支持前者；Codex SDK 走本地 CLI 沙箱档位 + 云沙箱（Codex Web）路线。
4. **抽象层级不同**。Codex SDK 的编程面最"薄"（Thread/run/resume，事件流），几乎不需要理解 agent 内部；Deep Agents 的编程面最"厚"（可替换 backend、子智能体、记忆、审批每个环节都可配置）；Claude Agent SDK 介于两者之间——选项丰富但围绕 Claude 工具命名空间展开。
5. **易混淆项澄清**：OpenAI 另有通用 **Agents SDK**（2026-04 加入 harness 与可插拔沙箱：E2B/Modal/Cloudflare 等），与 Codex SDK 是两条产品线——后者面向"嵌入 Codex 本尊"，前者面向"用 OpenAI 原语自建 harness"。

---

## 5. 选型建议

| 场景 | 推荐 | 理由 |
|---|---|---|
| 已深度使用 Claude 生态，做编码/研究/自动化 agent，追求最高开箱完成率 | **Claude Agent SDK** | 与 Claude Code 同源 harness + 模型联合优化；hooks/权限/MCP 生态最成熟 |
| 已在 OpenAI 生态（GPT-5.x），想把 Codex 能力嵌进自家工具链/CI | **Codex SDK** | Thread 模型极简，云/本地执行一致，AGENTS.md + apply_patch 原语现成 |
| 需要跨模型、自托管、多租户隔离、深度定制 harness 各环节，或已有 LangSmith/LangGraph 资产 | **Deep Agents** | 唯一模型无关方案，Backend/记忆/子智能体/审批全部可插拔 |
| 企业关注数据机密性或想配开源权重模型降本 | **Deep Agents** | 第三方 harness + 开源模型的组合是厂商 SDK 无法覆盖的空白 |

**一个务实的观点**（来自社区讨论）：第三方 harness 不会在"通用聊天循环"上打败模型厂商的自有工具，它赢在厂商不会专门做的"环产品面"——状态管理、权限边界、评估、回滚、多用户协作与部署集成。反过来，只要任务落在厂商偏好的环境内（Claude Code / Codex 的主场），厂商 SDK 几乎总是更优解。

---

## 6. 主要资料来源

**Deep Agents**
- https://docs.langchain.com/oss/python/deepagents/overview
- https://www.langchain.com/blog/deep-agents
- https://www.langchain.com/blog/doubling-down-on-deepagents
- https://github.com/langchain-ai/deepagents
- https://docs.langchain.com/oss/python/deepagents/comparison

**Claude Agent SDK**
- https://code.claude.com/docs/en/agent-sdk/overview
- https://www.morphllm.com/claude-agent-sdk
- https://hidekazu-konishi.com/entry/claude_agent_sdk_complete_guide.html
- https://platform.claude.com/docs/en/build-with-claude/context-editing

**Codex SDK**
- https://www.npmjs.com/package/@openai/codex-sdk
- https://learn.chatgpt.com/docs/codex-sdk
- https://github.com/openai/codex
- https://openai.com/index/the-next-evolution-of-the-agents-sdk （区分 OpenAI Agents SDK）

**对比与评论**
- https://docs.langchain.com/oss/python/deepagents/comparison （官方 vs Claude Agent SDK）
- https://medium.com/@rajasekar-venkatesan/anthropic-and-openai-just-shipped-the-same-answer-to-ai-agents-seven-days-apart-c19f2dc03244
- https://www.reddit.com/r/LangChain/comments/1tu9lxt/how_can_deep_agents_compete_with_claude_code
