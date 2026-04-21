from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Callable, Optional

from engine.editor.console_panel import log_warn

if TYPE_CHECKING:
    from engine.ecs.world import World

ResolvedCallable = Callable[..., Any]


@dataclass(frozen=True)
class CallableResolverContext:
    """Dependencias mínimas para resolver destinos runtime de señales."""

    get_world: Callable[[], Optional["World"]]
    get_script_behaviour_system: Callable[[], Any]
    get_event_bus: Callable[[], Any]


class CallableResolver:
    """Resuelve destinos serializables hacia callables runtime seguros."""

    def __init__(self, context: CallableResolverContext) -> None:
        self._get_world = context.get_world
        self._get_script_behaviour_system = context.get_script_behaviour_system
        self._get_event_bus = context.get_event_bus

    def resolve(
        self,
        target: dict[str, Any] | None,
        callable_ref: dict[str, Any] | None = None,
    ) -> ResolvedCallable | None:
        normalized_target = dict(target or {})
        normalized_callable = dict(callable_ref or {})
        kind = str(normalized_target.get("kind", "")).strip().lower()

        if kind == "entity":
            return self._resolve_entity_callable(normalized_target, normalized_callable)
        if kind == "event_bus":
            return self._resolve_event_bus_callable(normalized_target, normalized_callable)
        if kind == "service":
            log_warn("CallableResolver: targets de tipo service aún no están soportados")
            return None

        log_warn(f"CallableResolver: target kind no soportado: {kind or '<vacío>'}")
        return None

    def _resolve_entity_callable(
        self,
        target: dict[str, Any],
        callable_ref: dict[str, Any],
    ) -> ResolvedCallable | None:
        entity_name = str(target.get("name", "")).strip()
        component_name = str(target.get("component", "ScriptBehaviour") or "ScriptBehaviour").strip()
        method_name = str(callable_ref.get("method", "")).strip()

        if not entity_name or not method_name:
            log_warn("CallableResolver: target entity requiere name y callable.method")
            return None
        if component_name != "ScriptBehaviour":
            log_warn(
                "CallableResolver: solo component=ScriptBehaviour está soportado "
                f"por ahora; recibido={component_name}"
            )
            return None

        def invoke(*args: Any, **kwargs: Any) -> bool:
            world = self._get_world()
            if world is None:
                return False
            script_behaviour_system = self._get_script_behaviour_system()
            if script_behaviour_system is None:
                return False
            return bool(script_behaviour_system.invoke_callable(world, entity_name, method_name, *args, **kwargs))

        return invoke

    def _resolve_event_bus_callable(
        self,
        target: dict[str, Any],
        callable_ref: dict[str, Any],
    ) -> ResolvedCallable | None:
        event_name = str(callable_ref.get("event") or target.get("event") or "").strip()
        if not event_name:
            log_warn("CallableResolver: target event_bus requiere callable.event o target.event")
            return None

        def invoke(*args: Any, **kwargs: Any) -> bool:
            event_bus = self._get_event_bus()
            if event_bus is None:
                return False
            event_bus.emit(event_name, self._build_event_payload(args, kwargs))
            return True

        return invoke

    def _build_event_payload(self, args: tuple[Any, ...], kwargs: dict[str, Any]) -> dict[str, Any]:
        if args and isinstance(args[0], dict):
            payload = dict(args[0])
            if len(args) > 1:
                payload["args"] = list(args[1:])
            if kwargs:
                payload.update(kwargs)
            return payload
        if kwargs:
            payload = dict(kwargs)
            if args:
                payload["args"] = list(args)
            return payload
        if not args:
            return {}
        if len(args) == 1:
            return {"value": args[0]}
        return {"args": list(args)}
