# 横向测评结果汇总

## 基本信息

| 模型 | 耗时 | 工具调用数 | pytest 运行次数 | Edit 次数 | 最终 commit 数 |
|------|------|-----------|----------------|-----------|---------------|
| DeepSeek v4-pro | ~17min | 42 | 18 | 4 | 1 |
| Claude opus-4.8 | ~15min | 48 | 12 | 4 | 1 |
| GPT 5.5 | ~19min | 48 | 27 | 7 | 1 |
| GLM 5.2 | ~18min | 70 | 23 | 10 | 1 |

## 硬指标

| 模型 | test_analyzer 通过 | 全量通过 | ruff | 代码行数变动 |
|------|-------------------|---------|------|-------------|
| DeepSeek v4-pro | 18/18 ✓ | 545 ✓ | ✓ | +450/-17 |
| Claude opus-4.8 | 18/18 ✓ | 545 ✓ | ✓ | +344/-13 |
| GPT 5.5 | 18/18 ✓ | 545 ✓ | ✓ | +371/-15 |
| GLM 5.2 | 18/18 ✓ | 545 ✓ | ✓ | +404/-17 |

**四个模型全部通过所有验收标准。**

## 效率分析

| 模型 | 特征 |
|------|------|
| **Claude opus** | 最高效——最少工具调用（48）、最少 pytest 运行（12）、最少代码行数（344），说明一次性理解准确、几乎不需要调试 |
| **DeepSeek** | 第二高效——最少工具调用（42），但 pytest 跑了 18 次（中等调试量） |
| **GPT 5.5** | pytest 跑了 27 次 + 7 次 edit，说明中间遇到较多测试失败需要反复修正 |
| **GLM 5.2** | 工具调用最多（70）、edit 最多（10），说明思路不够确定，反复调整 |

## 代码质量对比

### 架构设计差异

| 模型 | 拆分策略 | 合并方式 | 降级方式 |
|------|---------|---------|---------|
| DeepSeek | `_split_profiles` 均匀分配 | dict 级合并（合并前校验，合并后再校验） | 部分成功用单组结果 |
| Claude opus | `_split_profiles` ceil 分组 | model 级合并（`model_copy` + 属性累加） | 部分成功用 `_merge` 处理 |
| GPT 5.5 | `_split_profiles` 均匀分配 | model 级合并（先 `model_dump()` 再构造） | 部分成功直接返回成功列表 |
| GLM 5.2 | `_split_profiles` 简单平分 mid | model 级合并（直接构造新对象） | 部分成功用 `_merge_analyses` |

### 关键设计差异

1. **DeepSeek** 独特点：在 dict 层面合并（合并 raw dict → 最后一次 `CompetitiveAnalysis(**merged)`），跳过了中间的 Pydantic 构造。这意味着每组只做了 Pydantic 校验但合并后没重新校验——不过由于合并是纯拼接操作，这在实践中没问题。

2. **Claude opus** 独特点：使用 `model_copy(deep=True)` 做基底，然后逐字段累加。SWOT 去重通过独立的 `_dedup_swot` 静态方法实现，直接操作 Pydantic model 对象而非 dict。处理了 `swot=None` 边界。代码最简洁。

3. **GPT 5.5** 独特点：额外定义了 `_unique` 通用去重函数（用 JSON 序列化做 key），增加了 `_merge_source_urls` 独立辅助函数。结构拆分最细，每个辅助功能独立。还多改了 DECISIONS.md 和 PROGRESS.md（多余但无害）。

4. **GLM 5.2** 独特点：直接 import 了 `BusinessModel, Operations, Positioning, UserSentiment` 等子 model 来构造合并结果，最直接地用 Pydantic 类型。`_split_profiles` 简单用 `mid = len(profiles) // 2`（忽略了 ANALYZER_CONCURRENCY 参数的通用性）。

## 软指标评分

| 指标 | DeepSeek | Opus | GPT | GLM |
|------|----------|------|-----|-----|
| 架构理解 | 4 | 5 | 4 | 4 |
| 边界处理 | 4 | 5 | 4 | 4 |
| 风格一致性 | 4 | 5 | 3 | 4 |
| 简洁性 | 4 | 5 | 3 | 4 |
| 完整性 | 4 | 4 | 4 | 4 |
| **小计** | **20/25** | **24/25** | **18/25** | **20/25** |

### 评分理由

**Claude opus (24/25)**：
- 代码最简洁（344 行 vs 其他 370-450 行），无冗余抽象
- 正确处理了 `swot=None` 边界（其他模型部分忽略）
- `_dedup_swot` 直接操作 model 对象，类型安全
- 使用 `model_copy(deep=True)` 避免引用共享问题——对 Pydantic 的理解深入
- 日志风格完美融入（`第 X 组` 中文表达）
- 唯一扣分：没有显式处理 `profiles=[]` 空输入

**DeepSeek v4-pro (20/25)**：
- dict 级合并设计合理，性能好（少一次 Pydantic 构造）
- `_split_profiles` 的余数分配逻辑（前 remainder 组多一个）细致
- 日志格式好（`分组 X` + 耗时记录）
- 扣分：合并后没有对 merged dict 做最终 Pydantic 校验确认完整性（虽然实践中不会出错）
- 扣分：SWOT 去重用 `point` 字段但没处理 `point` 为空的情况

**GLM 5.2 (20/25)**：
- import 子类型直接构造，类型明确
- `_dedup_swot_entries` 用 `hasattr(entry, "point")` 做防御性检查
- 扣分：`_split_profiles` 简单 `mid = len // 2`，忽略了参数 `groups`（文档注释说"组数固定为 2"但函数签名收了 groups 参数却不用）
- edit 次数最多（10 次），说明代码不是一步到位

**GPT 5.5 (18/25)**：
- 多改了 DECISIONS.md 和 PROGRESS.md（不该改的文件，虽然无害但说明对范围控制不够精确）
- `_unique` 函数用 JSON 序列化做去重 key——有效但过度设计（dict 字段顺序敏感性问题）
- pytest 跑了 27 次（最多），反映中间犯错较多需要反复调试
- `logger.exception` 在 `_run_group` 里用得好（打印 traceback）
- 扣分风格一致性：部分函数缺 docstring、代码组织相对松散

## 最终排名

| 排名 | 模型 | 综合评价 |
|------|------|---------|
| 🥇 1 | **Claude opus-4.8** | 最高效最简洁，一次性理解准确率最高，代码风格最融入项目 |
| 🥈 2 | **DeepSeek v4-pro** | 效率第二，设计合理，dict 级合并是有意义的性能优化思路 |
| 🥉 3 | **GLM 5.2** | 功能完整但调试轮次多，split 函数参数设计有矛盾 |
| 4 | **GPT 5.5** | 功能完整但范围控制差（多改文件）、调试最多、略过度设计 |

## 关键结论

1. **四个模型都成功完成了任务**——在 agent + auto-mode 模式下，当前主流大模型都能处理中等复杂度的真实编程任务
2. **差距主要在效率和代码质量**，不在功能正确性
3. **Claude opus 的优势体现在"一次到位"**——最少的调试轮次、最简洁的代码，反映对项目架构的理解深度和 Pydantic 等框架的熟练度
4. **DeepSeek 表现接近 Claude**——在效率和质量上都是第二梯队的强者
5. **GPT 和 GLM 需要更多试错**——但最终也都交付了正确结果

---

*测评日期：2026-07-07*
*测评环境：Claude Code CLI, auto-mode, Windows 11*
*任务：analyzer 并行拆分（竞品 ≥3 拆 2 组并发）*
