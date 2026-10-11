"""Specialist agents for agricultural decision support."""

from .base import AgentEvidence, AgentRequest, AgentResponse, AgriculturalAgent
from .registry import AgentRegistry, build_default_registry
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

__all__ = [
    "AgentEvidence",
    "AgentRequest",
    "AgentResponse",
    "AgriculturalAgent",
    "AgentRegistry",
    "build_default_registry",
    "ClimateRiskAgent",
    "CropDiseaseAgent",
    "CropPlanningAgent",
    "ExtensionAgent",
    "FarmCopilotAgent",
    "IrrigationAgent",
    "MarketIntelligenceAgent",
    "PestMonitoringAgent",
    "SoilHealthAgent",
    "TraceabilityAgent",
]
