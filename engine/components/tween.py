"""
engine/components/tween.py - Componente de interpolacion de propiedades (Tween).

Soporta 11 transiciones Godot-style, 4 modos ease, multiples steps,
encadenamiento, paralelismo y nesting.
"""

from __future__ import annotations

import dataclasses
from enum import Enum
from typing import Any

from engine.ecs.component import Component


class TweenTransition(Enum):
    LINEAR = "linear"
    SINE = "sine"
    QUINT = "quint"
    QUART = "quart"
    QUAD = "quad"
    EXPO = "expo"
    ELASTIC = "elastic"
    CUBIC = "cubic"
    CIRC = "circ"
    BOUNCE = "bounce"
    BACK = "back"
    SPRING = "spring"


class TweenEase(Enum):
    EASE_IN = "ease_in"
    EASE_OUT = "ease_out"
    EASE_IN_OUT = "ease_in_out"
    EASE_OUT_IN = "ease_out_in"


LEGACY_TRANSITION_SET: frozenset[str] = frozenset(
    [
        "linear",
        "sine_in",
        "sine_out",
        "sine_in_out",
        "quad_in",
        "quad_out",
        "quad_in_out",
        "cubic_in",
        "cubic_out",
        "cubic_in_out",
        "expo_in",
        "expo_out",
        "expo_in_out",
    ]
)


@dataclasses.dataclass
class TweenStep:
    """Operacion individual de tween sobre una propiedad."""

    target_entity: str = ""
    target_component: str = ""
    property_path: str = ""
    from_value: float = 0.0
    to_value: float = 0.0
    duration: float = 1.0
    delay: float = 0.0
    transition: TweenTransition = TweenTransition.LINEAR
    ease: TweenEase = TweenEase.EASE_IN_OUT
    # Runtime state
    elapsed: float = 0.0
    started: bool = False
    completed: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "target_entity": self.target_entity,
            "target_component": self.target_component,
            "property_path": self.property_path,
            "from_value": self.from_value,
            "to_value": self.to_value,
            "duration": self.duration,
            "delay": self.delay,
            "transition": self.transition.value,
            "ease": self.ease.value,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TweenStep":
        transition = TweenTransition(data.get("transition", "linear"))
        ease = TweenEase(data.get("ease", "ease_in_out"))
        return cls(
            target_entity=str(data.get("target_entity", "")),
            target_component=str(data.get("target_component", "")),
            property_path=str(data.get("property_path", "")),
            from_value=float(data.get("from_value", 0.0)),
            to_value=float(data.get("to_value", 1.0)),
            duration=float(data.get("duration", 1.0)),
            delay=float(data.get("delay", 0.0)),
            transition=transition,
            ease=ease,
        )


