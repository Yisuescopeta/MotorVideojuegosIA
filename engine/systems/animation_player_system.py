"""
engine/systems/animation_player_system.py - AnimationPlayerSystem.

Evalua AnimationResources y aplica tracks de propiedades a entidades
con AnimationPlayer2D.
"""

from __future__ import annotations

import json
import os
from typing import Any

from engine.components.animation_player_2d import AnimationPlayer2D
from engine.components.sprite import Sprite
from engine.components.transform import Transform
from engine.ecs.entity import Entity
from engine.ecs.world import World


class AnimationPlayerSystem:
    """Evalua AnimationResources y aplica tracks de propiedades a entidades."""

    DEFAULT_COMPONENT_MAP: dict[str, type] = {
        "Transform": Transform,
        "Sprite": Sprite,
    }

    def __init__(self, component_map: dict[str, type] | None = None) -> None:
        self._component_map: dict[str, type] = (
            dict(component_map) if component_map is not None else dict(self.DEFAULT_COMPONENT_MAP)
        )

    def register_component(self, name: str, comp_class: type) -> None:
        """Registra un nuevo tipo de componente para animacion."""
        self._component_map[name] = comp_class

    def update(self, world: World, dt: float) -> None:
        """Actualiza todas las animaciones activas."""
        for entity in world.get_entities_with(AnimationPlayer2D):
            player = entity.get_component(AnimationPlayer2D)
            if player is None or not player.enabled or not player._is_playing:
                continue

            # Cargar recurso (con cache)
            if player._resource_cache is None and player.animation_resource_path:
                try:
                    with open(player.animation_resource_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    from engine.resources.animation_resource import AnimationResource

                    player._resource_cache = AnimationResource.from_dict(data)
                except Exception:
                    continue

            resource = player._resource_cache
            if resource is None:
                continue

            # Avanzar tiempo
            player._playback_time += dt * player.playback_speed
            if player._playback_time >= resource.length:
                if resource.loop:
                    player._playback_time = player._playback_time % resource.length
                else:
                    player._playback_time = resource.length
                    player._is_playing = False

            # Aplicar tracks
            t = player._playback_time
            for track in resource.tracks:
                value = self._evaluate_track(track, t)
                if value is not None:
                    self._apply_property(entity, track.property_path, value)

    def _evaluate_track(self, track: Any, time: float) -> Any:
        """Interpola keyframes para obtener el valor en el tiempo dado."""
        keyframes = sorted(track.keyframes, key=lambda k: k.get("time", 0))
        if not keyframes:
            return None

        # Encontrar keyframes que rodean el tiempo
        prev_kf = None
        next_kf = None
        for kf in keyframes:
            kf_time = kf.get("time", 0)
            if kf_time <= time:
                prev_kf = kf
            if kf_time >= time and next_kf is None:
                next_kf = kf

        if prev_kf is None:
            return next_kf.get("value") if next_kf else None
        if next_kf is None:
            return prev_kf.get("value")
        if prev_kf == next_kf:
            return prev_kf.get("value")

        # Interpolar
        t0: float = prev_kf.get("time", 0)
        t1: float = next_kf.get("time", 0)
        if t1 == t0:
            return prev_kf.get("value")

        alpha = (time - t0) / (t1 - t0)
        v0 = prev_kf.get("value")
        v1 = next_kf.get("value")

        interp = track.interpolation
        if interp == "step":
            return v0
        elif interp == "cubic":
            # Smooth step
            alpha = alpha * alpha * (3 - 2 * alpha)

        # linear (default): lerp
        if isinstance(v0, (int, float)) and isinstance(v1, (int, float)):
            return v0 + (v1 - v0) * alpha
        elif isinstance(v0, list) and isinstance(v1, list):
            return [v0[i] + (v1[i] - v0[i]) * alpha for i in range(min(len(v0), len(v1)))]
        return v0

    def _apply_property(self, entity: Entity, property_path: str, value: Any) -> None:
        """Aplica un valor a una propiedad de componente de la entidad."""
        parts = property_path.split(".")
        if len(parts) < 2:
            return

        component_name = parts[0]
        comp_class = self._component_map.get(component_name)
        if comp_class is None:
            return

        component = entity.get_component(comp_class)
        if component is None:
            return

        prop_path = parts[1:]

        if len(prop_path) == 1:
            prop = prop_path[0]
            if hasattr(component, prop):
                setattr(component, prop, value)
        elif len(prop_path) == 2:
            parent = prop_path[0]
            child = prop_path[1]
            if hasattr(component, parent):
                parent_val = getattr(component, parent)
                if isinstance(parent_val, (list, tuple)):
                    idx_map = {"x": 0, "y": 1, "r": 0, "g": 1, "b": 2, "a": 3}
                    idx = idx_map.get(child)
                    if idx is not None and idx < len(parent_val):
                        new_val = list(parent_val)
                        new_val[idx] = value
                        setattr(component, parent, tuple(new_val))
