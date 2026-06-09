"""[fix4 prove-it] writer phase 2 payload prompt 必须包含 schema 字段约束块。

现象（trace 20260609-150301-df17ff / 20260609-161001-a2db5b）：
writer phase 2 反复 ValidationError：strengths < 2 / point < 10 字符 /
url < 8 字符 / artifact_id > 40 字符。LLM 不知道 schema 硬约束、
内部重试也只修一个错另一个，最终 max_retries 爆。

修：注入显眼的 SCHEMA_FIELD_CONSTRAINTS 块到 5 个场景 payload prompt。
"""
import pytest

from src.agents.prompts.writer import WRITER_PAYLOAD_PROMPTS


@pytest.mark.parametrize("scenario", ["S1", "S2", "S3", "S4", "S5"])
def test_payload_prompt_mentions_schema_constraints_block(scenario):
    """每个 scenario payload prompt 必须含 SCHEMA_FIELD_CONSTRAINTS 标志性短语"""
    prompt = WRITER_PAYLOAD_PROMPTS[scenario]
    # 标志性词组（来自 SCHEMA_FIELD_CONSTRAINTS）
    assert "字段长度与数量硬约束" in prompt, \
        f"{scenario} payload prompt 未注入 SCHEMA_FIELD_CONSTRAINTS"


@pytest.mark.parametrize("scenario", ["S1", "S2", "S3", "S4", "S5"])
def test_payload_prompt_warns_artifact_id_length(scenario):
    """每个 scenario 必须警告 artifact_id 3-40 字符（最高频踩坑）"""
    prompt = WRITER_PAYLOAD_PROMPTS[scenario]
    assert "artifact_id" in prompt and "40" in prompt, \
        f"{scenario} payload prompt 未提示 artifact_id 长度上限 40"


def test_payload_prompt_s1_warns_strengths_count():
    """S1 必须警告 strengths 2-5 条（trace 实测踩坑字段）"""
    prompt = WRITER_PAYLOAD_PROMPTS["S1"]
    assert "strengths" in prompt and "2-5" in prompt, \
        "S1 payload prompt 未提示 strengths list 长度 2-5"


@pytest.mark.parametrize("scenario", ["S1", "S2", "S3", "S4", "S5"])
def test_payload_prompt_warns_url_min_length(scenario):
    """每个 scenario 必须警告 url ≥8 字符（共用 SourceRef）"""
    prompt = WRITER_PAYLOAD_PROMPTS[scenario]
    assert "url" in prompt and ("8" in prompt or "8 字符" in prompt), \
        f"{scenario} payload prompt 未提示 url ≥8 字符约束"


# ============ [fix10 prove-it] S2 场景专属枚举与必填硬约束 ============

def test_s2_payload_prompt_warns_market_sizing_enums():
    """[fix10] S2 prompt 必须列出 market_sizing.unit / value_basis 枚举值

    现象（trace 20260609-194204-efeba1）：
    LLM 反复在 market_sizing.{tam,sam,som}.{unit, value_basis} 填中文/非枚举值
    （如 unit 填'亿美元'、value_basis 填'调研'），触发 schema 拦截。
    """
    prompt = WRITER_PAYLOAD_PROMPTS["S2"]
    # unit 4 个枚举值
    for v in ["billion", "million", "thousand", "raw"]:
        assert v in prompt, f"S2 prompt 缺 market_sizing.unit 枚举 {v}"
    # value_basis 4 个枚举值
    for v in ["measured", "estimated", "inferred", "unknown"]:
        assert v in prompt, f"S2 prompt 缺 market_sizing.value_basis 枚举 {v}"


def test_s2_payload_prompt_warns_consumer_segment_required_fields():
    """[fix10] S2 prompt 必须警告 consumer_segments 的 key_needs + addressability 必填"""
    prompt = WRITER_PAYLOAD_PROMPTS["S2"]
    assert "key_needs" in prompt, "S2 prompt 缺 consumer_segments.key_needs 必填提示"
    assert "addressability" in prompt, "S2 prompt 缺 consumer_segments.addressability 必填提示"
    # addressability 枚举
    for v in ["easy", "moderate", "hard"]:
        assert v in prompt, f"S2 prompt 缺 addressability 枚举 {v}"


