# 技术周报 · Deep Agents / LangGraph / Agent Harness 本周动态

> 本期聚焦：Deep Agents 0.6 大版本、Agent Harness 从 SDK 走向托管运行时、跨工具互操作与安全边界。

## 本周五大动态

### 1. LangChain 发布 Deep Agents v0.6：迄今最大版本，全面押注性能与模型适配
主打 code interpreter（程序化工具调用）、harness profiles（适配 Kimi/Qwen/DeepSeek 等开源权重模型）、Streaming v3 类型化事件流、DeltaChannel 增量 checkpoint（长会话存储最高缩减 100 倍），以及基于 LangSmith 的版本化文件系统 ContextHubBackend。其 Streaming v3 / DeltaChannel 依托 LangGraph v1.2 运行时，是本周 LangGraph 侧最主要的实质进展。
来源：https://www.langchain.com/blog/deep-agents-0-6

### 2. OpenAI Agents API 公测：以 Codex harness 为托管运行时
会话管理、沙箱执行等能力以 managed runtime 形式开放，标志着 OpenAI 的 agent harness 从 SDK 走向托管服务，与 LangChain/Anthropic 的托管路线正面竞争。
来源：https://aiagentsdirectory.com/news/ai-agents-news-brief-september-12-2026

### 3. Claude Code 2.1.277 支持 AGENTS.md，跨 Agent 指令互操作破冰
无 CLAUDE.md 时自动回退读取 AGENTS.md（Bedrock/Vertex/Foundry 暂不支持），跨 harness 共享项目级指令迈出关键一步，社区反响热烈。
来源：https://news.ycombinator.com/item?id=49758250

### 4. Apple Xcode 26.3 集成 Claude Agent SDK：harness 进入 IDE 主战场
从逐轮对话升级为 IDE 内自主长时程编码任务，可跨 SwiftUI/UIKit/Swift Data 理解整个项目架构；通用 agent harness 正加速被植入开发工具链。
来源：https://www.investing.com/news/stock-market-news/apples-xcode-263-adds-claude-agent-sdk-integration-93CH-4482891

### 5. TypeSafe AI 发布小模型 Jev，并深度嵌入 Deep Agent harness
Jev 号称分类类任务比 LLM 快 200x、便宜 400x，官方演示其在 Deep Agent harness 中承担模型路由与在线评估（Jev-as-a-judge），同步发布 `langchain-typesafe` 包，展示了 harness 内大小模型协同的新范式。
来源：https://www.langchain.com/blog/building-a-harness-with-jev

## 趋势点评
Agent harness 正从 SDK 走向托管运行时，性能优化与信任边界成为竞争焦点。
