"""Contracts shared by all agriculture decision-support agents."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(frozen=True)
class AgentRequest:
    """Normalized input supplied to an agriculture agent."""

    user_id: str
    farm_id: str
    question: str
    context: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AgentEvidence:
    """A traceable fact used by an agent response."""

    source: str
    excerpt: str
    confidence: float


@dataclass(frozen=True)
class AgentResponse:
    """Safe, explainable result returned by an agriculture agent."""

    agent_name: str
    answer: str
    actions: tuple[str, ...] = ()
    evidence: tuple[AgentEvidence, ...] = ()
    warnings: tuple[str, ...] = ()
    confidence: float = 0.0
    requires_confirmation: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Serialize the response for API clients."""
        return {
            "agent_name": self.agent_name,
            "answer": self.answer,
            "actions": list(self.actions),
            "evidence": [
                {
                    "source": item.source,
                    "excerpt": item.excerpt,
                    "confidence": item.confidence,
                }
                for item in self.evidence
            ],
            "warnings": list(self.warnings),
            "confidence": self.confidence,
            "requires_confirmation": self.requires_confirmation,
        }


class AgriculturalAgent(Protocol):
    """Protocol implemented by every specialist agent."""

    name: str

    def run(self, request: AgentRequest) -> AgentResponse:
        """Produce a deterministic, explainable recommendation."""
