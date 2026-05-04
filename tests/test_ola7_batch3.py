"""
tests/test_ola7_batch3.py - Tests for OLA7 batch 3: GPUParticles2D, Shadow2D, PerformanceMonitor.
"""

from __future__ import annotations

import math
import unittest
from unittest.mock import MagicMock, patch

from engine.components.gpu_particles_2d import GPUParticles2D
from engine.components.light_occluder_2d import LightOccluder2D
from engine.components.point_light_2d import PointLight2D
from engine.debug.performance_monitor import PerformanceMonitor
from engine.systems.gpu_particles_system import GPUParticlesSystem, _GPUAliveParticle
from engine.systems.light2d_system import Light2DSystem


# =============================================================================
# 1. PerformanceMonitor
# =============================================================================

class TestPerformanceMonitor(unittest.TestCase):
    def test_default_values(self) -> None:
        pm = PerformanceMonitor()
        self.assertEqual(pm.fps, 0.0)
        self.assertEqual(pm.frame_time, 0.0)
        self.assertEqual(pm.physics_time, 0.0)
        self.assertEqual(pm.render_time, 0.0)
        self.assertEqual(pm.process_time, 0.0)
        self.assertEqual(pm.entities_count, 0)
        self.assertEqual(pm.draw_calls, 0)

    def test_record_frame_updates_all_fields(self) -> None:
        pm = PerformanceMonitor()
        pm.record_frame(
            delta_time=0.016,
            physics_time=0.005,
            render_time=0.003,
            entities=42,
            draw_calls=10,
        )
        self.assertAlmostEqual(pm.frame_time, 16.0, places=1)
        self.assertAlmostEqual(pm.physics_time, 5.0, places=1)
        self.assertAlmostEqual(pm.render_time, 3.0, places=1)
        self.assertEqual(pm.entities_count, 42)
        self.assertEqual(pm.draw_calls, 10)
        self.assertGreater(pm.process_time, 0.0)

    def test_fps_calculation(self) -> None:
        pm = PerformanceMonitor()
        for _ in range(60):
            pm.record_frame(0.016, 0.005, 0.003, 10, 5)
        self.assertAlmostEqual(pm.fps, 62.5, delta=1.0)

    def test_rolling_buffer_limits_samples(self) -> None:
        pm = PerformanceMonitor()
        for i in range(100):
            pm.record_frame(0.01 + i * 0.0001, 0.005, 0.002, 5, 2)
        self.assertLessEqual(len(pm._frame_times), pm._max_samples)

    def test_get_report_structure(self) -> None:
        pm = PerformanceMonitor()
        pm.record_frame(0.016, 0.005, 0.003, 30, 7)
        report = pm.get_report()
        self.assertIn("fps", report)
        self.assertIn("frame_time_ms", report)
        self.assertIn("physics_time_ms", report)
        self.assertIn("render_time_ms", report)
        self.assertIn("process_time_ms", report)
        self.assertIn("entities", report)
        self.assertIn("draw_calls", report)

    def test_zero_dt_avoids_division_by_zero(self) -> None:
        pm = PerformanceMonitor()
        pm.record_frame(0.0, 0.0, 0.0, 0, 0)
        self.assertEqual(pm.fps, 0.0)


# =============================================================================
# 2. GPUParticles2D Component
# =============================================================================

class TestGPUParticles2D(unittest.TestCase):
    def test_default_values(self) -> None:
        comp = GPUParticles2D()
        self.assertTrue(comp.enabled)
        self.assertTrue(comp.emitting)
        self.assertEqual(comp.amount, 32)
        self.assertEqual(comp.lifetime, 1.0)
        self.assertEqual(comp.speed_scale, 1.0)
        self.assertFalse(comp.one_shot)
        self.assertEqual(comp.texture_path, "")
        self.assertEqual(comp.draw_order, "index")

    def test_clamp_amount(self) -> None:
        comp = GPUParticles2D(amount=0)
        self.assertEqual(comp.amount, 1)
        comp = GPUParticles2D(amount=-5)
        self.assertEqual(comp.amount, 1)

    def test_clamp_lifetime(self) -> None:
        comp = GPUParticles2D(lifetime=0.0)
        self.assertEqual(comp.lifetime, 0.01)

    def test_to_dict_from_dict_roundtrip(self) -> None:
        comp = GPUParticles2D(
            emitting=False,
            amount=64,
            lifetime=2.0,
            speed_scale=0.5,
            one_shot=True,
            preprocess=0.1,
            explosiveness=0.3,
            randomness=0.5,
            texture_path="res://fire.png",
            local_coords=False,
            draw_order="lifetime",
            fixed_fps=30,
            fract_delta=False,
            sub_emitter_path="res://spark.json",
        )
        data = comp.to_dict()
        restored = GPUParticles2D.from_dict(data)
        self.assertEqual(restored.emitting, comp.emitting)
        self.assertEqual(restored.amount, comp.amount)
        self.assertEqual(restored.lifetime, comp.lifetime)
        self.assertEqual(restored.speed_scale, comp.speed_scale)
        self.assertTrue(restored.one_shot)
        self.assertAlmostEqual(restored.preprocess, comp.preprocess)
        self.assertAlmostEqual(restored.explosiveness, comp.explosiveness)
        self.assertAlmostEqual(restored.randomness, comp.randomness)
        self.assertEqual(restored.texture_path, comp.texture_path)
        self.assertFalse(restored.local_coords)
        self.assertEqual(restored.draw_order, "lifetime")
        self.assertEqual(restored.fixed_fps, 30)
        self.assertFalse(restored.fract_delta)
        self.assertEqual(restored.sub_emitter_path, comp.sub_emitter_path)

    def test_invalid_draw_order_falls_back_to_index(self) -> None:
        comp = GPUParticles2D(draw_order="invalid")
        self.assertEqual(comp.draw_order, "index")
        comp = GPUParticles2D(draw_order="lifetime")
        self.assertEqual(comp.draw_order, "lifetime")
        comp = GPUParticles2D(draw_order="reverse_lifetime")
        self.assertEqual(comp.draw_order, "reverse_lifetime")


