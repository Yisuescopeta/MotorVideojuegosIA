"""
engine/systems/gpu_particles_system.py - GPU-accelerated particle rendering using batched raylib DrawTexturePro.
"""

from __future__ import annotations

import math
import random
from typing import TYPE_CHECKING, Optional

import pyray as rl

from engine.components.gpu_particles_2d import GPUParticles2D
from engine.components.transform import Transform

if TYPE_CHECKING:
    from engine.ecs.world import World


class _GPUAliveParticle:
    """Runtime state for a GPU-driven particle."""

    __slots__ = (
        "x", "y", "vx", "vy",
        "rotation", "ang_vel",
        "size", "scale",
        "r", "g", "b",
        "age", "lifetime",
        "active",
    )

    def __init__(self) -> None:
        self.x: float = 0.0
        self.y: float = 0.0
        self.vx: float = 0.0
        self.vy: float = 0.0
        self.rotation: float = 0.0
        self.ang_vel: float = 0.0
        self.size: float = 4.0
        self.scale: float = 1.0
        self.r: int = 255
        self.g: int = 255
        self.b: int = 255
        self.age: float = 0.0
        self.lifetime: float = 1.0
        self.active: bool = False


def _is_window_ready() -> bool:
    return bool(hasattr(rl, "is_window_ready") and rl.is_window_ready())


