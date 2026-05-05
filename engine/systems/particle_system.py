"""
engine/systems/particle_system.py - Sistema de particulas CPU 2D.

Gestiona emision, actualizacion y renderizado de particulas.
"""

from __future__ import annotations

import math
import random
from typing import TYPE_CHECKING, Dict, List, Optional, Tuple

import pyray as rl
from engine.components.particle_emitter2d import ColorRampStop, ParticleEmitter2D
from engine.components.transform import Transform

if TYPE_CHECKING:
    from engine.ecs.world import World
    from engine.events.event_bus import EventBus


class _Particle:
    """Estado runtime de una particula individual."""
    __slots__ = (
        "x", "y", "vx", "vy", "rotation", "ang_vel",
        "scale", "cr", "cg", "cb", "ca",
        "lifetime", "age", "active", "emitter_seed",
    )

    def __init__(self) -> None:
        self.x: float = 0.0
        self.y: float = 0.0
        self.vx: float = 0.0
        self.vy: float = 0.0
        self.rotation: float = 0.0
        self.ang_vel: float = 0.0
        self.scale: float = 1.0
        self.cr: int = 255
        self.cg: int = 255
        self.cb: int = 255
        self.ca: int = 255
        self.lifetime: float = 1.0
        self.age: float = 0.0
        self.active: bool = False
        self.emitter_seed: int = 0


def _rand_range(a: float, b: float) -> float:
    if a == b:
        return a
    lo = min(a, b)
    hi = max(a, b)
    return lo + random.random() * (hi - lo)


def _is_window_ready() -> bool:
    return bool(hasattr(rl, "is_window_ready") and rl.is_window_ready())


