from __future__ import annotations

import json
from typing import Callable, Dict, Optional, Union

from engine.api._context import EngineAPIComponent
from engine.api.types import ActionResult, EngineStatus, EntityData, ShapeCastResult
from engine.components.rigidbody import RigidBody
from engine.ecs.entity import normalize_entity_groups
from engine.events.signals import SignalConnectionFlags
from engine.physics.backend import PhysicsBackendInfo, PhysicsBackendSelection


class RuntimeAPI(EngineAPIComponent):
    """Runtime and inspection operations exposed through EngineAPI."""

    def play(self) -> None:
        """Start the engine play mode, activating all runtime systems.

        Transitions the engine from EDIT or STOPPED state to PLAY state.
        Entities are instantiated from the active scene data.
        """
        runtime = self.runtime
        if runtime is not None:
            runtime.play()

    def stop(self) -> None:
        """Stop play mode and return to edit state.

        Destroys the runtime world and transitions the engine back to EDIT state.
        """
        runtime = self.runtime
        if runtime is not None:
            runtime.stop()

    def set_seed(self, seed: int | None) -> ActionResult:
        """Set the random number generator seed for deterministic gameplay.

        Args:
            seed: Integer seed value, or None to randomize.

        Returns:
            ActionResult with the effective seed value applied.
        """
        runtime = self.runtime
        if runtime is None:
            return self.fail("Engine not initialized")
        runtime.set_seed(seed)
        return self.ok("Seed updated", {"seed": runtime.random_seed})

    def undo(self) -> ActionResult:
        """Undo the last authoring transaction if in edit mode.

        Returns:
            ActionResult confirming undo was applied, or failure if no undo is
            available or engine is not initialized.
        """
        runtime = self.runtime
        if runtime is None:
            return self.fail("Engine not initialized")
        success = runtime.undo()
        return self.ok("Undo applied") if success else self.fail("Undo unavailable")

    def redo(self) -> ActionResult:
        """Redo the last undone authoring transaction if in edit mode.

        Returns:
            ActionResult confirming redo was applied, or failure if no redo is
            available or engine is not initialized.
        """
        runtime = self.runtime
        if runtime is None:
            return self.fail("Engine not initialized")
        success = runtime.redo()
        return self.ok("Redo applied") if success else self.fail("Redo unavailable")

    def step(self, frames: int = 1) -> None:
        """Advance the simulation by a given number of frames while in play mode.

        Args:
            frames: Number of frames to simulate (default 1).
        """
        runtime = self.runtime
        if runtime is None:
            return
        if hasattr(runtime, "step_frame"):
            for _ in range(frames):
                runtime.step_frame()
            return
        if hasattr(runtime, "step"):
            for _ in range(frames):
                runtime.step()

    def get_recent_events(self, count: int = 50) -> list[Dict[str, Union[str, int, float, bool, list, dict, None]]]:
        """Retrieve the most recent events from the event bus.

        Args:
            count: Maximum number of events to return (default 50).

        Returns:
            List of event dictionaries with 'name' and 'data' keys.
        """
        runtime = self.runtime
        if runtime is None or runtime.event_bus is None:
            return []
        limit = max(0, int(count))
        events = runtime.event_bus.get_recent_events(limit)
        return [
            {
                "name": str(event.name),
                "data": json.loads(json.dumps(event.data, ensure_ascii=True, default=str)),
            }
            for event in events
        ]

    def get_status(self) -> EngineStatus:
        """Get the current runtime status snapshot.

        Returns:
            EngineStatus dictionary with state, frame, time, fps, and
            entity_count fields.

        Raises:
            RuntimeError: If the engine is not initialized.
        """
        runtime = self.runtime
        if runtime is None:
            raise RuntimeError("Engine not initialized")
        world = runtime.world
        return {
            "state": str(runtime.state),
            "frame": runtime.time.frame_count,
            "time": runtime.time.total_time,
            "fps": runtime.time.fps,
            "entity_count": world.entity_count() if world else 0,
        }

    def list_entities(
        self,
        tag: Optional[str] = None,
        layer: Optional[str] = None,
        active: Optional[bool] = None,
    ) -> list[EntityData]:
        """List all entities in the current runtime world with optional filters.

        Args:
            tag: Filter by entity tag (None = no filter).
            layer: Filter by entity layer (None = no filter).
            active: Filter by active state (None = no filter).

        Returns:
            List of EntityData dictionaries representing matching entities.
        """
        runtime = self.runtime
        if runtime is None or runtime.world is None:
            return []
        entities: list[EntityData] = []
        for entity in runtime.world.iter_all_entities():
            if tag is not None and entity.tag != tag:
                continue
            if layer is not None and entity.layer != layer:
                continue
            if active is not None and entity.active != active:
                continue
            entities.append(self.get_entity(entity.name))
        return entities

    def get_entity(self, name: str) -> EntityData:
        """Get serialized data for a single entity by name.

        Args:
            name: Entity name.

        Returns:
            EntityData dictionary with name, active, tag, layer, parent,
            prefab_instance, components, and component_metadata.
        """
        entity = self.require_entity(name)
        serialized = entity.to_dict()
        return {
            "name": entity.name,
            "active": entity.active,
            "tag": entity.tag,
            "layer": entity.layer,
            "parent": entity.parent_name,
            "prefab_instance": entity.prefab_instance,
            "components": dict(serialized.get("components", {})),
            "component_metadata": dict(serialized.get("component_metadata", {})),
        }

    def get_primary_camera(self) -> Optional[EntityData]:
        """Find the entity marked as the primary camera in the scene.

        Returns:
            EntityData for the primary camera entity, or None if no camera is
            marked as primary.
        """
        runtime = self.runtime
        if runtime is None or runtime.world is None:
            return None
        from engine.components.camera2d import Camera2D
        from engine.components.transform import Transform

        for entity in runtime.world.get_entities_with(Transform, Camera2D):
            camera_component = entity.get_component(Camera2D)
            if camera_component is not None and camera_component.is_primary:
                return self.get_entity(entity.name)
        return None

    def get_input_state(self, entity_name: str) -> Dict[str, float]:
        """Get the current raw input values for an entity's InputMap.

        Args:
            entity_name: Name of the entity with an InputMap component.

        Returns:
            Dictionary mapping action names to their current float values.
        """
        from engine.components.inputmap import InputMap

        entity = self.require_entity(entity_name)
        input_map = entity.get_component(InputMap)
        if input_map is None:
            return {}
        return dict(input_map.last_state)

    def inject_input_state(self, entity_name: str, state: Dict[str, float], frames: int = 1) -> ActionResult:
        """Inject simulated input values for testing or AI-driven gameplay.

        Args:
            entity_name: Name of the entity with an InputMap component.
            state: Mapping of action names to fake input values (e.g.
                {"move_left": 1.0, "move_right": 0.0}).
            frames: Number of frames the injected input persists (default 1).

        Returns:
            ActionResult confirming the injection.
        """
        runtime = self.runtime
        if runtime is None:
            return self.fail("Engine not initialized")
        if runtime.input_system is None:
            return self.fail("Input system not ready")
        normalized_name = str(entity_name).strip()
        if not normalized_name:
            return self.fail("Entity name is required")
        normalized_frames = max(1, int(frames))
        runtime.input_system.inject_state(normalized_name, dict(state), frames=normalized_frames)
        return self.ok(
            "Input injected",
            {
                "entity": normalized_name,
                "state": dict(state),
                "frames": normalized_frames,
            },
        )

    def get_audio_state(self, entity_name: str) -> Dict[str, Union[str, int, float, bool]]:
        """Get the current runtime state of an AudioSource component.

        Args:
            entity_name: Name of the entity with an AudioSource component.

        Returns:
            Dictionary with audio source properties plus playback_position,
            playback_duration, and is_paused.
        """
        from engine.components.audiosource import AudioSource

        runtime = self.runtime
        if runtime is None or runtime.world is None:
            return {}
        entity = self.require_entity(entity_name)
        audio_source = entity.get_component(AudioSource)
        if audio_source is None:
            return {}
        state = audio_source.to_dict()
        state["playback_position"] = audio_source.playback_position
        state["playback_duration"] = audio_source.playback_duration
        state["is_paused"] = audio_source.is_paused
        return state

    def get_script_public_data(self, entity_name: str) -> Dict[str, Union[str, int, float, bool, list, dict]]:
        """Get the public_data dictionary from a ScriptBehaviour component.

        Args:
            entity_name: Name of the entity with a ScriptBehaviour component.

        Returns:
            Dictionary of public data, or empty dict if not found.
        """
        from engine.components.scriptbehaviour import ScriptBehaviour

        entity = self.require_entity(entity_name)
        script_behaviour = entity.get_component(ScriptBehaviour)
        if script_behaviour is None:
            return {}
        return dict(script_behaviour.public_data)

    def query_physics_aabb(self, left: float, top: float, right: float, bottom: float) -> list[Dict[str, Union[str, int, float, bool, list, dict, None]]]:
        """Query the physics world for colliders overlapping an axis-aligned bounding box.

        Args:
            left: Left edge of the query rectangle.
            top: Top edge of the query rectangle.
            right: Right edge of the query rectangle.
            bottom: Bottom edge of the query rectangle.

        Returns:
            List of hit result dictionaries.
        """
        runtime = self.runtime
        if runtime is None:
            return []
        return runtime.query_physics_aabb(left, top, right, bottom)

    def query_physics_ray(
        self,
        origin_x: float,
        origin_y: float,
        direction_x: float,
        direction_y: float,
        max_distance: float,
    ) -> list[Dict[str, Union[str, int, float, bool, list, dict, None]]]:
        """Cast a ray through the physics world and return all hits.

        Args:
            origin_x: Ray origin x coordinate.
            origin_y: Ray origin y coordinate.
            direction_x: Ray direction x component.
            direction_y: Ray direction y component.
            max_distance: Maximum ray length.

        Returns:
            List of hit result dictionaries, sorted by distance.
        """
        runtime = self.runtime
        if runtime is None:
            return []
        return runtime.query_physics_ray(origin_x, origin_y, direction_x, direction_y, max_distance)

    def query_physics_shape_cast(
        self,
        shape_type: str,
        shape_width: float,
        shape_height: float,
        origin_x: float,
        origin_y: float,
        direction_x: float,
        direction_y: float,
        max_distance: float,
    ) -> list[ShapeCastResult]:
        """Cast a shape through the physics world and return the first hit.

        Args:
            shape_type: 'box' or 'circle'.
            shape_width: Width of the shape (diameter for circle).
            shape_height: Height of the shape (diameter for circle).
            origin_x: Starting position x.
            origin_y: Starting position y.
            direction_x: Direction x component.
            direction_y: Direction y component.
            max_distance: Maximum cast distance.

        Returns:
            List with at most one ShapeCastResult hit, or empty list if no hit.
        """
        runtime = self.runtime
        if runtime is None:
            return []
        return runtime.query_physics_shape_cast(
            shape_type, shape_width, shape_height,
            origin_x, origin_y, direction_x, direction_y, max_distance,
        )

    def list_physics_backends(self) -> list[PhysicsBackendInfo]:
        """List all available physics backends with their capabilities.

        Returns:
            List of PhysicsBackendInfo dictionaries.
        """
        runtime = self.runtime
        if runtime is None:
            return []
        return runtime.list_physics_backends()

    def get_physics_backend_selection(self) -> PhysicsBackendSelection:
        """Get the current physics backend selection and fallback information.

        Returns:
            PhysicsBackendSelection dictionary with requested_backend,
            effective_backend, used_fallback, fallback_reason, and
            unavailable_reason.
        """
        runtime = self.runtime
        if runtime is None:
            return {
                "requested_backend": "legacy_aabb",
                "effective_backend": None,
                "used_fallback": False,
                "fallback_reason": None,
                "unavailable_reason": "Engine not initialized",
            }
        return runtime.get_physics_backend_selection()

    def apply_force(self, entity_name: str, force_x: float, force_y: float) -> bool:
        """Aplica fuerza continua a una entidad con RigidBody."""
        entity = self.require_entity(entity_name)
        if entity is None:
            return False
        rb = entity.get_component(RigidBody)
        if rb is None:
            return False
        rb.apply_force(force_x, force_y)
        return True

    def apply_impulse(self, entity_name: str, impulse_x: float, impulse_y: float) -> bool:
        """Aplica impulso instantáneo a una entidad con RigidBody."""
        entity = self.require_entity(entity_name)
        if entity is None:
            return False
        rb = entity.get_component(RigidBody)
        if rb is None:
            return False
        rb.apply_impulse(impulse_x, impulse_y)
        return True

    def apply_torque(self, entity_name: str, torque: float) -> bool:
        """Aplica torque a una entidad con RigidBody."""
        entity = self.require_entity(entity_name)
        if entity is None:
            return False
        rb = entity.get_component(RigidBody)
        if rb is None:
            return False
        rb.apply_torque(torque)
        return True

    def play_audio(self, entity_name: str) -> ActionResult:
        """Start audio playback for an AudioSource entity.

        Args:
            entity_name: Name of the entity with an AudioSource component.

        Returns:
            ActionResult confirming playback started, or failure if the audio
            source is not found or disabled.
        """
        runtime = self.runtime
        if runtime is None or runtime.world is None or runtime.audio_system is None:
            return self.fail("Audio system not ready")
        success = runtime.audio_system.play(runtime.world, entity_name)
        return self.ok("Audio started", {"entity": entity_name}) if success else self.fail("Audio source not found or disabled")

    def stop_audio(self, entity_name: str) -> ActionResult:
        """Stop audio playback for an AudioSource entity.

        Args:
            entity_name: Name of the entity with an AudioSource component.

        Returns:
            ActionResult confirming playback stopped.
        """
        runtime = self.runtime
        if runtime is None or runtime.world is None or runtime.audio_system is None:
            return self.fail("Audio system not ready")
        success = runtime.audio_system.stop(runtime.world, entity_name)
        return self.ok("Audio stopped", {"entity": entity_name}) if success else self.fail("Audio source not found")

    def pause_audio(self, entity_name: str) -> ActionResult:
        """Pause audio playback for an AudioSource entity.

        Args:
            entity_name: Name of the entity with an AudioSource component.

        Returns:
            ActionResult confirming audio was paused.
        """
        runtime = self.runtime
        if runtime is None or runtime.world is None or runtime.audio_system is None:
            return self.fail("Audio system not ready")
        success = runtime.audio_system.pause(runtime.world, entity_name)
        return self.ok("Audio paused", {"entity": entity_name}) if success else self.fail("Audio source not found, disabled, or already paused")

    def resume_audio(self, entity_name: str) -> ActionResult:
        """Resume paused audio playback for an AudioSource entity.

        Args:
            entity_name: Name of the entity with an AudioSource component.

        Returns:
            ActionResult confirming audio was resumed.
        """
        runtime = self.runtime
        if runtime is None or runtime.world is None or runtime.audio_system is None:
            return self.fail("Audio system not ready")
        success = runtime.audio_system.resume(runtime.world, entity_name)
        return self.ok("Audio resumed", {"entity": entity_name}) if success else self.fail("Audio source not found, disabled, or not paused")

    def get_group_entities(self, group_name: str) -> list[str]:
        """Get the names of all entities belonging to a group.

        Args:
            group_name: Name of the group.

        Returns:
            List of entity name strings.
        """
        runtime = self.runtime
        if runtime is None or runtime.world is None:
            return []
        ops = runtime.group_operations
        if ops is None:
            return []
        return [e.name for e in ops.get_entities(group_name)]

    def get_first_in_group(self, group_name: str) -> str | None:
        """Get the name of the first entity found in a group.

        Args:
            group_name: Name of the group.

        Returns:
            Entity name string or None if the group is empty or not found.
        """
        runtime = self.runtime
        if runtime is None or runtime.world is None:
            return None
        ops = runtime.group_operations
        if ops is None:
            return None
        ent = ops.get_first_entity(group_name)
        return ent.name if ent is not None else None

    def is_in_group(self, entity_name: str, group_name: str) -> bool:
        """Check if an entity belongs to a specific group.

        Args:
            entity_name: Name of the entity.
            group_name: Name of the group.

        Returns:
            True if the entity is in the group, False otherwise.
        """
        runtime = self.runtime
        if runtime is None or runtime.world is None:
            return False
        ops = runtime.group_operations
        if ops is None:
            return False
        return ops.has(group_name, entity_name)

    def count_group(self, group_name: str) -> int:
        """Count the number of entities in a group.

        Args:
            group_name: Name of the group.

        Returns:
            Integer count of entities in the group.
        """
        runtime = self.runtime
        if runtime is None or runtime.world is None:
            return 0
        ops = runtime.group_operations
        if ops is None:
            return 0
        return ops.count(group_name)

    def call_group(self, group_name: str, method_name: str, *args: object, **kwargs: object) -> ActionResult:  # type: ignore[no-any-explicit]  # Variadic args: tipo exacto depende del grupo llamado
        """Call a method on every entity in a group by name.

        Args:
            group_name: Name of the group.
            method_name: Name of the method to invoke on each entity.
            *args: Positional arguments passed to the method.
            **kwargs: Keyword arguments passed to the method.

        Returns:
            ActionResult with the number of entities invoked.
        """
        runtime = self.runtime
        if runtime is None or runtime.world is None:
            return self.fail("Engine not initialized")
        ops = runtime.group_operations
        if ops is None:
            return self.fail("Group operations unavailable")
        invoked = ops.call_group(group_name, method_name, *args, **kwargs)
        return self.ok(
            "Group call completed",
            {"group": group_name, "method": method_name, "invoked": invoked},
        )

    def emit_group(self, group_name: str, signal_name: str, *args: object, **kwargs: object) -> ActionResult:  # type: ignore[no-any-explicit]  # Variadic args: tipo exacto depende del grupo
        """Emit a signal on every entity in a group.

        Args:
            group_name: Name of the group.
            signal_name: Name of the signal to emit.
            *args: Positional arguments passed to signal handlers.
            **kwargs: Keyword arguments passed to signal handlers.

        Returns:
            ActionResult with the number of signal handlers executed.
        """
        runtime = self.runtime
        if runtime is None or runtime.world is None:
            return self.fail("Engine not initialized")
        ops = runtime.group_operations
        if ops is None:
            return self.fail("Group operations unavailable")
        total = ops.emit_group(group_name, signal_name, *args, **kwargs)
        return self.ok(
            "Group emit completed",
            {"group": group_name, "signal": signal_name, "executed": total},
        )

    # --- Señales ---

    def connect_signal(
        self,
        source_id: str,
        signal_name: str,
        callback: Callable[..., object],  # type: ignore[no-any-explicit]  # Callback genérico: tipo exacto depende del evento
        *,
        flags: list[str] | int | None = None,
        binds: tuple[object, ...] | list[object] | None = None,
        connection_id: str | None = None,
        description: str = "",
        target_id: str | None = None,
    ) -> str:
        """Conecta una señal runtime a un callback directo.

        Retorna el id de la conexión creada.
        """
        runtime = self.runtime
        if runtime is None:
            return ""
        signal_runtime = runtime.signal_runtime
        if signal_runtime is None:
            return ""
        normalized_flags = self._normalize_signal_flags(flags)
        return signal_runtime.connect(
            source_id,
            signal_name,
            callback,
            flags=normalized_flags,
            binds=binds,
            connection_id=connection_id,
            description=description,
            target_id=target_id,
        )

    def emit_signal(self, source_id: str, signal_name: str, *args: object, **kwargs: object) -> int:  # type: ignore[no-any-explicit]  # Variadic: tipo exacto depende de la señal
        """Emite una señal runtime y retorna el número de conexiones ejecutadas."""
        runtime = self.runtime
        if runtime is None:
            return 0
        signal_runtime = runtime.signal_runtime
        if signal_runtime is None:
            return 0
        return signal_runtime.emit(source_id, signal_name, *args, **kwargs)

    def disconnect_signal(self, connection_id: str) -> bool:
        """Desconecta una señal runtime por su connection_id."""
        runtime = self.runtime
        if runtime is None:
            return False
        signal_runtime = runtime.signal_runtime
        if signal_runtime is None:
            return False
        return signal_runtime.disconnect(connection_id)

    def list_signal_connections(
        self,
        source_id: str | None = None,
        signal_name: str | None = None,
    ) -> list[dict[str, Union[str, int, float, bool, list, dict, None]]]:
        """Lista conexiones runtime activas, opcionalmente filtradas."""
        runtime = self.runtime
        if runtime is None:
            return []
        signal_runtime = runtime.signal_runtime
        if signal_runtime is None:
            return []
        connections = signal_runtime.list_connections(source_id=source_id, signal_name=signal_name)
        result: list[dict[str, Union[str, int, float, bool, list, dict, None]]] = []
        for conn in connections:
            flag_names: list[str] = []
            if conn.flags & SignalConnectionFlags.DEFERRED:
                flag_names.append("deferred")
            if conn.flags & SignalConnectionFlags.PERSIST:
                flag_names.append("persist")
            if conn.flags & SignalConnectionFlags.ONE_SHOT:
                flag_names.append("one_shot")
            if conn.flags & SignalConnectionFlags.REFERENCE_COUNTED:
                flag_names.append("reference_counted")
            result.append({
                "connection_id": conn.connection_id,
                "source_id": conn.signal.source_id,
                "signal_name": conn.signal.signal_name,
                "flags": flag_names,
                "binds": list(conn.binds),
                "enabled": conn.enabled,
                "target_id": conn.target_id,
                "description": conn.description,
                "reference_count": conn.reference_count,
            })
        return result

    def _normalize_signal_flags(self, flags: list[str] | int | None) -> SignalConnectionFlags:
        """Normaliza flags de conexión de señal desde lista de strings o int."""
        if flags is None:
            return SignalConnectionFlags.NONE
        if isinstance(flags, int):
            return SignalConnectionFlags(flags)
        if not isinstance(flags, list):
            return SignalConnectionFlags.NONE
        normalized_flags = {
            str(item).strip().lower()
            for item in flags
            if isinstance(item, str) and str(item).strip()
        }
        result = SignalConnectionFlags.NONE
        if "deferred" in normalized_flags:
            result |= SignalConnectionFlags.DEFERRED
        if "persist" in normalized_flags:
            result |= SignalConnectionFlags.PERSIST
        if "one_shot" in normalized_flags:
            result |= SignalConnectionFlags.ONE_SHOT
        if "reference_counted" in normalized_flags:
            result |= SignalConnectionFlags.REFERENCE_COUNTED
        return result

    def _is_edit_mode(self) -> bool:
        runtime = self.runtime
        if runtime is None:
            return False
        return bool(getattr(runtime, "is_edit_mode", False))

    def _get_authoring_groups(self, entity_name: str) -> list[str] | None:
        authoring = self.scene_authoring
        if authoring is None:
            return None
        entity_data = authoring.find_entity_data(entity_name)
        if entity_data is None:
            return None
        return list(normalize_entity_groups(entity_data.get("groups", ())))

    def _set_authoring_groups(self, entity_name: str, groups: list[str]) -> bool:
        authoring = self.scene_authoring
        if authoring is None:
            return False
        return authoring.update_entity_property(entity_name, "groups", list(normalize_entity_groups(groups)))

    # --- Grupos ---

    def add_entity_to_group(self, entity_name: str, group_name: str) -> ActionResult:
        """Añade una entidad a un grupo.

        En `EDIT` persiste el cambio vía `SceneManager`.
        En `PLAY` aplica la mutación solo sobre el world runtime actual.
        """
        runtime = self.runtime
        if runtime is None or runtime.world is None:
            return self.fail("Engine not initialized")
        normalized_group = str(group_name).strip()
        if not normalized_group:
            return self.fail("Group name is required")

        if self._is_edit_mode():
            current = self._get_authoring_groups(entity_name)
            if current is None:
                return self.fail(f"Entity '{entity_name}' not found")
            if normalized_group in current:
                return self.ok("Entity already in group", {"entity": entity_name, "group": normalized_group})
            updated = list(current)
            updated.append(normalized_group)
            if not self._set_authoring_groups(entity_name, updated):
                return self.fail("Group update failed")
            return self.ok("Entity added to group", {"entity": entity_name, "group": normalized_group})

        entity = runtime.world.get_entity_by_name(entity_name)
        if entity is None:
            return self.fail(f"Entity '{entity_name}' not found")
        runtime_groups = set(entity.groups)
        if normalized_group in runtime_groups:
            return self.ok("Entity already in group", {"entity": entity_name, "group": normalized_group})
        runtime_groups.add(normalized_group)
        entity.groups = tuple(runtime_groups)
        return self.ok("Entity added to group", {"entity": entity_name, "group": normalized_group})

    def remove_entity_from_group(self, entity_name: str, group_name: str) -> ActionResult:
        """Quita una entidad de un grupo en authoring o runtime según el modo actual."""
        runtime = self.runtime
        if runtime is None or runtime.world is None:
            return self.fail("Engine not initialized")
        normalized_group = str(group_name).strip()
        if not normalized_group:
            return self.fail("Group name is required")

        if self._is_edit_mode():
            current = self._get_authoring_groups(entity_name)
            if current is None:
                return self.fail(f"Entity '{entity_name}' not found")
            if normalized_group not in current:
                return self.ok("Entity was not in group", {"entity": entity_name, "group": normalized_group})
            updated = [group for group in current if group != normalized_group]
            if not self._set_authoring_groups(entity_name, updated):
                return self.fail("Group update failed")
            return self.ok("Entity removed from group", {"entity": entity_name, "group": normalized_group})

        entity = runtime.world.get_entity_by_name(entity_name)
        if entity is None:
            return self.fail(f"Entity '{entity_name}' not found")
        runtime_groups = set(entity.groups)
        if normalized_group not in runtime_groups:
            return self.ok("Entity was not in group", {"entity": entity_name, "group": normalized_group})
        runtime_groups.discard(normalized_group)
        entity.groups = tuple(runtime_groups)
        return self.ok("Entity removed from group", {"entity": entity_name, "group": normalized_group})

    def get_entity_groups(self, entity_name: str) -> list[str]:
        """Lista los grupos de una entidad según el modo actual."""
        runtime = self.runtime
        if runtime is None or runtime.world is None:
            return []
        if self._is_edit_mode():
            groups = self._get_authoring_groups(entity_name)
            return groups or []
        entity = runtime.world.get_entity_by_name(entity_name)
        if entity is None:
            return []
        return list(entity.groups)

    def get_entities_in_group(self, group_name: str) -> list[str]:
        """Alias legible de get_group_entities."""
        return self.get_group_entities(group_name)

    # --- Servicios globales / autoloads ---

    def get_service(self, name: str) -> Optional[object]:
        """Obtiene un servicio global registrado en el runtime actual."""
        runtime = self.runtime
        if runtime is None:
            return None
        servicios = runtime.servicios
        if servicios is None:
            return None
        obtener = getattr(servicios, "obtener", None)
        if obtener is not None:
            return obtener(name)
        return None

    def has_service(self, name: str) -> bool:
        """Indica si existe un servicio global registrado en el runtime actual."""
        runtime = self.runtime
        if runtime is None:
            return False
        servicios = runtime.servicios
        if servicios is None:
            return False
        tiene = getattr(servicios, "tiene", None)
        if tiene is not None:
            return bool(tiene(name))
        return False

    def register_service_runtime(self, name: str, service: object) -> ActionResult:  # type: ignore[no-any-explicit]  # Servicio externo: tipo determinado en runtime
        """Registra un servicio para la sesión de PLAY actual."""
        runtime = self.runtime
        if runtime is None:
            return self.fail("Engine not initialized")
        servicios = runtime.servicios
        if servicios is None:
            return self.fail("Service registry unavailable")
        registrar = getattr(servicios, "registrar", None)
        if registrar is None:
            return self.fail("Service registry does not support runtime registration")
        registrar(name, service)
        return self.ok("Runtime service registered", {"name": name})

    def register_service_builtin(self, name: str, service: object) -> ActionResult:  # type: ignore[no-any-explicit]  # Servicio externo: tipo determinado en runtime
        """Registra un servicio builtin persistente entre sesiones de PLAY."""
        runtime = self.runtime
        if runtime is None:
            return self.fail("Engine not initialized")
        servicios = runtime.servicios
        if servicios is None:
            return self.fail("Service registry unavailable")
        registrar = getattr(servicios, "registrar_builtin", None)
        if registrar is None:
            return self.fail("Service registry does not support builtin registration")
        registrar(name, service)
        return self.ok("Builtin service registered", {"name": name})

    def shutdown(self) -> None:
        """Request a graceful engine shutdown, closing all systems and windows."""
        runtime = self.runtime
        if runtime is not None:
            runtime.request_shutdown()
