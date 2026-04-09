"""
engine/systems/animator_controller_system.py - Seleccion de estados para Animator.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Optional

from engine.components.animator import Animator
from engine.components.animator_controller import AnimatorController

if TYPE_CHECKING:
    from engine.ecs.entity import Entity
    from engine.ecs.world import World
    from engine.events.event_bus import EventBus


class AnimatorControllerSystem:
    """Evalua AnimatorController y sincroniza el clip activo en Animator."""

    def __init__(self, event_bus: Optional["EventBus"] = None) -> None:
        self._event_bus = event_bus

    def set_event_bus(self, event_bus: "EventBus") -> None:
        self._event_bus = event_bus

    def update(self, world: "World", delta_time: float) -> None:
        for entity in world.get_entities_with(Animator, AnimatorController):
            animator = entity.get_component(Animator)
            controller = entity.get_component(AnimatorController)
            if animator is None or controller is None or not controller.enabled:
                continue
            controller.ensure_runtime_parameters()
            active_state = self._ensure_active_state(entity, animator, controller)
            if not active_state:
                continue
            controller.time_in_state = max(0.0, float(controller.time_in_state)) + max(0.0, float(delta_time))
            transition = self._select_transition(controller, animator)
            if transition is not None:
                self._apply_transition(entity, animator, controller, transition)
            else:
                self._sync_animator_to_controller(entity, animator, controller, controller.active_state, force_restart=False)

    def _ensure_active_state(self, entity: "Entity", animator: Animator, controller: AnimatorController) -> str:
        active_state = str(controller.active_state or "").strip()
        if active_state in controller.states:
            if self._sync_animator_to_controller(entity, animator, controller, active_state, force_restart=False):
                return active_state

        candidate = self._resolve_initial_state(animator, controller)
        if not candidate:
            return ""
        if not self._sync_animator_to_controller(entity, animator, controller, candidate, force_restart=False):
            return ""
        controller.previous_state = ""
        controller.active_state = candidate
        controller.time_in_state = 0.0
        controller.last_transition_id = ""
        self._emit_state_events(entity, controller.get_state_payload(candidate), "enter_events")
        return candidate

    def _resolve_initial_state(self, animator: Animator, controller: AnimatorController) -> str:
        preferred = str(controller.entry_state or "").strip()
        if preferred and preferred in controller.states:
            return preferred
        if animator.default_state in controller.states:
            return str(animator.default_state)
        if animator.current_state:
            for state_name in controller.states:
                if controller.get_state_animation(state_name) == animator.current_state:
                    return str(state_name)
        return next(iter(controller.states.keys()), "")

    def _select_transition(self, controller: AnimatorController, animator: Animator) -> dict[str, Any] | None:
        active_state = str(controller.active_state or "").strip()
        any_state_transitions: list[dict[str, Any]] = []
        local_transitions: list[dict[str, Any]] = []
        for transition in controller.transitions:
            if not isinstance(transition, dict) or not bool(transition.get("enabled", True)):
                continue
            if bool(transition.get("from_any_state", False)):
                any_state_transitions.append(transition)
            elif str(transition.get("from_state", "") or "").strip() == active_state:
                local_transitions.append(transition)
        for transition in any_state_transitions + local_transitions:
            if self._transition_can_fire(controller, animator, transition):
                return transition
        return None

    def _transition_can_fire(
        self,
        controller: AnimatorController,
        animator: Animator,
        transition: dict[str, Any],
    ) -> bool:
        to_state = str(transition.get("to_state", "") or "").strip()
        if to_state not in controller.states:
            return False
        if bool(transition.get("has_exit_time", False)):
            exit_time = max(0.0, min(1.0, float(transition.get("exit_time", 1.0) or 0.0)))
            if float(animator.normalized_time) < exit_time:
                return False
        conditions = transition.get("conditions", [])
        if not isinstance(conditions, list):
            return False
        return all(self._condition_matches(controller, condition) for condition in conditions if isinstance(condition, dict))

    def _condition_matches(self, controller: AnimatorController, condition: dict[str, Any]) -> bool:
        parameter_name = str(condition.get("parameter", "") or "").strip()
        if not parameter_name or not controller.has_parameter(parameter_name):
            return False
        parameter_type = controller.get_parameter_type(parameter_name)
        op = str(condition.get("op", "") or "").strip().lower()
        value = controller.get_parameter_value(parameter_name)
        if parameter_type == "bool":
            if op == "is_true":
                return bool(value) is True
            if op == "is_false":
                return bool(value) is False
            return False
        if parameter_type == "trigger":
            return op == "is_set" and bool(value) is True
        expected = condition.get("value", 0)
        if parameter_type == "int":
            current = int(value)
            target = int(expected)
        else:
            current = float(value)
            target = float(expected)
        if op == "equals":
            return current == target
        if op == "not_equals":
            return current != target
        if op == "greater":
            return current > target
        if op == "greater_or_equal":
            return current >= target
        if op == "less":
            return current < target
        if op == "less_or_equal":
            return current <= target
        return False

    def _apply_transition(
        self,
        entity: "Entity",
        animator: Animator,
        controller: AnimatorController,
        transition: dict[str, Any],
    ) -> None:
        to_state = str(transition.get("to_state", "") or "").strip()
        if to_state not in controller.states:
            return
        current_state = str(controller.active_state or "").strip()
        next_state_payload = controller.get_state_payload(to_state)
        if next_state_payload is None:
            return
        if not self._sync_animator_to_controller(
            entity,
            animator,
            controller,
            to_state,
            force_restart=bool(transition.get("force_restart", False)) or current_state == to_state,
        ):
            return

        current_payload = controller.get_state_payload(current_state)
        self._emit_state_events(entity, current_payload, "exit_events")
        self._emit_declared_events(entity, transition.get("events", []))
        controller.previous_state = current_state
        controller.active_state = to_state
        controller.time_in_state = 0.0
        controller.last_transition_id = str(transition.get("id", "") or "")
        self._emit_state_events(entity, next_state_payload, "enter_events")
        controller.consume_triggers(self._transition_trigger_parameters(controller, transition))

    def _transition_trigger_parameters(
        self,
        controller: AnimatorController,
        transition: dict[str, Any],
    ) -> list[str]:
        names: list[str] = []
        for condition in transition.get("conditions", []):
            if not isinstance(condition, dict):
                continue
            parameter_name = str(condition.get("parameter", "") or "").strip()
            if not parameter_name:
                continue
            if controller.get_parameter_type(parameter_name) == "trigger" and str(condition.get("op", "") or "").strip().lower() == "is_set":
                names.append(parameter_name)
        return names

    def _sync_animator_to_controller(
        self,
        entity: "Entity",
        animator: Animator,
        controller: AnimatorController,
        state_name: str,
        *,
        force_restart: bool,
    ) -> bool:
        animation_state = controller.get_state_animation(state_name)
        if not animation_state:
            print(
                f"[WARNING] AnimatorControllerSystem: state '{state_name}' in entity '{entity.name}' has no animation_state"
            )
            return False
        if animation_state not in animator.animations:
            print(
                f"[WARNING] AnimatorControllerSystem: animation_state '{animation_state}' not found in Animator for entity '{entity.name}'"
            )
            return False
        animator.play(animation_state, force_restart=force_restart or animator.current_state != animation_state)
        return True

    def _emit_state_events(self, entity: "Entity", state_payload: dict[str, Any] | None, key: str) -> None:
        if state_payload is None:
            return
        self._emit_declared_events(entity, state_payload.get(key, []))

    def _emit_declared_events(self, entity: "Entity", events: Any) -> None:
        if self._event_bus is None or not isinstance(events, list):
            return
        for event_payload in events:
            if not isinstance(event_payload, dict):
                continue
            event_name = str(event_payload.get("name", "") or "").strip()
            if not event_name:
                continue
            data = event_payload.get("data", {})
            serialized = dict(data) if isinstance(data, dict) else {}
            serialized.setdefault("entity", entity.name)
            serialized.setdefault("entity_id", entity.id)
            self._event_bus.emit(event_name, serialized)
