from __future__ import annotations

import json
from typing import Any, Callable, Dict, Optional

from engine.api._context import EngineAPIComponent
from engine.api.types import ActionResult, EngineStatus, EntityData
from engine.ecs.entity import normalize_entity_groups
from engine.events.signals import SignalConnectionFlags
from engine.physics.backend import PhysicsBackendInfo, PhysicsBackendSelection


class RuntimeAPI(EngineAPIComponent):
    """Runtime and inspection operations exposed through EngineAPI."""

    def play(self) -> None:
        runtime = self.runtime
        if runtime is not None:
            runtime.play()

    def stop(self) -> None:
        runtime = self.runtime
        if runtime is not None:
            runtime.stop()

    def set_seed(self, seed: int | None) -> ActionResult:
        runtime = self.runtime
        if runtime is None:
            return self.fail("Engine not initialized")
        runtime.set_seed(seed)
        return self.ok("Seed updated", {"seed": runtime.random_seed})

    def undo(self) -> ActionResult:
        runtime = self.runtime
        if runtime is None:
            return self.fail("Engine not initialized")
        success = runtime.undo()
        return self.ok("Undo applied") if success else self.fail("Undo unavailable")

    def redo(self) -> ActionResult:
        runtime = self.runtime
        if runtime is None:
            return self.fail("Engine not initialized")
        success = runtime.redo()
        return self.ok("Redo applied") if success else self.fail("Redo unavailable")

    def step(self, frames: int = 1) -> None:
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

    def get_recent_events(self, count: int = 50) -> list[Dict[str, Any]]:
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
        runtime = self.runtime
        if runtime is None or runtime.world is None:
            return []
        entities: list[EntityData] = []
        for entity in runtime.world.get_all_entities():
            if tag is not None and entity.tag != tag:
                continue
            if layer is not None and entity.layer != layer:
                continue
            if active is not None and entity.active != active:
                continue
            entities.append(self.get_entity(entity.name))
        return entities

    def get_entity(self, name: str) -> EntityData:
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
        from engine.components.inputmap import InputMap

        entity = self.require_entity(entity_name)
        input_map = entity.get_component(InputMap)
        if input_map is None:
            return {}
        return dict(input_map.last_state)

    def inject_input_state(self, entity_name: str, state: Dict[str, float], frames: int = 1) -> ActionResult:
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

    def get_audio_state(self, entity_name: str) -> Dict[str, Any]:
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

    def get_script_public_data(self, entity_name: str) -> Dict[str, Any]:
        from engine.components.scriptbehaviour import ScriptBehaviour

        entity = self.require_entity(entity_name)
        script_behaviour = entity.get_component(ScriptBehaviour)
        if script_behaviour is None:
            return {}
        return dict(script_behaviour.public_data)

    def query_physics_aabb(self, left: float, top: float, right: float, bottom: float) -> list[Dict[str, Any]]:
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
    ) -> list[Dict[str, Any]]:
        runtime = self.runtime
        if runtime is None:
            return []
        return runtime.query_physics_ray(origin_x, origin_y, direction_x, direction_y, max_distance)

    def list_physics_backends(self) -> list[PhysicsBackendInfo]:
        runtime = self.runtime
        if runtime is None:
            return []
        return runtime.list_physics_backends()

    def get_physics_backend_selection(self) -> PhysicsBackendSelection:
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

    def play_audio(self, entity_name: str) -> ActionResult:
        runtime = self.runtime
        if runtime is None or runtime.world is None or runtime.audio_system is None:
            return self.fail("Audio system not ready")
        success = runtime.audio_system.play(runtime.world, entity_name)
        return self.ok("Audio started", {"entity": entity_name}) if success else self.fail("Audio source not found or disabled")

    def stop_audio(self, entity_name: str) -> ActionResult:
        runtime = self.runtime
        if runtime is None or runtime.world is None or runtime.audio_system is None:
            return self.fail("Audio system not ready")
        success = runtime.audio_system.stop(runtime.world, entity_name)
        return self.ok("Audio stopped", {"entity": entity_name}) if success else self.fail("Audio source not found")

    def pause_audio(self, entity_name: str) -> ActionResult:
        runtime = self.runtime
        if runtime is None or runtime.world is None or runtime.audio_system is None:
            return self.fail("Audio system not ready")
        success = runtime.audio_system.pause(runtime.world, entity_name)
        return self.ok("Audio paused", {"entity": entity_name}) if success else self.fail("Audio source not found, disabled, or already paused")

    def resume_audio(self, entity_name: str) -> ActionResult:
        runtime = self.runtime
        if runtime is None or runtime.world is None or runtime.audio_system is None:
            return self.fail("Audio system not ready")
        success = runtime.audio_system.resume(runtime.world, entity_name)
        return self.ok("Audio resumed", {"entity": entity_name}) if success else self.fail("Audio source not found, disabled, or not paused")

    def get_group_entities(self, group_name: str) -> list[str]:
        runtime = self.runtime
        if runtime is None or runtime.world is None:
            return []
        ops = runtime.group_operations
        if ops is None:
            return []
        return [e.name for e in ops.get_entities(group_name)]

    def get_first_in_group(self, group_name: str) -> str | None:
        runtime = self.runtime
        if runtime is None or runtime.world is None:
            return None
        ops = runtime.group_operations
        if ops is None:
            return None
        ent = ops.get_first_entity(group_name)
        return ent.name if ent is not None else None

    def is_in_group(self, entity_name: str, group_name: str) -> bool:
        runtime = self.runtime
        if runtime is None or runtime.world is None:
            return False
        ops = runtime.group_operations
        if ops is None:
            return False
        return ops.has(group_name, entity_name)

    def count_group(self, group_name: str) -> int:
        runtime = self.runtime
        if runtime is None or runtime.world is None:
            return 0
        ops = runtime.group_operations
        if ops is None:
            return 0
        return ops.count(group_name)

    def call_group(self, group_name: str, method_name: str, *args: Any, **kwargs: Any) -> dict[str, Any]:
        runtime = self.runtime
        if runtime is None or runtime.world is None:
            return self.fail("Engine not initialized")
        ops = runtime.group_operations
        if ops is None:
            return self.fail("Group operations unavailable")
        invoked = ops.call_group(group_name, method_name, *args, **kwargs)
        return self.ok(
            f"Group call completed",
            {"group": group_name, "method": method_name, "invoked": invoked},
        )

    def emit_group(self, group_name: str, signal_name: str, *args: Any, **kwargs: Any) -> dict[str, Any]:
        runtime = self.runtime
        if runtime is None or runtime.world is None:
            return self.fail("Engine not initialized")
        ops = runtime.group_operations
        if ops is None:
            return self.fail("Group operations unavailable")
        total = ops.emit_group(group_name, signal_name, *args, **kwargs)
        return self.ok(
            f"Group emit completed",
            {"group": group_name, "signal": signal_name, "executed": total},
        )

    # --- Señales ---

    def connect_signal(
        self,
        source_id: str,
        signal_name: str,
        callback: Callable[..., Any],
        *,
        flags: list[str] | int | None = None,
        binds: tuple[Any, ...] | list[Any] | None = None,
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

    def emit_signal(self, source_id: str, signal_name: str, *args: Any, **kwargs: Any) -> int:
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
    ) -> list[dict[str, Any]]:
        """Lista conexiones runtime activas, opcionalmente filtradas."""
        runtime = self.runtime
        if runtime is None:
            return []
        signal_runtime = runtime.signal_runtime
        if signal_runtime is None:
            return []
        connections = signal_runtime.list_connections(source_id=source_id, signal_name=signal_name)
        result: list[dict[str, Any]] = []
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
        current = set(entity.groups)
        if normalized_group in current:
            return self.ok("Entity already in group", {"entity": entity_name, "group": normalized_group})
        current.add(normalized_group)
        entity.groups = tuple(current)
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
        current = set(entity.groups)
        if normalized_group not in current:
            return self.ok("Entity was not in group", {"entity": entity_name, "group": normalized_group})
        current.discard(normalized_group)
        entity.groups = tuple(current)
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

    def get_service(self, name: str) -> Any | None:
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

    def register_service_runtime(self, name: str, service: Any) -> ActionResult:
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

    def register_service_builtin(self, name: str, service: Any) -> ActionResult:
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
        runtime = self.runtime
        if runtime is not None:
            runtime.request_shutdown()
