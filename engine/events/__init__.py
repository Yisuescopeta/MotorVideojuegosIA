"""
engine/events/__init__.py - Sistema de eventos y reglas
 
PROPÓSITO:
    Módulo de eventos para comunicación desacoplada entre sistemas.
    Incluye EventBus y RuleSystem para reglas declarativas.
"""
 
from engine.events.callable_resolver import CallableResolver, CallableResolverContext
from engine.events.deferred_queue import DeferredCall, DeferredCallQueue
from engine.events.event_bus import Event, EventBus
from engine.events.rule_system import RuleSystem
from engine.events.signals import SignalConnection, SignalConnectionFlags, SignalRef, SignalRuntime
 
__all__ = [
    "CallableResolver",
    "CallableResolverContext",
    "DeferredCall",
    "DeferredCallQueue",
    "EventBus",
    "Event",
    "RuleSystem",
    "SignalConnection",
    "SignalConnectionFlags",
    "SignalRef",
    "SignalRuntime",
]
