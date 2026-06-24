from pydantic import BaseModel, Field, field_validator
from typing import Literal, Any, Optional


class FeedbackIssue(BaseModel):
    """质检发现的单个问题"""
    agent: Literal["collector", "analyzer", "writer", "end"]
    field: str
    severity: Literal["critical", "major", "minor"]
    reason: str
    suggestion: str = ""
    # v4 新增（Optional 兼容旧 trace 反序列化）
    dimension: Optional[Literal["evidence", "specificity", "coherence", "actionability", "programmatic", "critic_failed", "overall"]] = None
    """critic 维度名——用于去重 + 反馈路由"""
    issue_type: Optional[Literal["url_not_discovered", "source_mismatch", "source_irrelevant", "vague_description", "cross_field_contradiction", "vague_recommendation", "critic_failed"]] = None
    """critic issue 类型——用于 _map_issue_type_to_agent 路由"""


class CriticScores(BaseModel):
    """critic 4 维评分（持久化到 ReportMetadata.critic_scores）

    每维 1-4 整数分；reasoning 是 dict[dim, list[bullet]] 结构化短列表（spec v4-M9）。
    """
    evidence: int = Field(ge=1, le=4)
    specificity: int = Field(ge=1, le=4)
    coherence: int = Field(ge=1, le=4)
    actionability: int = Field(ge=1, le=4)
    reasoning: dict[str, list[str]] = Field(default_factory=dict)
    """{dim: [bullet1, bullet2, ...]}，CoT 推理过程（短 bullet，每条 ≤80 Python len 字符）"""

    @field_validator("reasoning", mode="before")
    @classmethod
    def _truncate_reasoning_bullets(cls, v: dict) -> dict:
        """S3：每条 reasoning bullet 截断到 80 字符（不报错，静默截断）。"""
        if not isinstance(v, dict):
            return v
        return {dim: [b[:80] if isinstance(b, str) else b for b in bullets]
                for dim, bullets in v.items()}


class RejectionFeedback(BaseModel):
    """质检 Agent 输出：打回反馈"""
    passed: bool
    issues: list[FeedbackIssue] = Field(default_factory=list)
    retry_count: int = Field(ge=0, default=0)
    max_retries: int = Field(ge=0, default=2)


class AgentMessage(BaseModel):
    """Agent 间消息"""
    from_agent: str
    to_agent: str
    message_type: Literal["task", "result", "feedback", "retry"]
    payload: dict[str, Any] = Field(default_factory=dict)
    timestamp: str
    trace_id: str
