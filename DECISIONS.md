# Technical Decisions

项目关键技术决策记录。每个决策包含选择、理由和被排除的备选方案。

> 决策会直接影响后续代码实现，比进度信息更重要。

## Format

```markdown
## YYYY-MM-DD: 决策标题
- 选择：...
- 理由：...
- 备选：...（排除原因：...）
```

---

## 2026-05-30: 编排框架选型
- 选择：LangGraph
- 理由：课题要求质检→采集的反馈闭环（DAG 循环），LangGraph 原生支持条件分支和环路
- 备选：CrewAI（排除原因：声明式编排，复杂闭环控制力弱，需要额外 hack）

## 2026-05-30: Agent 构建框架选型
- 选择：待定（LangChain 或纯手写）
- 理由：取决于 Doubao 模型的 SDK 适配情况
- 备选：Claude Agent SDK / OpenAI Agents SDK（排除原因：课题提供 Doubao 模型，需优先适配）

## 2026-05-30: LLM 选型
- 选择：Doubao-Seed-2.0-lite（EP: ep-20260514111325-xjmj7）
- 理由：课题官方提供的模型资源，所有成员共用
- 备选：无（课题要求使用指定资源）
