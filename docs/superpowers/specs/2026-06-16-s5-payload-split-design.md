# S5 Payload 拆分优化设计

## 背景

S5（战略定位）场景的 writer phase 2 是全流水线最脆弱的瓶颈。当前实现将整个 `S5PositioningPayload`（7 个顶层模块 + 跨字段一致性校验）通过单次 LLM 调用产出，要求 LLM 输出几千字严格合规 JSON。

**实测数据**：
- Doubao-Seed-2.0-lite：1/1 PASS，靠 fix20 代码兜底
- MiMo-v2.5-pro：0/3 PASS，writer phase 2 反复失败
- 失败类型：`blue_ocean_move.artifact_id` 缺失、字段过短、JSON 解析失败（未转义引号/未终止字符串）

**根因**：单次 LLM 输出复杂度过高，不是模型能力问题。

## 目标

1. S5 场景能稳定产出完整报告（PASS 率 > 80%）
2. quality_score ≥ 0.7
3. 减少重试耗时（当前 S5 平均 ~25 分钟，目标 < 15 分钟）
4. S1~S4 不受影响

## 方案：2-call 拆分 + 增强错误反馈

### 拆分架构

将 phase 2 的单次 LLM 调用拆为两次串行调用：

```
Phase 2a (数据层): LLM → {vendor_profiles, perceptual_map, strategy_canvas}
         ↓ 校验数据层 schema + 合并
Phase 2b (战略层): LLM → {errc_grid, blue_ocean_move, positioning_statement, category_strategy}
         ↓ 合并 → 完整 S5PositioningPayload
         ↓ 跨字段一致性校验（model_validator）
```

**拆分依据**：
- 数据层：需要竞品信息（profiles + analysis），输出结构化评分数据
- 战略层：需要 strategy_canvas 的 competitive_factors 名称（由 2a 产出），输出策略判断
- 两层之间有自然的依赖边界（ERRC 的 factor 必须与 strategy_canvas 的 competitive_factors 对应）

### Phase 2a：数据层

**输入**：scenario_input + profiles + analysis + discovered_urls

**输出**：
```json
{
  "vendor_profiles": [...],
  "perceptual_map": {...},
  "strategy_canvas": {...}
}
```

**Prompt**：从现有 `S5_PAYLOAD_PROMPT` 提取 vendor_profiles / perceptual_map / strategy_canvas 相关约束，移除 errc_grid / blue_ocean_move / positioning_statement / category_strategy 部分。

**校验**：使用 `S5VendorProfile` / `PerceptualMap` / `StrategyCanvas` 分别校验，不需要 `S5PositioningPayload` 的跨字段 validator。

### Phase 2b：战略层

**输入**：scenario_input + analysis + phase_2a_output（提取 competitive_factors 名称列表 + vendor_names）+ discovered_urls

**输出**：
```json
{
  "errc_grid": {...},
  "blue_ocean_move": {...},
  "positioning_statement": {...},
  "category_strategy": {...}
}
```

**Prompt**：注入 phase 2a 产出的 `competitive_factors` 名称列表，要求 ERRC 的 factor 必须基于这些因子。注入 vendor_names 供 category_strategy.competitors_implied 参考。

**校验**：使用 `ERRCGrid` / `BlueOceanMove` / `PositioningStatement` / `CategoryStrategy` 分别校验。

### 重试策略

每个 phase 独立重试，最多 2 次（与当前 `max_retries=2` 一致）：
- Phase 2a 校验失败 → 重试 phase 2a
- Phase 2b 校验失败 → 重试 phase 2b
- 合并后跨字段校验失败 → 根据错误字段定位到 2a 或 2b，重试对应 phase
- Phase 2a 全部重试失败 → raise `WriterRouteToWriter`（整个 writer 重来）
- Phase 2b 全部重试失败 → raise `WriterRouteToWriter`

### 合并与最终校验

Phase 2b 产出后，代码将 2a + 2b 的结果合并为完整的 `S5PositioningPayload` dict，然后：
1. 补充 `scenario_type: "S5"`
2. 补充 `artifact_id`（如果 LLM 遗漏）
3. 调用 `S5PositioningPayload(**merged_dict)` 做最终的跨字段一致性校验
4. 校验失败时，将错误摘要注入重试 prompt（仅重试失败的 phase）

### 增强错误反馈

当前 `_build_error_summary` 只输出 `loc` + `msg`。增强为：

```
上次输出有以下问题，请逐条修正：
1. vendor_profiles[2].strengths: 只有 1 条，schema 要求 ≥2 条
2. perceptual_map.x_axis.low_label: "低" 只有 1 个字符，要求 ≥2 字符
3. blue_ocean_move.artifact_id: 必填字段缺失
```

增强逻辑：
- 提取 `ValidationError` 的 `loc` 路径，转为人类可读的字段路径
- 提取 `type` 信息，翻译为具体的期望值（如 "string_too_short" → "要求 ≥N 字符"）
- 每条错误独立一行，带序号

此增强适用于所有场景的 phase 2 重试，不只 S5。

## 文件改动

| 文件 | 改动 |
|------|------|
| `src/agents/writer_orchestrator.py` | `_call_phase2_with_validation` 增加 S5 分支；新增 `_call_s5_phase2a` / `_call_s5_phase2b` / `_merge_s5_payload` 方法；增强 `_build_error_summary` |
| `src/agents/prompts/writer/payload/s5.py` | 拆为 `s5_data.py`（数据层 prompt）+ `s5_strategy.py`（战略层 prompt）；原 `s5.py` 改为 import 两者（向后兼容） |
| `tests/unit/test_writer_orchestrator.py` | 新增 S5 拆分单测：phase2a 校验通过 / phase2b 校验通过 / 合并后跨字段校验通过 / 错误反馈增强 |

## 不改动的部分

- `S5PositioningPayload` schema 不变
- `s5.py` normalizer (fix20) 保留
- S1~S4 的 phase 2 逻辑不变
- Inspector 不变

## 验证标准

1. S5 端到端 PASS（MiMo 下至少 2/3 成功）
2. quality_score ≥ 0.7
3. S1~S4 全量回归 443 passed
4. 单次 phase 2 耗时 < 10 分钟（当前 ~13 分钟）