class ParticleSystem:
    """Sistema de particulas 2D calculadas en CPU."""

    POOL_GROWTH = 64
    MAX_POOL = 32768

    def __init__(self, event_bus: Optional["EventBus"] = None) -> None:
        self._event_bus = event_bus
        self._pool: List[_Particle] = []
        self._preprocessed: Dict[int, bool] = {}
        self._emission_accum: Dict[int, float] = {}
        self._finished_fired: Dict[int, bool] = {}

    def set_event_bus(self, event_bus: "EventBus") -> None:
        self._event_bus = event_bus

    def update(self, world: "World", dt: float) -> None:
        entities = world.get_entities_with(ParticleEmitter2D, Transform)

        for entity in entities:
            emitter = entity.get_component(ParticleEmitter2D)
            transform = entity.get_component(Transform)
            if emitter is None or transform is None or not emitter.enabled:
                continue
            if not transform.enabled:
                continue

            seed = emitter.seed if emitter.seed else hash(entity.name) & 0x7FFFFFFF

            self._handle_preprocess(emitter, transform, seed)
            self._emit(emitter, transform, seed, dt)
            self._update_particles(emitter, seed, dt)
            self._check_finished(emitter, seed, entity.name)

        self._pool = [p for p in self._pool if p.active]

    def _handle_preprocess(self, emitter: ParticleEmitter2D, transform: Transform, seed: int) -> None:
        if emitter.preprocess <= 0.0 or self._preprocessed.get(seed, False):
            return
        self._preprocessed[seed] = True

        steps = int(emitter.preprocess * 60.0)
        substep = 1.0 / 60.0
        for _ in range(steps):
            self._emit(emitter, transform, seed, substep)
            self._update_particles(emitter, seed, substep)

    def _emit(self, emitter: ParticleEmitter2D, transform: Transform, seed: int, dt: float) -> None:
        if not emitter.emitting:
            return
        if emitter.lifetime <= 0:
            return

        effective_dt = dt * emitter.speed_scale

        if emitter.one_shot or emitter.explosiveness >= 1.0:
            acc_val = self._emission_accum.get(seed, 0.0)
            if acc_val == 0.0:
                burst = emitter.amount
                for _ in range(burst):
                    self._spawn(emitter, transform, seed)
                self._emission_accum[seed] = -1.0
            return

        pps = float(emitter.amount) / emitter.lifetime
        if emitter.explosiveness > 0:
            pps *= (1.0 + emitter.explosiveness * 9.0)

        acc = self._emission_accum.get(seed, 0.0)
        acc += pps * effective_dt
        count = int(acc)
        if count > 0:
            self._emission_accum[seed] = acc - float(count)
            for _ in range(count):
                self._spawn(emitter, transform, seed)
        else:
            self._emission_accum[seed] = acc

    def _spawn(self, emitter: ParticleEmitter2D, transform: Transform, seed: int) -> None:
        px = transform.x
        py = transform.y

        shape = emitter.emission_shape
        if shape == "rectangle":
            px += _rand_range(-emitter.emission_rect_extents[0] * 0.5, emitter.emission_rect_extents[0] * 0.5)
            py += _rand_range(-emitter.emission_rect_extents[1] * 0.5, emitter.emission_rect_extents[1] * 0.5)
        elif shape == "sphere":
            angle = random.random() * math.pi * 2.0
            r = emitter.emission_sphere_radius * math.sqrt(random.random())
            px += math.cos(angle) * r
            py += math.sin(angle) * r
        elif shape == "sphere_surface":
            angle = random.random() * math.pi * 2.0
            r = emitter.emission_sphere_radius
            px += math.cos(angle) * r
            py += math.sin(angle) * r

        base_rad = math.atan2(emitter.direction[1], emitter.direction[0])
        half_spread = math.radians(max(0.0, emitter.spread) * 0.5)
        dir_rad = _rand_range(base_rad - half_spread, base_rad + half_spread)
        dir_x = math.cos(dir_rad)
        dir_y = math.sin(dir_rad)

        vel_mag = _rand_range(emitter.initial_velocity[0], emitter.initial_velocity[1])
        vx = dir_x * vel_mag
        vy = dir_y * vel_mag

        rotation = _rand_range(emitter.angle[0], emitter.angle[1])
        ang_vel = _rand_range(emitter.angular_velocity[0], emitter.angular_velocity[1])
        scale_val = max(0.01, _rand_range(emitter.scale_amount[0], emitter.scale_amount[1]))

        lifetime_val = _rand_range(
            emitter.lifetime * (1.0 - emitter.lifetime_randomness),
            emitter.lifetime,
        )
        lifetime_val = max(0.001, lifetime_val)

        p = self._alloc()
        p.x = px
        p.y = py
        p.vx = vx
        p.vy = vy
        p.rotation = rotation
        p.ang_vel = ang_vel
        p.scale = scale_val
        p.cr = emitter.color[0]
        p.cg = emitter.color[1]
        p.cb = emitter.color[2]
        p.ca = emitter.color[3]
        p.lifetime = lifetime_val
        p.age = 0.0
        p.active = True
        p.emitter_seed = seed

    def _alloc(self) -> _Particle:
        for p in self._pool:
            if not p.active:
                p.active = False
                return p
        if len(self._pool) >= self.MAX_POOL:
            oldest = self._pool[0]
            oldest.active = False
            return oldest
        new_count = min(len(self._pool) + self.POOL_GROWTH, self.MAX_POOL)
        while len(self._pool) < new_count:
            self._pool.append(_Particle())
        return self._pool[-1]

    def _update_particles(self, emitter: ParticleEmitter2D, seed: int, dt: float) -> None:
        effective_dt = dt * emitter.speed_scale

        for p in self._pool:
            if not p.active or p.emitter_seed != seed:
                continue

            p.age += effective_dt
            if p.age >= p.lifetime:
                p.active = False
                continue

            t_life = p.age / p.lifetime if p.lifetime > 0 else 0.5

            damp = emitter.damping[0] + (emitter.damping[1] - emitter.damping[0]) * t_life
            p.vx *= (1.0 - damp * effective_dt)
            p.vy *= (1.0 - damp * effective_dt)

            lin_x = emitter.linear_accel[0] + (emitter.linear_accel[1] - emitter.linear_accel[0]) * t_life
            lin_y = emitter.linear_accel[0] + (emitter.linear_accel[1] - emitter.linear_accel[0]) * t_life
            p.vx += lin_x * effective_dt
            p.vy += lin_y * effective_dt

            p.vx += emitter.gravity[0] * effective_dt
            p.vy += emitter.gravity[1] * effective_dt

            p.x += p.vx * effective_dt
            p.y += p.vy * effective_dt

            ang_v = emitter.angular_velocity[0] + (emitter.angular_velocity[1] - emitter.angular_velocity[0]) * t_life
            p.rotation += ang_v * effective_dt

            if emitter.color_ramp:
                c = self.sample_ramp(emitter.color_ramp, t_life)
                if c is not None:
                    p.cr, p.cg, p.cb, p.ca = c

    @staticmethod
    def sample_ramp(ramp: List[ColorRampStop], t: float) -> Optional[Tuple[int, int, int, int]]:
        if not ramp:
            return None
        sorted_ramp = sorted(ramp, key=lambda s: s.position)
        if t <= sorted_ramp[0].position:
            return sorted_ramp[0].color
        if t >= sorted_ramp[-1].position:
            return sorted_ramp[-1].color
        for i in range(len(sorted_ramp) - 1):
            a = sorted_ramp[i]
            b = sorted_ramp[i + 1]
            if a.position <= t <= b.position:
                if a.position == b.position:
                    return a.color
                ratio = (t - a.position) / (b.position - a.position)
                return (
                    int(a.color[0] + (b.color[0] - a.color[0]) * ratio),
                    int(a.color[1] + (b.color[1] - a.color[1]) * ratio),
                    int(a.color[2] + (b.color[2] - a.color[2]) * ratio),
                    int(a.color[3] + (b.color[3] - a.color[3]) * ratio),
                )
        return sorted_ramp[-1].color

    def _check_finished(self, emitter: ParticleEmitter2D, seed: int, entity_name: str) -> None:
        if not emitter.one_shot:
            return
        if self._finished_fired.get(seed, False):
            return
        alive = sum(1 for p in self._pool if p.active and p.emitter_seed == seed)
        if alive == 0:
            self._finished_fired[seed] = True
            if self._event_bus is not None:
                self._event_bus.emit("on_particle_finished", {
                    "entity": entity_name,
                    "entity_id": seed,
                })

    def render(self, world: "World") -> None:
        _ = world
        if not _is_window_ready():
            return

        for p in self._pool:
            if not p.active:
                continue
            size = max(1.0, p.scale * 4.0)
            half = size * 0.5
            dest = rl.Rectangle(p.x - half, p.y - half, size, size)
            origin = rl.Vector2(half, half)
            rotation_deg = p.rotation * 180.0 / math.pi
            color = rl.Color(
                max(0, min(255, p.cr)),
                max(0, min(255, p.cg)),
                max(0, min(255, p.cb)),
                max(0, min(255, p.ca)),
            )
            rl.draw_rectangle_pro(dest, origin, rotation_deg, color)

    def clear(self) -> None:
        self._pool.clear()
        self._preprocessed.clear()
        self._emission_accum.clear()
        self._finished_fired.clear()

    @property
    def active_particle_count(self) -> int:
        return sum(1 for p in self._pool if p.active)

    @property
    def total_particle_count(self) -> int:
        return len(self._pool)
