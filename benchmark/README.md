# LLM 编程能力横向测评

## 目的

用同一个真实编程任务，在相同环境下测试 4 个模型的代码生成能力差异，为 DeepSeek 笔试题提供实证数据。

## 测评模型

| 模型 | 版本 |
|------|------|
| DeepSeek | v4-pro |
| Claude | opus-4.6 |
| GPT | 5.5 |
| GLM | 5.2 |

## 测评任务

**analyzer 并行拆分**：将当前串行处理 N 个竞品的 analyzer 改为 2 组并发处理，提速 ~50%。

任务详情见 [TASK.md](./TASK.md)。

## 测评方法

### 环境控制

- **执行环境**：全部使用 Claude Code CLI agent，auto-mode
- **代码起点**：全部从同一个 git commit（a968ec1）拉分支
- **任务输入**：完全相同的 prompt（PROMPT.md 全文）
- **交互模式**：一轮出结果，模型自主迭代直到自己满意并 commit

### 分支

```
benchmark/analyzer-parallel-deepseek
benchmark/analyzer-parallel-opus
benchmark/analyzer-parallel-gpt
benchmark/analyzer-parallel-glm
```

## 评估指标

### 硬指标（客观）

| 指标 | 衡量能力 | 判定方法 |
|------|---------|---------|
| 功能正确性 | 代码是否实现了需求 | pytest 通过 + lint 通过 |
| 测试覆盖 | 是否写了对应测试 | 新增测试数量与覆盖场景 |
| 代码量 | 是否过度/不足 | 新增/修改行数 |

### 软指标（主观 1-5 分）

| 指标 | 衡量能力 | 评判标准 |
|------|---------|---------|
| 架构理解 | 对现有项目的理解 | 是否正确复用 state 契约、错误处理模式、日志风格 |
| 边界处理 | 工程成熟度 | 部分组失败降级、空输入、单竞品不拆分 |
| 风格一致性 | 协作能力 | 命名、注释、代码组织是否与项目一致 |
| 简洁性 | 判断力 | 是否加了未要求的抽象/配置/复杂度 |
| 完整性 | 全面性 | 是否遗漏边界 case、state 更新、日志 |

## 结果

详见 [results/](./results/) 目录各模型评估文件。
