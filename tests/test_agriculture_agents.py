"""Unit tests for the agriculture agent contracts and deterministic rules."""

from __future__ import annotations

import pytest

from src.agents.agriculture import AgentRequest, build_default_registry
from src.agents.agriculture.services import irrigation_need_mm, net_market_revenue, nutrient_deficit


def request(**context) -> AgentRequest:
    return AgentRequest("user-1", "farm-1", "Provide a farm recommendation", context)


def test_registry_contains_all_ten_agents():
    registry = build_default_registry()
    assert registry.names() == (
        "climate-risk",
        "crop-disease",
        "crop-planning",
        "extension",
        "farm-copilot",
        "irrigation",
        "market-intelligence",
        "pest-monitoring",
        "soil-health",
        "traceability",
    )


@pytest.mark.parametrize(
    ("name", "context"),
    [
        ("crop-disease", {"symptoms": "spotted leaves", "crop": "tomato"}),
        ("irrigation", {"evapotranspiration_mm": 5, "rainfall_mm": 1}),
        ("pest-monitoring", {"trap_count": 12, "previous_trap_count": 4}),
        ("soil-health", {"nitrogen_required": 100, "nitrogen_available": 40}),
        ("crop-planning", {"previous_crop": "maize", "candidate_crop": "beans"}),
        ("climate-risk", {"temperature_c": 38}),
        ("market-intelligence", {"quantity": 10, "price": 5, "costs": 3}),
        ("traceability", {"events": [{"type": "harvest"}]}),
        ("extension", {}),
        ("farm-copilot", {"symptoms": "spots", "evapotranspiration_mm": 2, "rainfall_mm": 0}),
    ],
)
def test_each_agent_returns_explainable_response(name, context):
    result = build_default_registry().run(name, request(**context))
    payload = result.to_dict()
    assert payload["agent_name"] == name
    assert payload["answer"]
    assert 0 <= payload["confidence"] <= 1
    assert isinstance(payload["actions"], list)
    assert isinstance(payload["evidence"], list)


def test_unknown_agent_is_rejected():
    with pytest.raises(KeyError, match="Unknown agriculture agent"):
        build_default_registry().get("does-not-exist")


def test_irrigation_calculation_accounts_for_rain_and_efficiency():
    assert irrigation_need_mm(5, 1, crop_coefficient=1, efficiency=0.8) == 5.0


def test_nutrient_deficit_never_goes_negative():
    assert nutrient_deficit(20, 30) == 0
    assert nutrient_deficit(30, 20) == 10


def test_market_revenue_is_net_of_costs():
    assert net_market_revenue(10, 5, 3) == 47


@pytest.mark.parametrize(
    "calculator,args",
    [
        (irrigation_need_mm, (-1, 0)),
        (nutrient_deficit, (-1, 0)),
        (net_market_revenue, (-1, 2)),
    ],
)
def test_calculators_reject_negative_inputs(calculator, args):
    with pytest.raises(ValueError):
        calculator(*args)