def test_s2_payload_prompt_warns_five_forces_intensity_enum():
    """[fix10] S2 prompt 必须列出 five_forces.{*}.intensity 三档枚举"""
    prompt = WRITER_PAYLOAD_PROMPTS["S2"]
    # intensity / likelihood / impact 共用 low/medium/high
    for v in ["low", "medium", "high"]:
        assert v in prompt, f"S2 prompt 缺 intensity/likelihood/impact 枚举 {v}"


def test_s2_payload_prompt_warns_market_concentration_enum():
    """[fix10] S2 prompt 必须列出 market_concentration 枚举"""
    prompt = WRITER_PAYLOAD_PROMPTS["S2"]
    for v in ["fragmented", "moderate", "concentrated"]:
        assert v in prompt, f"S2 prompt 缺 market_concentration 枚举 {v}"


# ============ [fix14 prove-it] S3 prompt 枚举值与 schema 一致 ============

def test_s3_payload_prompt_uses_correct_arr_uplift_basis_enum():
    """[fix14] S3 prompt 里的 expected_arr_uplift_basis 枚举必须和 schema 一致

    现象：之前 prompt 写 elasticity_model / internal_estimate / unknown，
    但 schema 是 measured_pilot / competitor_benchmark / industry_estimate / llm_inferred，
    LLM 按 prompt 填值必撞 ValidationError。
    """
    prompt = WRITER_PAYLOAD_PROMPTS["S3"]
    # schema 真实枚举值必须出现
    for v in ["measured_pilot", "competitor_benchmark", "industry_estimate", "llm_inferred"]:
        assert v in prompt, f"S3 prompt 缺 expected_arr_uplift_basis 枚举 {v}"
    # 错误旧枚举值仅可出现在"禁止"上下文里（提醒 LLM 不要用），不能作为正面定义
    # 检查是否仍把它当成合法枚举宣告（如 `: "elasticity_model" |`）
    for bad in ["elasticity_model", "internal_estimate"]:
        # 如果错枚举出现在 prompt 里，必须在 "禁止" / "不要" 等否定语境内
        if bad in prompt:
            idx = prompt.find(bad)
            ctx = prompt[max(0, idx - 30):idx]
            assert any(neg in ctx for neg in ["禁止", "不要", "不能", "不可"]), \
                f"S3 prompt 残留错误枚举 {bad}（不在禁止上下文里）"


def test_s3_payload_prompt_warns_packaging_position_enum():
    """[fix14] S3 prompt 必须列 RecommendedPriceTier.position 枚举"""
    prompt = WRITER_PAYLOAD_PROMPTS["S3"]
    for v in ["good", "better", "best", "enterprise", "free"]:
        assert v in prompt, f"S3 prompt 缺 packaging.tiers.position 枚举 {v}"


def test_s3_payload_prompt_warns_pricing_page_audit_rules():
    """[fix14] S3 prompt 应列 PricingPageAuditScore.rule_name 8 个枚举（高频踩坑）"""
    prompt = WRITER_PAYLOAD_PROMPTS["S3"]
    # 至少列出关键 4 个，让 LLM 知道是固定枚举不能瞎写
    expected = ["tier_naming_buyer_centric", "anchor_pricing_middle_tier",
                "annual_billing_default", "feature_gating_clear"]
    hits = sum(1 for v in expected if v in prompt)
    assert hits >= 3, f"S3 prompt rule_name 枚举命中 {hits}/{len(expected)}，需要 ≥3"


# ============ [fix15 prove-it] S4 / S5 prompt 补遗漏枚举 ============

def test_s4_payload_prompt_lists_opportunity_effort_impact_enum():
    """[fix15] S4 prompt 必须列 MonitoringOpportunity.estimated_effort / expected_impact 枚举"""
    prompt = WRITER_PAYLOAD_PROMPTS["S4"]
    # estimated_effort + expected_impact 都是 low/medium/high
    # prompt 必须显式提到这两个字段是枚举值（避免 LLM 填中文）
    assert "estimated_effort" in prompt and "expected_impact" in prompt
    # 寻找 estimated_effort 上下文，验证含枚举说明
    idx = prompt.find("estimated_effort")
    ctx = prompt[idx:idx + 200]
    assert "low" in ctx and "medium" in ctx and "high" in ctx, \
        f"S4 prompt estimated_effort 上下文缺 low/medium/high 枚举说明：{ctx[:120]}"


