"""Export runtime: centraliza carga de escenas, World, sistemas y game loop para export.

No usa EngineAPI, Game, RuntimeController, ni módulos de editor/inspector.
No persiste mutaciones runtime como authoring state.
"""

from __future__ import annotations

import sys
from typing import Any

from engine.ecs.world import World
from engine.events.event_bus import EventBus
from engine.levels.component_registry import ComponentRegistry
from engine.runtime.content_loader import ContentLoader
from engine.scenes.scene import Scene
from engine.systems.collision_system import CollisionSystem
from engine.systems.physics_system import PhysicsSystem


class ExportRuntime:
    """Runtime exportable que carga escenas, crea Worlds y ejecuta game loop."""

    def __init__(
        self,
        loader: ContentLoader,
        registry: ComponentRegistry,
        *,
        window_config: dict[str, Any] | None = None,
        gravity: float = 600.0,
    ) -> None:
        self._loader = loader
        self._registry = registry
        self._window_config = window_config or {}
        self._gravity = gravity
        self._world: World | None = None
        self._event_bus = EventBus()
        self._physics = PhysicsSystem(gravity=gravity)
        self._collision = CollisionSystem(event_bus=self._event_bus)
        self._current_scene_path: str | None = None
        self._frame_count: int = 0
        self._active: bool = True

    # ── properties ──────────────────────────────────────────────

    @property
    def world(self) -> World | None:
        return self._world

    @property
    def event_bus(self) -> EventBus:
        return self._event_bus

    @property
    def frame_count(self) -> int:
        return self._frame_count

    @property
    def current_scene_path(self) -> str | None:
        return self._current_scene_path

    @property
    def active(self) -> bool:
        return self._active

    # ── scene loading ───────────────────────────────────────────

    def load_scene(self, scene_path: str) -> bool:
        """Carga una escena desde el content pack y crea un World nuevo."""
        scene_data = self._loader.load_scene_json(scene_path)
        if scene_data is None:
            print(f"[ExportRuntime] Scene not found: {scene_path}", file=sys.stderr)
            return False

        scene = Scene(name=scene_path, data=scene_data, source_path=scene_path)
        try:
            self._world = scene.create_world(self._registry)
            self._current_scene_path = scene_path
            self._frame_count = 0
            self._event_bus.reset_frame_dedup()
            self._event_bus.emit("scene_loaded", {"scene_path": scene_path})
            return True
        except Exception as exc:
            print(f"[ExportRuntime] Failed to create world: {exc}", file=sys.stderr)
            return False

    # ── game loop ───────────────────────────────────────────────

    def run_frame(self, dt: float = 1.0 / 60.0) -> None:
        """Ejecuta un frame de simulación (física + colisiones)."""
        if not self._active or self._world is None:
            return
        self._event_bus.reset_frame_dedup()
        self._physics.update(self._world, dt)
        self._collision.update(self._world)
        self._frame_count += 1

    # ── events ──────────────────────────────────────────────────

    def get_events(self, count: int = 10) -> list[Any]:
        """Devuelve eventos recientes del EventBus."""
        return self._event_bus.get_recent_events(count)

    def get_recent_events(self, count: int = 10) -> list[dict[str, Any]]:
        """Versión JSON-serializable de eventos recientes."""
        events = self._event_bus.get_recent_events(count)
        return [{"name": e.name, "data": e.data} for e in events]

    # ── lifecycle ───────────────────────────────────────────────

    def shutdown(self) -> None:
        """Apaga el runtime sin persistir estado."""
        self._active = False
        self._event_bus.emit("runtime_shutdown", {})
