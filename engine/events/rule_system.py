"""
engine/events/rule_system.py - Sistema de reglas declarativas

PROPÃ“SITO:
    Ejecuta reglas definidas en JSON cuando ocurren eventos.
    Permite definir comportamiento de juego sin cÃ³digo Python.

FORMATO DE REGLA:
    {
        "event": "on_collision",
        "when": {
            "entity_a": "Player",
            "entity_b": "Enemy"
        },
        "do": [
            {"action": "set_animation", "entity": "Player", "state": "hit"},
            {"action": "destroy_entity", "entity": "Enemy"}
        ]
    }

ACCIONES SOPORTADAS:
    - set_animation: Cambia el estado de animaciÃ³n de una entidad
    - set_position: Mueve una entidad a una posiciÃ³n
    - destroy_entity: Elimina una entidad del mundo
    - emit_event: Emite otro evento
    - log_message: Imprime un mensaje en consola

EJEMPLO DE USO:
    rule_system = RuleSystem(event_bus)
    rule_system.set_world(world)
    rule_system.load_rules(rules_list)
"""

from typing import Any, Dict, List, Optional

from engine.components.animator import Animator
from engine.components.animator_controller import AnimatorController
from engine.components.transform import Transform
from engine.ecs.world import World
from engine.events.event_bus import Event, EventBus


