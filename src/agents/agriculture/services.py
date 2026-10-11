"""Deterministic calculations used by agriculture agents."""

from __future__ import annotations


def irrigation_need_mm(
    evapotranspiration_mm: float,
    rainfall_mm: float,
    crop_coefficient: float = 1.0,
    efficiency: float = 0.8,
) -> float:
    """Estimate net irrigation depth after rainfall and system losses."""
    if evapotranspiration_mm < 0 or rainfall_mm < 0:
        raise ValueError("weather amounts cannot be negative")
    if crop_coefficient <= 0 or efficiency <= 0 or efficiency > 1:
        raise ValueError("crop coefficient must be positive and efficiency must be in (0, 1]")
    return round(max(0.0, evapotranspiration_mm * crop_coefficient - rainfall_mm) / efficiency, 2)


def nutrient_deficit(required: float, available: float) -> float:
    """Return a non-negative nutrient deficit in the caller's units."""
    if required < 0 or available < 0:
        raise ValueError("nutrient values cannot be negative")
    return round(max(0.0, required - available), 2)


def net_market_revenue(quantity: float, price: float, costs: float = 0.0) -> float:
    """Calculate revenue after explicitly supplied costs."""
    if quantity < 0 or price < 0 or costs < 0:
        raise ValueError("quantity, price, and costs cannot be negative")
    return round(quantity * price - costs, 2)
