"""engine/ai/ - AI-facing capabilities and registry for OpenGame."""

from engine.ai.capability_registry import (
    Capability,
    CapabilityExample,
    CapabilityParam,
    CapabilityRegistry,
)
from engine.ai.compliance import run_ai_compliance
from engine.ai.registry_builder import (
    CapabilityRegistryBuilder,
    MotorAIBootstrapBuilder,
    get_default_registry,
)

__all__ = [
    "Capability",
    "CapabilityExample",
    "CapabilityParam",
    "CapabilityRegistry",
    "CapabilityRegistryBuilder",
    "MotorAIBootstrapBuilder",
    "get_default_registry",
    "run_ai_compliance",
]
