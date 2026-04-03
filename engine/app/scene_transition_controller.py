from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable, Optional

from engine.components.collider import Collider
from engine.components.inputmap import InputMap
from engine.components.playercontroller2d import PlayerController2D
from engine.components.rigidbody import RigidBody
from engine.components.scene_entry_point import SceneEntryPoint
from engine.components.scene_transition_action import SceneTransitionAction
from engine.components.scene_transition_on_contact import SceneTransitionOnContact
from engine.components.scene_transition_on_interact import SceneTransitionOnInteract
from engine.components.scene_transition_on_player_death import SceneTransitionOnPlayerDeath
from engine.components.transform import Transform
from engine.core.engine_state import EngineState
from engine.editor.console_panel import log_err
from engine.scenes.scene_transition_support import (
    find_scene_entry_point_in_world,
    list_scene_entry_points_from_payload,
    load_scene_transition_payload,
    resolve_scene_transition_target_path,
)

if TYPE_CHECKING:
    from engine.ecs.entity import Entity
    from engine.ecs.world import World
    from engine.events.event_bus import Event, EventBus
    from engine.physics.registry import PhysicsBackendRegistry


class SceneTransitionController:
    """Ejecuta una unica accion de cambio de escena reutilizada por varios triggers."""

    def __init__(
        self,
        *,
        get_state: Callable[[], EngineState],
        get_world: Callable[[], Optional["World"]],
        get_scene_manager: Callable[[], Any],
        get_physics_backend_registry: Callable[[], "PhysicsBackendRegistry"],
        load_scene_by_path: Callable[[str], bool],
        play_runtime: Callable[[], None],
    ) -> None:
        self._get_state = get_state
        self._get_world = get_world
        self._get_scene_manager = get_scene_manager
        self._get_physics_backend_registry = get_physics_backend_registry
        self._load_scene_by_path = load_scene_by_path
        self._play_runtime = play_runtime
        self._event_bus: Optional["EventBus"] = None
        self._pending_entry_id: str = ""
        self._interact_latches: set[tuple[str, str]] = set()

    def set_event_bus(self, event_bus: Optional["EventBus"]) -> None:
        if self._event_bus is event_bus:
            return
        if self._event_bus is not None:
            self._event_bus.unsubscribe("on_trigger_enter", self._on_trigger_enter)
            self._event_bus.unsubscribe("on_collision", self._on_collision)
            self._event_bus.unsubscribe("player_death", self._on_player_death)
        self._event_bus = event_bus
        if self._event_bus is not None:
            self._event_bus.subscribe("on_trigger_enter", self._on_trigger_enter)
            self._event_bus.subscribe("on_collision", self._on_collision)
            self._event_bus.subscribe("player_death", self._on_player_death)

    def run_transition_for_entity(self, entity_name: str) -> bool:
        world = self._get_world()
        if world is None:
            return False
        entity = world.get_entity_by_name(str(entity_name or "").strip())
        if entity is None:
            return False
        action = entity.get_component(SceneTransitionAction)
        if action is None or not action.enabled:
            return False

        target_scene_path = str(action.target_scene_path or "").strip()
        if not target_scene_path:
            log_err(f"SceneTransition: entity '{entity.name}' has no target_scene_path")
            return False

        source_scene_path = self._current_scene_source_path()
        resolved_path = resolve_scene_transition_target_path(source_scene_path, target_scene_path)
        if resolved_path is None or not resolved_path.exists():
            log_err(f"SceneTransition: target scene '{target_scene_path}' was not found")
            return False

        target_payload = load_scene_transition_payload(resolved_path)
        if target_payload is None:
            log_err(f"SceneTransition: target scene '{target_scene_path}' is unreadable or invalid")
            return False

        target_entry_id = str(action.target_entry_id or "").strip()
        if target_entry_id:
            entry_points = list_scene_entry_points_from_payload(target_payload)
            if not any(item["entry_id"] == target_entry_id for item in entry_points):
                log_err(
                    f"SceneTransition: target entry point '{target_entry_id}' was not found in scene '{target_scene_path}'"
                )
                return False

        was_running = self._get_state() in (EngineState.PLAY, EngineState.PAUSED, EngineState.STEPPING)
        self._pending_entry_id = target_entry_id if was_running and target_entry_id else ""
        if not self._load_scene_by_path(resolved_path.as_posix()):
            self._pending_entry_id = ""
            return False

        if was_running and self._get_state() == EngineState.EDIT:
            self._play_runtime()

        if self._pending_entry_id:
            applied = self._apply_pending_spawn()
            self._interact_latches.clear()
            return applied

        self._interact_latches.clear()
        return True

    def update(self, world: Optional["World"]) -> None:
        if world is None:
            self._interact_latches.clear()
            return
        backend = self._get_physics_backend_registry().resolve(world).backend
        if backend is None:
            self._interact_latches.clear()
            return

        active_pairs: set[tuple[str, str]] = set()
        for contact in backend.collect_contacts(world):
            if not bool(contact.is_trigger):
                continue
            entity_a = world.get_entity_by_name(contact.entity_a)
            entity_b = world.get_entity_by_name(contact.entity_b)
            if entity_a is None or entity_b is None:
                continue
            if self._process_interaction_pair(entity_a, entity_b, active_pairs):
                return
            if self._process_interaction_pair(entity_b, entity_a, active_pairs):
                return

        self._interact_latches = active_pairs

    def _process_interaction_pair(
        self,
        owner: "Entity",
        actor: "Entity",
        active_pairs: set[tuple[str, str]],
    ) -> bool:
        interact = owner.get_component(SceneTransitionOnInteract)
        action = owner.get_component(SceneTransitionAction)
        if interact is None or action is None or not interact.enabled or not action.enabled:
            return False
        if interact.require_player and not self._is_player_entity(actor):
            return False
        input_map = actor.get_component(InputMap)
        if input_map is None or not input_map.enabled:
            return False
        action_pressed = float(input_map.last_state.get("action_2", 0.0)) > 0.5
        pair = (owner.name, actor.name)
        if not action_pressed:
            return False
        active_pairs.add(pair)
        if pair in self._interact_latches:
            return False
        self._interact_latches = active_pairs
        return self.run_transition_for_entity(owner.name)

    def _on_trigger_enter(self, event: "Event") -> None:
        self._handle_contact_event(event, expected_mode="trigger_enter")

    def _on_collision(self, event: "Event") -> None:
        self._handle_contact_event(event, expected_mode="collision")

    def _handle_contact_event(self, event: "Event", *, expected_mode: str) -> None:
        world = self._get_world()
        if world is None:
            return
        entity_a = world.get_entity_by_name(str(event.data.get("entity_a", "") or "").strip())
        entity_b = world.get_entity_by_name(str(event.data.get("entity_b", "") or "").strip())
        if entity_a is None or entity_b is None:
            return
        if self._process_contact_side(entity_a, entity_b, expected_mode=expected_mode):
            return
        self._process_contact_side(entity_b, entity_a, expected_mode=expected_mode)

    def _process_contact_side(self, owner: "Entity", other: "Entity", *, expected_mode: str) -> bool:
        trigger = owner.get_component(SceneTransitionOnContact)
        action = owner.get_component(SceneTransitionAction)
        if trigger is None or action is None or not trigger.enabled or not action.enabled:
            return False
        if str(trigger.mode or "").strip() != expected_mode:
            return False
        if trigger.require_player and not self._is_player_entity(other):
            return False
        return self.run_transition_for_entity(owner.name)

    def _on_player_death(self, event: "Event") -> None:
        world = self._get_world()
        if world is None:
            return
        entity_name = str(event.data.get("entity") or event.data.get("entity_name") or "").strip()
        if not entity_name:
            return
        entity = world.get_entity_by_name(entity_name)
        if entity is None:
            return
        trigger = entity.get_component(SceneTransitionOnPlayerDeath)
        action = entity.get_component(SceneTransitionAction)
        if trigger is None or action is None or not trigger.enabled or not action.enabled:
            return
        self.run_transition_for_entity(entity.name)

    def _apply_pending_spawn(self) -> bool:
        entry_id = str(self._pending_entry_id or "").strip()
        self._pending_entry_id = ""
        if not entry_id:
            return True

        world = self._get_world()
        if world is None:
            log_err(f"SceneTransition: cannot apply entry point '{entry_id}' without an active world")
            return False
        entry_entity = find_scene_entry_point_in_world(world, entry_id)
        if entry_entity is None:
            log_err(f"SceneTransition: entry point '{entry_id}' is missing in the active scene")
            return False
        player = self._find_primary_player(world)
        if player is None:
            log_err(f"SceneTransition: could not resolve a player entity for entry point '{entry_id}'")
            return False

        entry_transform = entry_entity.get_component(Transform)
        player_transform = player.get_component(Transform)
        if entry_transform is None or player_transform is None:
            log_err(f"SceneTransition: entry point '{entry_id}' cannot be applied because Transform is missing")
            return False

        player_transform.set_position(entry_transform.x, entry_transform.y)
        rigidbody = player.get_component(RigidBody)
        if rigidbody is not None:
            rigidbody.velocity_x = 0.0
            rigidbody.velocity_y = 0.0

        backend = self._get_physics_backend_registry().resolve(world).backend
        if backend is not None:
            backend.sync_world(world)
        return True

    def _find_primary_player(self, world: "World") -> Optional["Entity"]:
        for entity in world.get_entities_with(PlayerController2D, Transform):
            return entity
        for entity in world.get_all_entities():
            if not entity.active:
                continue
            if entity.get_component(Transform) is None:
                continue
            if str(entity.tag or "").strip().lower() in {"player", "hero"}:
                return entity
        return None

    def _is_player_entity(self, entity: Optional["Entity"]) -> bool:
        if entity is None or not entity.active:
            return False
        if entity.get_component(PlayerController2D) is not None:
            return True
        return str(entity.tag or "").strip().lower() in {"player", "hero"}

    def _current_scene_source_path(self) -> str | None:
        scene_manager = self._get_scene_manager()
        if scene_manager is None or scene_manager.current_scene is None:
            return None
        return scene_manager.current_scene.source_path
