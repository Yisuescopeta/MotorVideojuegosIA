from __future__ import annotations

import json
from typing import Any, Dict, Optional

from engine.api._context import EngineAPIComponent
from engine.api.types import ActionResult, EngineStatus, EntityData
from engine.physics.backend import PhysicsBackendInfo, PhysicsBackendSelection


class RuntimeAPI(EngineAPIComponent):
    """Runtime and inspection operations exposed through EngineAPI."""

    def play(self) -> None:
        if self.game is not None:
            self.game.play()

    def stop(self) -> None:
        if self.game is not None:
            self.game.stop()

    def set_seed(self, seed: int | None) -> ActionResult:
        if self.game is None:
            return self.fail("Engine not initialized")
        self.game.set_seed(seed)
        return self.ok("Seed updated", {"seed": self.game.random_seed})

    def undo(self) -> ActionResult:
        if self.game is None:
            return self.fail("Engine not initialized")
        success = self.game.undo()
        return self.ok("Undo applied") if success else self.fail("Undo unavailable")

    def redo(self) -> ActionResult:
        if self.game is None:
            return self.fail("Engine not initialized")
        success = self.game.redo()
        return self.ok("Redo applied") if success else self.fail("Redo unavailable")

    def step(self, frames: int = 1) -> None:
        if self.game is None:
            return
        if hasattr(self.game, "step_frame"):
            for _ in range(frames):
                self.game.step_frame()
            return
        if hasattr(self.game, "step"):
            for _ in range(frames):
                self.game.step()

    def get_recent_events(self, count: int = 50) -> list[Dict[str, Any]]:
        if self.game is None or self.game.event_bus is None:
            return []
        limit = max(0, int(count))
        events = self.game.event_bus.get_recent_events(limit)
        return [
            {
                "name": str(event.name),
                "data": json.loads(json.dumps(event.data, ensure_ascii=True, default=str)),
            }
            for event in events
        ]

    def get_status(self) -> EngineStatus:
        if self.game is None:
            raise RuntimeError("Engine not initialized")
        world = self.game.world
        return {
            "state": str(self.game.state),
            "frame": self.game.time.frame_count,
            "time": self.game.time.total_time,
            "fps": self.game.time.fps,
            "entity_count": world.entity_count() if world else 0,
        }

    def list_entities(
        self,
        tag: Optional[str] = None,
        layer: Optional[str] = None,
        active: Optional[bool] = None,
    ) -> list[EntityData]:
        if self.game is None or self.game.world is None:
            return []
        entities: list[EntityData] = []
        for entity in self.game.world.get_all_entities():
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
        if self.game is None or self.game.world is None:
            return None
        from engine.components.camera2d import Camera2D
        from engine.components.transform import Transform

        for entity in self.game.world.get_entities_with(Transform, Camera2D):
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
        if self.game is None:
            return self.fail("Engine not initialized")
        if self.game.input_system is None:
            return self.fail("Input system not ready")
        normalized_name = str(entity_name).strip()
        if not normalized_name:
            return self.fail("Entity name is required")
        normalized_frames = max(1, int(frames))
        self.game.input_system.inject_state(normalized_name, dict(state), frames=normalized_frames)
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

        if self.game is None or self.game.world is None:
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
        if self.game is None:
            return []
        return self.game.query_physics_aabb(left, top, right, bottom)

    def query_physics_ray(
        self,
        origin_x: float,
        origin_y: float,
        direction_x: float,
        direction_y: float,
        max_distance: float,
    ) -> list[Dict[str, Any]]:
        if self.game is None:
            return []
        return self.game.query_physics_ray(origin_x, origin_y, direction_x, direction_y, max_distance)

    def list_physics_backends(self) -> list[PhysicsBackendInfo]:
        if self.game is None:
            return []
        return self.game.list_physics_backends()

    def get_physics_backend_selection(self) -> PhysicsBackendSelection:
        if self.game is None:
            return {
                "requested_backend": "legacy_aabb",
                "effective_backend": None,
                "used_fallback": False,
                "fallback_reason": None,
                "unavailable_reason": "Engine not initialized",
            }
        return self.game.get_physics_backend_selection()

    def play_audio(self, entity_name: str) -> ActionResult:
        if self.game is None or self.game.world is None or self.game.audio_system is None:
            return self.fail("Audio system not ready")
        success = self.game.audio_system.play(self.game.world, entity_name)
        return self.ok("Audio started", {"entity": entity_name}) if success else self.fail("Audio source not found or disabled")

    def stop_audio(self, entity_name: str) -> ActionResult:
        if self.game is None or self.game.world is None or self.game.audio_system is None:
            return self.fail("Audio system not ready")
        success = self.game.audio_system.stop(self.game.world, entity_name)
        return self.ok("Audio stopped", {"entity": entity_name}) if success else self.fail("Audio source not found")

    def pause_audio(self, entity_name: str) -> ActionResult:
        if self.game is None or self.game.world is None or self.game.audio_system is None:
            return self.fail("Audio system not ready")
        success = self.game.audio_system.pause(self.game.world, entity_name)
        return self.ok("Audio paused", {"entity": entity_name}) if success else self.fail("Audio source not found, disabled, or already paused")

    def resume_audio(self, entity_name: str) -> ActionResult:
        if self.game is None or self.game.world is None or self.game.audio_system is None:
            return self.fail("Audio system not ready")
        success = self.game.audio_system.resume(self.game.world, entity_name)
        return self.ok("Audio resumed", {"entity": entity_name}) if success else self.fail("Audio source not found, disabled, or not paused")

    def shutdown(self) -> None:
        if self.game is not None:
            self.game.request_shutdown()
