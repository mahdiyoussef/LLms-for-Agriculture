"""Ten safe-by-default agriculture decision-support agents.

The agents intentionally keep calculations deterministic. An LLM or RAG provider
can be added around these results for explanation without delegating numeric
decisions or safety gates to a model.
"""

from __future__ import annotations

from typing import Any

from .base import AgentEvidence, AgentRequest, AgentResponse
from .services import irrigation_need_mm, net_market_revenue, nutrient_deficit


def _evidence(request: AgentRequest, excerpt: str) -> tuple[AgentEvidence, ...]:
    return (AgentEvidence("request-context", excerpt, 0.7),)


class CropDiseaseAgent:
    name = "crop-disease"

    def run(self, request: AgentRequest) -> AgentResponse:
        symptoms = str(request.context.get("symptoms", "")).strip()
        crop = request.context.get("crop", "the reported crop")
        if not symptoms:
            return AgentResponse(self.name, "More symptom details are required.", warnings=("Add symptoms, growth stage, and a photo if available.",))
        return AgentResponse(
            self.name,
            f"Potential disease assessment for {crop}: treat this as a hypothesis until an agronomist confirms it.",
            ("Record symptom progression", "Inspect nearby plants", "Consult an agronomist before applying treatment"),
            _evidence(request, symptoms),
            ("Do not apply pesticide based on this preliminary assessment.",),
            0.55,
            True,
        )


class IrrigationAgent:
    name = "irrigation"

    def run(self, request: AgentRequest) -> AgentResponse:
        ctx = request.context
        depth = irrigation_need_mm(
            float(ctx.get("evapotranspiration_mm", 0)),
            float(ctx.get("rainfall_mm", 0)),
            float(ctx.get("crop_coefficient", 1.0)),
            float(ctx.get("efficiency", 0.8)),
        )
        return AgentResponse(
            self.name,
            f"Estimated irrigation requirement is {depth} mm for the supplied period.",
            (f"Schedule up to {depth} mm after checking field moisture.",),
            _evidence(request, "evapotranspiration, rainfall, crop coefficient, and efficiency"),
            ("Confirm soil-moisture sensor health before irrigating.",),
            0.8,
            True,
        )


class PestMonitoringAgent:
    name = "pest-monitoring"

    def run(self, request: AgentRequest) -> AgentResponse:
        count = float(request.context.get("trap_count", 0))
        previous = float(request.context.get("previous_trap_count", 0))
        risk = "high" if count > max(10.0, previous * 1.5) else "moderate" if count > previous else "low"
        return AgentResponse(
            self.name,
            f"Pest monitoring risk is {risk}.",
            ("Increase scouting frequency." if risk != "low" else "Continue routine scouting",),
            _evidence(request, f"current trap count={count}, previous={previous}"),
            ("Use integrated pest management and confirm species before treatment.",),
            0.75,
            risk == "high",
        )


class SoilHealthAgent:
    name = "soil-health"

    def run(self, request: AgentRequest) -> AgentResponse:
        ctx = request.context
        deficit = nutrient_deficit(float(ctx.get("nitrogen_required", 0)), float(ctx.get("nitrogen_available", 0)))
        return AgentResponse(
            self.name,
            f"Estimated nitrogen deficit is {deficit} in the supplied units.",
            ("Review a split-application plan." if deficit else "No nitrogen deficit was calculated",),
            _evidence(request, "soil laboratory values and crop requirement"),
            ("Validate units and local fertilizer regulations before application.",),
            0.8,
            bool(deficit),
        )


class CropPlanningAgent:
    name = "crop-planning"

    def run(self, request: AgentRequest) -> AgentResponse:
        previous = str(request.context.get("previous_crop", "")).strip()
        crop = str(request.context.get("candidate_crop", "")).strip()
        answer = f"Review {crop or 'candidate crops'} against rotation constraints."
        if previous and crop and previous.lower() == crop.lower():
            answer = "Avoid repeating the same crop without a documented disease and soil-health assessment."
        return AgentResponse(self.name, answer, ("Compare water, soil, disease-break, and labor constraints.",), _evidence(request, f"previous crop={previous or 'unknown'}"), (), 0.65, False)


class ClimateRiskAgent:
    name = "climate-risk"

    def run(self, request: AgentRequest) -> AgentResponse:
        ctx = request.context
        temperature = float(ctx.get("temperature_c", 20))
        frost = temperature <= float(ctx.get("frost_threshold_c", 0))
        heat = temperature >= float(ctx.get("heat_threshold_c", 35))
        risk = "frost" if frost else "heat stress" if heat else "low"
        return AgentResponse(self.name, f"Current climate risk is {risk}.", ("Activate approved crop protection measures." if risk != "low" else "Continue normal monitoring",), _evidence(request, f"temperature={temperature} C"), ("Forecasts are advisory and can change.",), 0.8, risk != "low")


class MarketIntelligenceAgent:
    name = "market-intelligence"

    def run(self, request: AgentRequest) -> AgentResponse:
        ctx = request.context
        revenue = net_market_revenue(float(ctx.get("quantity", 0)), float(ctx.get("price", 0)), float(ctx.get("costs", 0)))
        return AgentResponse(self.name, f"Estimated net revenue is {revenue}.", ("Compare at least two buyers and account for storage loss.",), _evidence(request, "quantity, price, and costs supplied by the caller"), ("This is an estimate, not a guaranteed price.",), 0.7, False)


class TraceabilityAgent:
    name = "traceability"

    def run(self, request: AgentRequest) -> AgentResponse:
        events = request.context.get("events", [])
        missing = not isinstance(events, list) or not events
        return AgentResponse(self.name, "The batch timeline is incomplete." if missing else f"The batch contains {len(events)} recorded events.", ("Add immutable timestamps and source IDs for missing events.",) if missing else ("Review the timeline for conflicting events.",), _evidence(request, "batch event list"), ("Do not overwrite historical traceability events.",), 0.8 if not missing else 0.4, missing)


class ExtensionAgent:
    name = "extension"

    def run(self, request: AgentRequest) -> AgentResponse:
        return AgentResponse(self.name, "Use the retrieved extension guidance as a starting point and adapt it to local conditions.", ("Share crop, region, growth stage, and constraints for a localized answer.",), _evidence(request, request.question), ("Verify recommendations with a local extension professional for high-impact decisions.",), 0.6, False)


class FarmCopilotAgent:
    name = "farm-copilot"

    def __init__(self, specialists: tuple[Any, ...] = ()):
        self.specialists = specialists

    def run(self, request: AgentRequest) -> AgentResponse:
        if not self.specialists:
            return AgentResponse(self.name, "No specialist agents are configured.", warnings=("Configure specialist agents before using the farm copilot.",), requires_confirmation=True)
        results = [agent.run(request) for agent in self.specialists]
        warnings = tuple(warning for result in results for warning in result.warnings)
        actions = tuple(action for result in results for action in result.actions)
        confidence = round(sum(result.confidence for result in results) / len(results), 2)
        return AgentResponse(self.name, f"Collected {len(results)} specialist assessments.", actions, tuple(item for result in results for item in result.evidence), warnings, confidence, any(result.requires_confirmation for result in results))