class Tween(Component):
    """Godot-style Tween: soporta multiples steps, encadenamiento, paralelismo."""

    def __init__(
        self,
        enabled: bool = True,
        property_path: str = "",
        from_value: float = 0.0,
        to_value: float = 1.0,
        duration: float = 1.0,
        autostart: bool = False,
        one_shot: bool = True,
        transition: str = "linear",
    ) -> None:
        self.enabled: bool = enabled
        self.steps: list[TweenStep] = []
        self.loops: int = 0  # 0 = sin loop, -1 = infinito, N = N repeticiones
        self.loop_count: int = 0
        self.parallel: bool = False
        self.running: bool = False
        self.paused: bool = False
        self.speed_scale: float = 1.0
        self.default_transition: TweenTransition = TweenTransition.LINEAR
        self.default_ease: TweenEase = TweenEase.EASE_IN_OUT
        self.autostart: bool = bool(autostart)
        self.one_shot: bool = bool(one_shot)
        self._runtime_steps: list[TweenStep] = []
        self._next_step_batch: int = 0
        self._has_autostarted: bool = False

        # Backward compat: if old-style params given, create a single step
        if property_path.strip() or transition != "linear":
            legacy_trans = self._coerce_transition(transition)
            legacy_ease = self._infer_ease_from_legacy(transition)
            step = TweenStep(
                target_entity="",
                target_component="",
                property_path=str(property_path or "").strip(),
                from_value=float(from_value),
                to_value=float(to_value),
                duration=max(0.001, float(duration)),
                delay=0.0,
                transition=legacy_trans,
                ease=legacy_ease,
            )
            self.steps.append(step)

    # --- Legacy backward-compat properties ---

    @property
    def property_path(self) -> str:
        if self.steps:
            return self.steps[0].property_path
        return ""

    @property
    def from_value(self) -> float:
        if self.steps:
            return self.steps[0].from_value
        return 0.0

    @property
    def to_value(self) -> float:
        if self.steps:
            return self.steps[0].to_value
        return 1.0

    @property
    def duration(self) -> float:
        if self.steps:
            return self.steps[0].duration
        return 1.0

    @property
    def transition(self) -> str:
        if self.steps:
            return self.steps[0].transition.value
        return "linear"

    @property
    def is_running(self) -> bool:
        return self.running

    @property
    def is_finished(self) -> bool:
        step = self.steps[0] if self.steps else None
        if step is not None:
            return step.completed
        return not self.running

    @property
    def progress(self) -> float:
        step = self.steps[0] if self.steps else None
        if step is None or step.duration <= 0:
            return 1.0
        return min(1.0, step.elapsed / step.duration)

    @progress.setter
    def progress(self, value: float) -> None:
        pass

    # Legacy runtime attrs for backward compat
    @property
    def _elapsed(self) -> float:
        step = self.steps[0] if self.steps else None
        return step.elapsed if step else 0.0

    @_elapsed.setter
    def _elapsed(self, value: float) -> None:
        if self.steps:
            self.steps[0].elapsed = value

    @property
    def _is_running(self) -> bool:
        return self.running

    @_is_running.setter
    def _is_running(self, value: bool) -> None:
        self.running = value

    @property
    def _is_finished(self) -> bool:
        return self.is_finished

    @_is_finished.setter
    def _is_finished(self, value: bool) -> None:
        if self.steps:
            self.steps[0].completed = value
        if value:
            self.running = False

    @staticmethod
    def _coerce_transition(value: Any) -> TweenTransition:
        normalized = str(value or "linear").strip().lower()
        if normalized in LEGACY_TRANSITION_SET:
            # Extract base transition
            for base in ["sine", "quad", "cubic", "expo"]:
                if normalized.startswith(base):
                    return TweenTransition(base)
            return TweenTransition.LINEAR
        try:
            return TweenTransition(normalized)
        except ValueError:
            return TweenTransition.LINEAR

    @staticmethod
    def _infer_ease_from_legacy(transition: str) -> TweenEase:
        normalized = str(transition or "linear").strip().lower()
        if normalized.endswith("_in_out"):
            return TweenEase.EASE_IN_OUT
        elif normalized.endswith("_out"):
            return TweenEase.EASE_OUT
        elif normalized.endswith("_in"):
            return TweenEase.EASE_IN
        return TweenEase.EASE_IN_OUT

    # --- Builder methods (fluent API) ---

    def tween_property(
        self,
        target_entity: str,
        target_component: str,
        property_path: str,
        to_value: float,
        duration: float,
    ) -> TweenStep:
        """Crea un step de tween de propiedad y lo agrega a la lista."""
        step = TweenStep(
            target_entity=target_entity,
            target_component=target_component,
            property_path=property_path,
            to_value=to_value,
            duration=max(0.001, float(duration)),
            transition=self.default_transition,
            ease=self.default_ease,
        )
        self.steps.append(step)
        return step

    def chain(self) -> Tween:
        """El siguiente tween se ejecuta despues de que el anterior termine."""
        self.parallel = False
        return self

    def set_parallel(self, parallel: bool = True) -> Tween:
        """Establece si los siguientes tweens corren en paralelo."""
        self.parallel = parallel
        return self

    def set_loops(self, count: int = 0) -> Tween:
        """Define cuantas veces repetir. 0 = una vez, -1 = infinito."""
        self.loops = count
        return self

    def set_trans(self, transition: str | TweenTransition) -> Tween:
        """Establece transicion para el ultimo step agregado."""
        if self.steps:
            if isinstance(transition, TweenTransition):
                self.steps[-1].transition = transition
            else:
                try:
                    self.steps[-1].transition = TweenTransition(str(transition).strip().lower())
                except ValueError:
                    self.steps[-1].transition = TweenTransition.LINEAR
        return self

    def set_ease(self, ease: str | TweenEase) -> Tween:
        """Establece ease para el ultimo step agregado."""
        if self.steps:
            if isinstance(ease, TweenEase):
                self.steps[-1].ease = ease
            else:
                try:
                    self.steps[-1].ease = TweenEase(str(ease).strip().lower())
                except ValueError:
                    self.steps[-1].ease = TweenEase.EASE_IN_OUT
        return self

    def set_delay(self, delay: float) -> Tween:
        """Establece delay para el ultimo step agregado."""
        if self.steps:
            self.steps[-1].delay = float(delay)
        return self

    def set_from(self, from_value: float) -> Tween:
        """Establece valor inicial para el ultimo step agregado."""
        if self.steps:
            # Sample current value from target component at play time
            self.steps[-1].from_value = float(from_value)
        return self

    # --- Control methods ---

    def start(self) -> None:
        """Inicia la reproduccion del tween."""
        self.running = True
        self.paused = False
        self._runtime_steps = []
        self._next_step_batch = 0
        self.loop_count = 0

    def stop(self) -> None:
        """Detiene la reproduccion."""
        self.running = False
        self.paused = False

    def pause(self) -> None:
        """Pausa la reproduccion."""
        self.paused = True

    def resume(self) -> None:
        """Reanuda la reproduccion."""
        self.paused = False

    def kill(self) -> None:
        """Detiene y limpia los steps de runtime."""
        self.running = False
        self.paused = False
        self._runtime_steps.clear()

    # --- Serialization ---

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "steps": [s.to_dict() for s in self.steps],
            "loops": self.loops,
            "parallel": self.parallel,
            "running": self.running,
            "paused": self.paused,
            "speed_scale": self.speed_scale,
            "default_transition": self.default_transition.value,
            "default_ease": self.default_ease.value,
            "autostart": self.autostart,
            "one_shot": self.one_shot,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Tween":
        component = cls.__new__(cls)
        Component.__init__(component)  # type: ignore[misc]
        component.enabled = bool(data.get("enabled", True))
        component._runtime_steps = []
        component._next_step_batch = 0
        component._has_autostarted = False
        component.loop_count = 0

        # Detect legacy format (has property_path, no steps)
        if "steps" not in data and "property_path" in data:
            component.steps = cls._convert_legacy_to_steps(data)
        else:
            component.steps = [
                TweenStep.from_dict(s) for s in data.get("steps", [])
            ]

        component.loops = int(data.get("loops", 0))
        component.parallel = bool(data.get("parallel", False))
        component.running = bool(data.get("running", False))
        component.paused = bool(data.get("paused", False))
        component.speed_scale = float(data.get("speed_scale", 1.0))
        try:
            component.default_transition = TweenTransition(
                str(data.get("default_transition", "linear")).strip().lower()
            )
        except ValueError:
            component.default_transition = TweenTransition.LINEAR
        try:
            component.default_ease = TweenEase(
                str(data.get("default_ease", "ease_in_out")).strip().lower()
            )
        except ValueError:
            component.default_ease = TweenEase.EASE_IN_OUT
        component.autostart = bool(data.get("autostart", False))
        component.one_shot = bool(data.get("one_shot", True))
        return component

    @staticmethod
    def _convert_legacy_to_steps(data: dict[str, Any]) -> list[TweenStep]:
        """Convierte el formato legacy de Tween a lista de TweenStep."""
        legacy_trans = str(data.get("transition", "linear")).strip().lower()
        transition = TweenTransition.LINEAR
        ease = TweenEase.EASE_IN_OUT
        for base in ["sine", "quad", "cubic", "expo"]:
            if legacy_trans.startswith(base):
                transition = TweenTransition(base)
                break
        if legacy_trans.endswith("_in_out"):
            ease = TweenEase.EASE_IN_OUT
        elif legacy_trans.endswith("_out"):
            ease = TweenEase.EASE_OUT
        elif legacy_trans.endswith("_in"):
            ease = TweenEase.EASE_IN

        property_path = str(data.get("property_path", ""))
        parts = property_path.split(".") if property_path else []
        component_name = parts[0] if len(parts) >= 1 else ""

        return [TweenStep(
            target_entity="",
            target_component=component_name,
            property_path=property_path,
            from_value=float(data.get("from_value", 0.0)),
            to_value=float(data.get("to_value", 1.0)),
            duration=max(0.001, float(data.get("duration", 1.0))),
            delay=0.0,
            transition=transition,
            ease=ease,
        )]
