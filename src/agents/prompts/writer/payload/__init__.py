"""5 场景 Phase 2 payload prompts。

每个 PAYLOAD_PROMPT 让 LLM 产出该场景的 scenario_payload（S{N}Payload schema）。
约束：
- [v3-R14] 双防护：source_refs 必填的条目（S3 ObservedCompetitorTier / S4 _BaseChange）无来源时不生成
- [C5/v3-R01] evidence_url / SourceRef.url 只能从 profiles_source_urls 列表选
- [v3-R10] S2 competitor_recommendations 字段由代码覆盖，LLM 仅作为只读上下文使用
"""
from src.agents.prompts.writer.payload.s1 import S1_PAYLOAD_PROMPT
from src.agents.prompts.writer.payload.s2 import S2_PAYLOAD_PROMPT
from src.agents.prompts.writer.payload.s3 import S3_PAYLOAD_PROMPT
from src.agents.prompts.writer.payload.s4 import S4_PAYLOAD_PROMPT
from src.agents.prompts.writer.payload.s5 import S5_PAYLOAD_PROMPT
from src.agents.prompts.writer.payload.s5_phase2a import S5_PHASE2A_PROMPT
from src.agents.prompts.writer.payload.s5_phase2b import S5_PHASE2B_PROMPT

WRITER_PAYLOAD_PROMPTS: dict[str, str] = {
    "S1": S1_PAYLOAD_PROMPT,
    "S2": S2_PAYLOAD_PROMPT,
    "S3": S3_PAYLOAD_PROMPT,
    "S4": S4_PAYLOAD_PROMPT,
    "S5": S5_PAYLOAD_PROMPT,
}

# S5 拆分路径专用：phase 2a 数据层 + phase 2b 战略层
S5_SPLIT_PROMPTS: dict[str, str] = {
    "phase2a": S5_PHASE2A_PROMPT,
    "phase2b": S5_PHASE2B_PROMPT,
}

__all__ = ["WRITER_PAYLOAD_PROMPTS", "S5_SPLIT_PROMPTS"]