# =============================================================================
# 3. GPUParticlesSystem
# =============================================================================

class TestGPUParticlesSystem(unittest.TestCase):
    def setUp(self) -> None:
        self.system = GPUParticlesSystem()

    def test_initial_state(self) -> None:
        self.assertEqual(self.system.active_particle_count, 0)
        self.assertEqual(self.system.total_particle_count, 0)

    def test_clear_resets_pool(self) -> None:
        self.system._pool.append(_GPUAliveParticle())
        self.system._pool[-1].active = True
        self.system.clear()
        self.assertEqual(self.system.total_particle_count, 0)
        self.assertEqual(len(self.system._emission_accum), 0)
        self.assertEqual(len(self.system._burst_fired), 0)

    def test_active_particle_count(self) -> None:
        p1 = _GPUAliveParticle()
        p1.active = True
        p2 = _GPUAliveParticle()
        p2.active = False
        self.system._pool = [p1, p2]
        self.assertEqual(self.system.active_particle_count, 1)

    def test_total_particle_count(self) -> None:
        self.system._pool = [_GPUAliveParticle(), _GPUAliveParticle()]
        self.assertEqual(self.system.total_particle_count, 2)


# =============================================================================
# 4. Shadow Volume Computation
# =============================================================================

class TestShadowVolume(unittest.TestCase):
    def test_compute_shadow_volume_returns_vectors(self) -> None:
        volume = Light2DSystem._compute_shadow_volume(
            light_x=100.0,
            light_y=50.0,
            occluder_aabb=(150.0, 80.0, 182.0, 112.0),
            radius=200.0,
        )
        self.assertGreaterEqual(len(volume), 2)
        for v in volume:
            self.assertIsNotNone(v.x)
            self.assertIsNotNone(v.y)

    def test_compute_shadow_volume_coincident_light(self) -> None:
        volume = Light2DSystem._compute_shadow_volume(
            light_x=150.0,
            light_y=80.0,
            occluder_aabb=(150.0, 80.0, 182.0, 112.0),
            radius=200.0,
        )
        self.assertEqual(len(volume), 4)  # one corner skipped (coincident), 3 projected + first corner

    def test_compute_shadow_volume_all_coincident(self) -> None:
        volume = Light2DSystem._compute_shadow_volume(
            light_x=0.0,
            light_y=0.0,
            occluder_aabb=(0.0, 0.0, 0.0, 0.0),
            radius=200.0,
        )
        self.assertEqual(len(volume), 0)


# =============================================================================
# 5. PointLight2D Shadow Fields
# =============================================================================

class TestPointLight2DShadow(unittest.TestCase):
    def test_default_shadow_disabled(self) -> None:
        light = PointLight2D()
        self.assertFalse(light.shadow_enabled)
        self.assertEqual(light.shadow_color, (0, 0, 0, 100))
        self.assertEqual(light.shadow_filter, "none")

    def test_shadow_enabled_serialization(self) -> None:
        light = PointLight2D(shadow_enabled=True, shadow_color=(10, 20, 30, 80))
        data = light.to_dict()
        self.assertTrue(data["shadow_enabled"])
        self.assertEqual(data["shadow_color"], [10, 20, 30, 80])
        restored = PointLight2D.from_dict(data)
        self.assertTrue(restored.shadow_enabled)
        self.assertEqual(restored.shadow_color, (10, 20, 30, 80))

    def test_shadow_filter_validation(self) -> None:
        light = PointLight2D(shadow_filter="pcf5")
        self.assertEqual(light.shadow_filter, "pcf5")
        light = PointLight2D(shadow_filter="invalid_filter")
        self.assertEqual(light.shadow_filter, "none")


# =============================================================================
# 6. LightOccluder2D Bounds
# =============================================================================

class TestLightOccluder2D(unittest.TestCase):
    def test_get_bounds_box(self) -> None:
        occluder = LightOccluder2D(shape="box", width=32.0, height=48.0)
        bounds = occluder.get_bounds(10.0, 20.0)
        self.assertEqual(bounds, (10.0, 20.0, 42.0, 68.0))

    def test_get_bounds_default(self) -> None:
        occluder = LightOccluder2D(shape="box")
        bounds = occluder.get_bounds()
        self.assertEqual(bounds, (0.0, 0.0, 32.0, 32.0))

    def test_toggle_enabled(self) -> None:
        occluder = LightOccluder2D(enabled=False)
        self.assertFalse(occluder.enabled)


if __name__ == "__main__":
    unittest.main()
