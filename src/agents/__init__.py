"""Agent packages.

Weather support is imported lazily so lightweight API and agriculture-agent
imports do not require the optional HTTP weather dependency.
"""

from importlib import import_module
from typing import Any

__all__ = ["WeatherAgent", "WeatherContext", "create_weather_agent"]


def __getattr__(name: str) -> Any:
    if name in __all__:
        module = import_module(".weather_agent", __name__)
        return getattr(module, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