class GPUParticlesSystem:
    """GPU-accelerated particle rendering using batched raylib DrawTexturePro.

    When both GPUParticles2D and ParticleEmitter2D exist on an entity,
    GPUParticles2D takes precedence.
    """

    POOL_GROWTH = 64
    MAX_POOL = 16384

    def __init__(self) -> None:
        self._pool: list[_GPUAliveParticle] = []
        self._texture_cache: dict[str, Optional[rl.Texture2D]] = {}
        self._emission_accum: dict[int, float] = {}
        self._burst_fired: dict[int, bool] = {}

    def _get_texture(self, texture_path: str) -> Optional[rl.Texture2D]:
        if not texture_path or not _is_window_ready():
            return None
        if texture_path not in self._texture_cache:
            try:
                if hasattr(rl, "load_texture"):
                    tex = rl.load_texture(texture_path)
                    if tex and getattr(tex, "id", 0) > 0:
                        self._texture_cache[texture_path] = tex
                    else:
                        self._texture_cache[texture_path] = None
                else:
                    self._texture_cache[texture_path] = None
            except Exception:
                self._texture_cache[texture_path] = None
        return self._texture_cache.get(texture_path)

    def _ensure_pool(self, comp: GPUParticles2D) -> None:
        needed = comp.amount
        available = sum(1 for p in self._pool if p.active)
        if available >= needed:
            return
        to_add = min(needed - available, self.POOL_GROWTH)
        for _ in range(to_add):
            if len(self._pool) >= self.MAX_POOL:
                break
            self._pool.append(_GPUAliveParticle())

    def _spawn_particles(self, comp: GPUParticles2D, x: float, y: float, seed: int) -> None:
        import random as _random
        rng = _random.Random(seed + len([p for p in self._pool if p.active]))

        count = comp.amount
        for _ in range(count):
            p = self._alloc_particle()
            if p is None:
                break

            p.x = x + rng.uniform(-10.0, 10.0) * comp.randomness
            p.y = y + rng.uniform(-10.0, 10.0) * comp.randomness

            angle = rng.uniform(0, math.pi * 2)
            speed = rng.uniform(50.0, 150.0) * comp.speed_scale
            p.vx = math.cos(angle) * speed
            p.vy = math.sin(angle) * speed - rng.uniform(20.0, 60.0)
            p.rotation = rng.uniform(0, 360) * math.pi / 180.0
            p.ang_vel = rng.uniform(-2.0, 2.0)
            p.size = rng.uniform(2.0, 8.0)
            p.scale = rng.uniform(0.5, 1.5)
            p.r = rng.randint(180, 255)
            p.g = rng.randint(100, 200)
            p.b = rng.randint(50, 150)
            p.age = 0.0
            p.lifetime = comp.lifetime * (1.0 - rng.uniform(0.0, comp.randomness))
            p.lifetime = max(0.05, p.lifetime)
            p.active = True

    def _alloc_particle(self) -> Optional[_GPUAliveParticle]:
        for p in self._pool:
            if not p.active:
                return p
        if len(self._pool) >= self.MAX_POOL:
            return None
        for _ in range(min(self.POOL_GROWTH, self.MAX_POOL - len(self._pool))):
            self._pool.append(_GPUAliveParticle())
        return self._pool[-1]

    def _update_particles(self, comp: GPUParticles2D, dt: float) -> None:
        effective_dt = dt * comp.speed_scale
        for p in self._pool:
            if not p.active:
                continue
            p.age += effective_dt
            if p.age >= p.lifetime:
                p.active = False
                continue

            p.vy += 80.0 * effective_dt  # gravity
            p.x += p.vx * effective_dt
            p.y += p.vy * effective_dt
            p.rotation += p.ang_vel * effective_dt

    def _render_particles(self, comp: GPUParticles2D) -> None:
        if not _is_window_ready():
            return

        texture = None
        if comp.texture_path:
            texture = self._get_texture(comp.texture_path)

        if texture is not None and getattr(texture, "id", 0) > 0:
            for p in self._pool:
                if not p.active:
                    continue
                alpha = int(255 * max(0.0, 1.0 - p.age / p.lifetime))
                color = rl.Color(p.r, p.g, p.b, alpha)
                src = rl.Rectangle(0, 0, texture.width, texture.height)
                dest = rl.Rectangle(p.x, p.y, p.size * p.scale, p.size * p.scale)
                origin = rl.Vector2(p.size * p.scale * 0.5, p.size * p.scale * 0.5)
                rl.draw_texture_pro(texture, src, dest, origin, p.rotation * 180.0 / math.pi, color)
        else:
            for p in self._pool:
                if not p.active:
                    continue
                alpha = int(255 * max(0.0, 1.0 - p.age / p.lifetime))
                color = rl.Color(p.r, p.g, p.b, alpha)
                half = p.size * p.scale * 0.5
                dest = rl.Rectangle(p.x - half, p.y - half, p.size * p.scale, p.size * p.scale)
                origin = rl.Vector2(half, half)
                rl.draw_rectangle_pro(dest, origin, p.rotation * 180.0 / math.pi, color)

    def update(self, world: "World", dt: float) -> None:
        entities = world.get_entities_with(GPUParticles2D, Transform)

        for entity in entities:
            gpu_particles = entity.get_component(GPUParticles2D)
            transform = entity.get_component(Transform)
            if gpu_particles is None or transform is None or not gpu_particles.enabled:
                continue
            if not transform.enabled:
                continue
            if not gpu_particles.emitting:
                continue

            seed = hash(entity.name) & 0x7FFFFFFF

            self._ensure_pool(gpu_particles)

            if gpu_particles.one_shot and not self._burst_fired.get(seed, False):
                self._spawn_particles(gpu_particles, transform.x, transform.y, seed)
                self._burst_fired[seed] = True
            elif not gpu_particles.one_shot:
                emission_rate = gpu_particles.amount / gpu_particles.lifetime
                acc = self._emission_accum.get(seed, 0.0)
                acc += emission_rate * dt * gpu_particles.speed_scale
                spawn_count = int(acc)
                if spawn_count > 0:
                    self._emission_accum[seed] = acc - float(spawn_count)
                    for _ in range(spawn_count):
                        self._spawn_particles(gpu_particles, transform.x, transform.y, seed)
                else:
                    self._emission_accum[seed] = acc

            self._update_particles(gpu_particles, dt)

    def render(self, world: "World") -> None:
        _ = world
        if not _is_window_ready():
            return
        entities = world.get_entities_with(GPUParticles2D, Transform)
        for entity in entities:
            gpu_particles = entity.get_component(GPUParticles2D)
            if gpu_particles is None or not gpu_particles.enabled or not gpu_particles.emitting:
                continue
            self._render_particles(gpu_particles)

    def clear(self) -> None:
        self._pool.clear()
        self._emission_accum.clear()
        self._burst_fired.clear()

    @property
    def active_particle_count(self) -> int:
        return sum(1 for p in self._pool if p.active)

    @property
    def total_particle_count(self) -> int:
        return len(self._pool)
