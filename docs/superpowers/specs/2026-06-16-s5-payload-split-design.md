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

**拆分依据**（主要收益是降低单次输出复杂度）：
- 数据层：需要竞品信息（profiles + analysis），输出结构化评分数据（vendor_profiles + perceptual_map + strategy_canvas）
- 战略层：需要 strategy_canvas 的 competitive_factors 名称列表（由 2a 产出），输出策略判断（errc_grid + blue_ocean_move + positioning_statement + category_strategy）
- 每层输出量约为原来的一半，JSON 合规率显著提升
- 注：ERRC 的 factor 与 competitive_factors 的对应关系仅在 prompt 层面约束，schema 层面无强制校验。这是可接受的，因为拆分的核心收益是降低单次输出长度，而非依赖 factor 对齐

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

**校验**：使用 `S5VendorProfile` / `PerceptualMap` / `StrategyCanvas` 分别校验。`StrategyCanvas` 的 `model_validator _check_factor_key_completeness` 会校验 competitive_factors 名称与 value_curves[*].factor_levels 的一致性，这在 phase 2a 内部完成。

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

**Prompt**：注入 phase 2a 产出的 `competitive_factors` 名称列表，要求 ERRC 的 factor 基于这些因子。注入 vendor_names 供 category_strategy.competitors_implied 参考。显式标注 `blue_ocean_move` 为 Optional（可省略），避免 LLM 产出不完整的 BlueOceanMove dict 浪费重试。

**校验**：使用 `ERRCGrid` / `BlueOceanMove` / `PositioningStatement` / `CategoryStrategy` 分别校验。

### LLM 调用预算

当前 `WRITER_MAX_LLM_CALLS=18`。拆分后的调用预算：

| 阶段 | 正常路径 | 最坏路径（每 phase 重试 2 次） |
|------|---------|-------------------------------|
| Phase 1 outline | 1 | 1 |
| Phase 2a 数据层 | 1 | 3 (1+2 retries) |
| Phase 2b 战略层 | 1 | 3 (1+2 retries) |
| Phase 3 narrative | 6 | 6 (并发，不重试) |
| **合计** | **9** | **13** |

正常路径 9 次，最坏路径 13 次，均在 18 次上限内。合并后跨字段校验失败时重试对应 phase，最多额外 2 次（仍计入 phase 2a 或 2b 的重试预算），总计不超过 15 次。**无需调整 `WRITER_MAX_LLM_CALLS`**。

### 重试策略

每个 phase 独立重试，最多 2 次（与当前 `max_retries=2` 一致）：
- Phase 2a 校验失败 → 重试 phase 2a
- Phase 2b 校验失败 → 重试 phase 2b
- 合并后跨字段校验失败 → 按 field→phase 路由表定位，重试对应 phase（见下表）
- Phase 2a 全部重试失败 → raise `WriterRouteToWriter`（整个 writer 重来）
- Phase 2b 全部重试失败 → raise `WriterRouteToWriter`

**Field→Phase 路由表**：

| 错误字段路径前缀 | 归属 phase |
|-----------------|-----------|
| `vendor_profiles` | 2a |
| `perceptual_map` | 2a |
| `strategy_canvas` | 2a |
| `errc_grid` | 2b |
| `blue_ocean_move` | 2b |
| `positioning_statement` | 2b |
| `category_strategy` | 2b |
| 跨 phase 引用（如 vendor_names 一致性） | 2a（数据层是源头） |

### 合并与最终校验

Phase 2b 产出后，代码将 2a + 2b 的结果合并为完整的 `S5PositioningPayload` dict，然后：
1. 补充 `scenario_type: "S5"`
2. 补充 `artifact_id`（如果 LLM 遗漏）
3. 运行 normalizer `_normalize_s5_raw`（仅在此处运行一次，不在各 phase 分别运行）
4. 调用 `S5PositioningPayload(**merged_dict)` 做最终校验

**merge 校验的实际范围**：`S5PositioningPayload` 的唯一 `model_validator` 是 `_check_competitor_consistency`，校验 vendor_profiles / perceptual_map / strategy_canvas 三者的 competitor_name 一致性——这些全部来自 phase 2a，因此 merge 校验本质是 re-instantiation。Phase 2b 字段（errc_grid 等）无跨 phase validator，由各自的 Pydantic schema 独立校验。

### Normalizer 交互

normalizer `_normalize_s5_raw` **仅在 merge 后运行一次**，不在各 phase 分别运行。这保持了与当前行为的一致性。

注意：normalizer 的 category_strategy 占位逻辑（fix20）可能掩盖 phase 2b 的 LLM 失败。这是可接受的——fix20 是兜底安全网，正常情况下 phase 2b 应产出合规的 category_strategy，normalizer 只处理极端边缘情况。

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

此增强**初始版本仅对 S5 生效**，S1~S4 保持原有错误反馈格式，避免回归风险。验证稳定后可推广到其他场景。

## 文件改动

| 文件 | 改动 |
|------|------|
| `src/agents/writer_orchestrator.py` | `_call_phase2_with_validation` 增加 S5 分支；新增 `_call_s5_phase2a` / `_call_s5_phase2b` / `_merge_s5_payload` 方法；增强 `_build_error_summary` |
| `src/agents/prompts/writer/payload/s5.py` | 拆为 `s5_phase2a.py`（数据层 prompt）+ `s5_phase2b.py`（战略层 prompt）；原 `s5.py` 改为 import 两者（向后兼容） |
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
