from pydantic import BaseModel, Field
from typing import Literal, Any


class FeedbackIssue(BaseModel):
    """质检发现的单个问题"""
    agent: Literal["collector", "analyzer", "writer"]
    field: str
    severity: Literal["critical", "major", "minor"]
    reason: str
    suggestion: str = ""


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
