"""
engine/events/__init__.py - Sistema de eventos y reglas

PROPÓSITO:
    Módulo de eventos para comunicación desacoplada entre sistemas.
    Incluye EventBus y RuleSystem para reglas declarativas.
"""

from engine.events.event_bus import Event, EventBus
from engine.events.rule_system import RuleSystem

__all__ = [
    "EventBus",
    "Event",
    "RuleSystem",
]