class RuleSystem:
    """
    Sistema que ejecuta reglas declarativas basadas en eventos.
    """

    def __init__(self, event_bus: EventBus, world: Optional[World] = None) -> None:
        """
        Inicializa el sistema de reglas.

        Args:
            event_bus: Bus de eventos para suscribirse
            world: Mundo con las entidades. Puede enlazarse mas tarde.
        """
        self._event_bus = event_bus
        self._world = world
        self._rules: List[Dict[str, Any]] = []
        self._rules_executed: int = 0

        # Suscribirse al callback genÃ©rico
        self._subscribed_events: set[str] = set()

    def load_rules(self, rules: List[Dict[str, Any]]) -> None:
        """
        Carga una lista de reglas y suscribe a los eventos necesarios.

        Args:
            rules: Lista de reglas en formato diccionario
        """
        self._rules = rules
        self._rules_executed = 0

        # Obtener eventos Ãºnicos
        events_needed = set()
        for rule in rules:
            event_name = rule.get("event")
            if event_name:
                events_needed.add(event_name)

        # Suscribirse a eventos no suscritos
        for event_name in events_needed:
            if event_name not in self._subscribed_events:
                self._event_bus.subscribe(event_name, self._on_event)
                self._subscribed_events.add(event_name)

        print(f"[INFO] RuleSystem: {len(rules)} reglas cargadas")

    def clear_rules(self) -> None:
        """Limpia todas las reglas."""
        self._rules = []
        self._rules_executed = 0

    def set_world(self, world: Optional[World]) -> None:
        """Actualiza la referencia al mundo."""
        self._world = world

    def _get_world_for_action(self, action_type: str) -> Optional[World]:
        """Devuelve el world actual o reporta que la accion se omite."""
        if self._world is None:
            print(f"[WARNING] RuleSystem: accion '{action_type}' ignorada porque no hay world enlazado")
            return None
        return self._world

    def _on_event(self, event: Event) -> None:
        """
        Callback genÃ©rico para todos los eventos.
        Busca reglas que coincidan y las ejecuta.
        """
        for rule in self._rules:
            if rule.get("event") != event.name:
                continue

            # Verificar condiciones
            if self._check_conditions(rule.get("when", {}), event):
                self._execute_actions(rule.get("do", []), event)
                self._rules_executed += 1

    def _check_conditions(self, conditions: Dict[str, Any], event: Event) -> bool:
        """
        Verifica si las condiciones de una regla se cumplen.

        Args:
            conditions: Diccionario de condiciones
            event: Evento actual

        Returns:
            True si todas las condiciones se cumplen
        """
        if not conditions:
            return True

        event_data = event.data

        for key, expected_value in conditions.items():
            actual_value = event_data.get(key)

            if actual_value != expected_value:
                return False

        return True

    def _execute_actions(self, actions: List[Dict[str, Any]], event: Event) -> None:
        """
        Ejecuta una lista de acciones.

        Args:
            actions: Lista de acciones a ejecutar
            event: Evento que disparÃ³ las acciones
        """
        for action in actions:
            action_type = action.get("action")

            if action_type is None:
                print("[WARNING] RuleSystem: acciÃ³n sin tipo")
                continue

            try:
                self._execute_action(action_type, action, event)
            except Exception as e:
                print(f"[ERROR] RuleSystem: error ejecutando '{action_type}': {e}")

    def _execute_action(self, action_type: str, params: Dict[str, Any], event: Event) -> None:
        """
        Ejecuta una acciÃ³n individual.

        Args:
            action_type: Tipo de acciÃ³n
            params: ParÃ¡metros de la acciÃ³n
            event: Evento contexto
        """
        if action_type == "set_animation":
            self._action_set_animation(params)

        elif action_type == "set_position":
            self._action_set_position(params)

        elif action_type == "destroy_entity":
            self._action_destroy_entity(params)

        elif action_type == "emit_event":
            self._action_emit_event(params)

        elif action_type == "log_message":
            self._action_log_message(params, event)

        else:
            print(f"[WARNING] RuleSystem: acciÃ³n desconocida '{action_type}'")

    def _action_set_animation(self, params: Dict[str, Any]) -> None:
        """Cambia el estado de animaciÃ³n de una entidad."""
        entity_name = params.get("entity")
        state = params.get("state")

        if not entity_name or not state:
            print("[WARNING] set_animation: falta entity o state")
            return

        world = self._get_world_for_action("set_animation")
        if world is None:
            return

        entity = world.get_entity_by_name(entity_name)
        if entity is None:
            return

        animator = entity.get_component(Animator)
        controller = entity.get_component(AnimatorController)
        if animator is not None and controller is not None and controller.enabled and state in controller.states:
            controller.set_active_state(state, last_transition_id="rule_set_animation")
            animation_state = controller.get_state_animation(state)
            if animation_state in animator.animations:
                animator.play(animation_state, force_restart=True)
            return
        if animator is not None:
            animator.play(state)

    def _action_set_position(self, params: Dict[str, Any]) -> None:
        """Mueve una entidad a una posiciÃ³n."""
        entity_name = params.get("entity")
        x = params.get("x")
        y = params.get("y")

        if not entity_name:
            return

        world = self._get_world_for_action("set_position")
        if world is None:
            return

        entity = world.get_entity_by_name(entity_name)
        if entity is None:
            return

        transform = entity.get_component(Transform)
        if transform is not None:
            if x is not None:
                transform.x = float(x)
            if y is not None:
                transform.y = float(y)

    def _action_destroy_entity(self, params: Dict[str, Any]) -> None:
        """Elimina una entidad del mundo."""
        entity_name = params.get("entity")

        if not entity_name:
            return

        world = self._get_world_for_action("destroy_entity")
        if world is None:
            return

        entity = world.get_entity_by_name(entity_name)
        if entity is not None:
            world.destroy_entity(entity.id)

    def _action_emit_event(self, params: Dict[str, Any]) -> None:
        """Emite otro evento."""
        event_name = params.get("event")
        data = params.get("data", {})

        if event_name:
            self._event_bus.emit(event_name, data)

    def _action_log_message(self, params: Dict[str, Any], event: Event) -> None:
        """Imprime un mensaje en consola."""
        message = params.get("message", "")
        # Sustituir placeholders bÃ¡sicos
        message = message.replace("{event}", event.name)
        print(f"[RULE] {message}")

    @property
    def rules_count(self) -> int:
        """NÃºmero de reglas cargadas."""
        return len(self._rules)

    @property
    def rules_executed_count(self) -> int:
        """NÃºmero de reglas ejecutadas."""
        return self._rules_executed
