"""Registry and lookup for agriculture agents."""

from __future__ import annotations

from .base import AgriculturalAgent, AgentRequest, AgentResponse
from .specialists import (
    ClimateRiskAgent,
    CropDiseaseAgent,
    CropPlanningAgent,
    ExtensionAgent,
    FarmCopilotAgent,
    IrrigationAgent,
    MarketIntelligenceAgent,
    PestMonitoringAgent,
    SoilHealthAgent,
    TraceabilityAgent,
)


class AgentRegistry:
    """Case-insensitive registry that prevents unknown agent execution."""

    def __init__(self, agents: tuple[AgriculturalAgent, ...]):
        self._agents = {agent.name: agent for agent in agents}

    def names(self) -> tuple[str, ...]:
        return tuple(sorted(self._agents))

    def get(self, name: str) -> AgriculturalAgent:
        try:
            return self._agents[name.strip().lower()]
        except KeyError as exc:
            raise KeyError(f"Unknown agriculture agent: {name}") from exc

    def run(self, name: str, request: AgentRequest) -> AgentResponse:
        return self.get(name).run(request)


def build_default_registry() -> AgentRegistry:
    """Build all ten supported agents with a coordinating copilot."""
    specialists = (
        CropDiseaseAgent(), IrrigationAgent(), PestMonitoringAgent(), SoilHealthAgent(),
        CropPlanningAgent(), ClimateRiskAgent(), MarketIntelligenceAgent(),
        TraceabilityAgent(), ExtensionAgent(),
    )
    return AgentRegistry(specialists + (FarmCopilotAgent(specialists),))
