"""Public API request and response models."""

from typing import Any

from pydantic import BaseModel, Field


class TokenRequest(BaseModel):
    username: str = Field(min_length=1, max_length=128)
    password: str = Field(min_length=1, max_length=256)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class QueryRequest(BaseModel):
    question: str = Field(min_length=1, max_length=4000)
    top_k: int = Field(default=5, ge=1, le=20)
    use_agent: bool = False
    agent_name: str | None = Field(default=None, max_length=64)


class QueryResponse(BaseModel):
    answer: str
    provider: str
    model: str
    sources: list[str] = Field(default_factory=list)


class AgentRunRequest(BaseModel):
    question: str = Field(min_length=1, max_length=4000)
    farm_id: str = Field(default="default", min_length=1, max_length=128)
    context: dict[str, Any] = Field(default_factory=dict)


class AgentInfo(BaseModel):
    name: str


class AgentRunResponse(BaseModel):
    agent_name: str
    answer: str
    actions: list[str]
    evidence: list[dict[str, Any]]
    warnings: list[str]
    confidence: float
    requires_confirmation: bool


class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=500)
    limit: int = Field(default=5, ge=1, le=10)