def test_s5_payload_prompt_lists_whitespace_quadrant_enum():
    """[fix15] S5 prompt 必须列 WhiteSpaceZone.quadrant 5 个枚举"""
    prompt = WRITER_PAYLOAD_PROMPTS["S5"]
    for v in ["top_right", "top_left", "bottom_right", "bottom_left", "center"]:
        assert v in prompt, f"S5 prompt 缺 WhiteSpaceZone.quadrant 枚举 {v}"


# ============ [fix17 prove-it] S4 prompt threats/opportunities/battlecards 显式提示 artifact_id ============

def test_s5_payload_prompt_has_pitfall_checklist():
    """[fix19] S5 prompt 末尾必须有 S5 专属「高频踩坑」清单（仿 S2/S3）

    现象（trace 20260609-234227-a836e1）：
    LLM 在 vendor_profiles 的 strengths 数量 / cautions point 字数 /
    perceptual_map 轴标签长度等多处反复栽，2 次 writer 都 max_retries 强制结束。
    需要在 prompt 末尾把这些密集约束再强调一遍。
    """
    prompt = WRITER_PAYLOAD_PROMPTS["S5"]
    # S5 专属高频踩坑标志（区分 SCHEMA_FIELD_CONSTRAINTS 通用块里的 S1 专属段）
    assert "S5 高频踩坑" in prompt or "S5 枚举速查" in prompt, \
        "S5 prompt 末尾应有 S5 专属高频踩坑清单（参考 S2/S3）"
    # 关键约束必须出现：vendor_profiles strengths 2-5 + cautions 1-4
    assert "2-5" in prompt and "1-4" in prompt, \
        "S5 prompt 缺 strengths 2-5 / cautions 1-4 的数量约束"
    # perceptual_map 轴标签 ≥2 字符约束
    assert "low_label" in prompt and "high_label" in prompt, \
        "S5 prompt 应提示轴标签必须 ≥2 字符"


def test_s5_payload_prompt_marks_category_strategy_as_required():
    """[fix18] S5 schema 中 category_strategy 是必填非 Optional，prompt 也必须明确必填。

    现象（trace 20260609-234227-a836e1）：
    prompt 写 "category_strategy: CategoryStrategy Optional"，但 schema 是必填
    → LLM 漏填或填 null → ValidationError category_strategy.chosen_category 等 missing。
    """
    prompt = WRITER_PAYLOAD_PROMPTS["S5"]
    # 必须出现 category_strategy 必填提示
    idx = prompt.find("category_strategy")
    assert idx >= 0, "S5 prompt 没找到 category_strategy"
    ctx = prompt[idx:idx + 200]
    # 不应标 "Optional"，应明确"必填"
    assert "Optional" not in ctx[:60], \
        f"S5 prompt category_strategy 段落不应标 Optional：{ctx[:120]}"
    assert ("必填" in ctx) or ("required" in ctx.lower()), \
        f"S5 prompt category_strategy 应明确必填：{ctx[:200]}"
    # 必填子字段也要列
    for sub in ["chosen_category", "why_this_category"]:
        assert sub in ctx, f"S5 prompt category_strategy 段落缺子字段 {sub}"


@pytest.mark.parametrize("section", ["threats", "opportunities", "battlecards"])
def test_s4_payload_prompt_warns_artifact_id_for_artifact_sections(section):
    """[fix17] S4 prompt 必须在 threats / opportunities / battlecards 段落里
    明确提示 artifact_id 必填，否则 LLM 反复漏写撞 ValidationError。

    现象（trace 20260609-222633-281b59）：
    threats[0/1].artifact_id / opportunities[0/1].artifact_id /
    battlecards[0/1].artifact_id 反复 missing。
    """
    prompt = WRITER_PAYLOAD_PROMPTS["S4"]
    # 找到该 section 描述区块（段落起首），验证后续 200 字符内含 artifact_id
    idx = prompt.find(section)
    assert idx >= 0, f"S4 prompt 没找到 {section} 段落"
    ctx = prompt[idx:idx + 400]
    assert "artifact_id" in ctx, \
        f"S4 prompt {section} 段落未提示 artifact_id 必填"
