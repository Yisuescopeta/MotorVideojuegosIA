import unittest

from engine.components.remote_transform_2d import RemoteTransform2D
from engine.components.touch_screen_button import TouchScreenButton
from engine.components.gpu_particles_2d import GPUParticles2D
from engine.ecs.component import Component, ProcessMode
from engine.events.input_events import (
    InputEvent,
    InputEventKey,
    InputEventMouseButton,
    InputEventMouseMotion,
    InputEventJoypadButton,
    InputEventJoypadMotion,
    InputEventAction,
)
from engine.levels.component_registry import create_default_registry
from engine.resources.sprite_frames_resource import (
    SpriteFrame,
    SpriteAnimation,
    SpriteFrames,
)


class TestRemoteTransform2D(unittest.TestCase):
    def test_default_values(self) -> None:
        rt = RemoteTransform2D()
        self.assertEqual(rt.target_entity, "")
        self.assertTrue(rt.update_position)
        self.assertTrue(rt.update_rotation)
        self.assertTrue(rt.update_scale)
        self.assertTrue(rt.use_global_coordinates)
        self.assertTrue(rt.enabled)

    def test_serialization_roundtrip(self) -> None:
        rt = RemoteTransform2D(
            target_entity="Player",
            update_position=False,
            update_scale=False,
            use_global_coordinates=False,
        )
        data = rt.to_dict()
        restored = RemoteTransform2D.from_dict(data)
        self.assertEqual(restored.target_entity, "Player")
        self.assertFalse(restored.update_position)
        self.assertTrue(restored.update_rotation)
        self.assertFalse(restored.update_scale)
        self.assertFalse(restored.use_global_coordinates)


class TestTouchScreenButton(unittest.TestCase):
    def test_default_values(self) -> None:
        btn = TouchScreenButton()
        self.assertEqual(btn.action, "action_1")
        self.assertTrue(btn.visible)
        self.assertEqual(btn.shape, "rectangle")
        self.assertEqual(btn.shape_width, 64.0)
        self.assertFalse(btn.passby_press)
        self.assertTrue(btn.release_on_exit)

    def test_serialization_roundtrip(self) -> None:
        btn = TouchScreenButton(
            action="jump",
            shape="circle",
            shape_radius=48.0,
            passby_press=True,
            release_on_exit=False,
        )
        data = btn.to_dict()
        restored = TouchScreenButton.from_dict(data)
        self.assertEqual(restored.action, "jump")
        self.assertEqual(restored.shape, "circle")
        self.assertEqual(restored.shape_radius, 48.0)
        self.assertTrue(restored.passby_press)
        self.assertFalse(restored.release_on_exit)


class TestGPUParticles2D(unittest.TestCase):
    def test_default_values(self) -> None:
        gpu = GPUParticles2D()
        self.assertTrue(gpu.emitting)
        self.assertEqual(gpu.amount, 32)
        self.assertEqual(gpu.lifetime, 1.0)
        self.assertEqual(gpu.draw_order, "index")
        self.assertTrue(gpu.fract_delta)

    def test_serialization_roundtrip(self) -> None:
        gpu = GPUParticles2D(
            emitting=False,
            amount=16,
            draw_order="lifetime",
            fixed_fps=30,
        )
        data = gpu.to_dict()
        restored = GPUParticles2D.from_dict(data)
        self.assertFalse(restored.emitting)
        self.assertEqual(restored.amount, 16)
        self.assertEqual(restored.draw_order, "lifetime")
        self.assertEqual(restored.fixed_fps, 30)


class TestInputEvents(unittest.TestCase):
    def test_input_event_base(self) -> None:
        ev = InputEvent()
        self.assertEqual(ev.device, 0)

    def test_input_event_key(self) -> None:
        ev = InputEventKey(keycode=65, pressed=True, echo=False)
        self.assertEqual(ev.keycode, 65)
        self.assertTrue(ev.pressed)
        self.assertFalse(ev.echo)
        self.assertEqual(ev.device, 0)

    def test_input_event_mouse_button(self) -> None:
        ev = InputEventMouseButton(button_index=1, pressed=True, x=100.0, y=200.0)
        self.assertEqual(ev.button_index, 1)
        self.assertTrue(ev.pressed)
        self.assertEqual(ev.x, 100.0)
        self.assertEqual(ev.y, 200.0)

    def test_input_event_mouse_motion(self) -> None:
        ev = InputEventMouseMotion(x=50.0, y=60.0, relative_x=5.0, relative_y=-2.0)
        self.assertEqual(ev.relative_x, 5.0)
        self.assertEqual(ev.relative_y, -2.0)

    def test_input_event_joypad_button(self) -> None:
        ev = InputEventJoypadButton(button_index=0, pressed=True)
        self.assertTrue(ev.pressed)
        self.assertEqual(ev.button_index, 0)

    def test_input_event_joypad_motion(self) -> None:
        ev = InputEventJoypadMotion(axis=0, axis_value=0.75)
        self.assertEqual(ev.axis, 0)
        self.assertEqual(ev.axis_value, 0.75)

    def test_input_event_action(self) -> None:
        ev = InputEventAction(action="jump", strength=1.0, pressed=True)
        self.assertEqual(ev.action, "jump")
        self.assertEqual(ev.strength, 1.0)
        self.assertTrue(ev.pressed)


class TestProcessMode(unittest.TestCase):
    def test_process_mode_enum_values(self) -> None:
        self.assertEqual(ProcessMode.INHERIT.value, "inherit")
        self.assertEqual(ProcessMode.ALWAYS.value, "always")
        self.assertEqual(ProcessMode.WHEN_PAUSED.value, "when_paused")
        self.assertEqual(ProcessMode.DISABLED.value, "disabled")

    def test_component_base_has_process_mode(self) -> None:
        comp = Component()
        self.assertEqual(comp.process_mode, "inherit")
        self.assertEqual(comp.process_priority, 0)

    def test_component_process_mode_in_to_dict(self) -> None:
        comp = Component()
        comp.process_mode = "always"
        comp.process_priority = 5
        data = comp.to_dict()
        self.assertEqual(data["process_mode"], "always")
        self.assertEqual(data["process_priority"], 5)


class TestSpriteFramesStandalone(unittest.TestCase):
    def test_sprite_frame_default(self) -> None:
        sf = SpriteFrame()
        self.assertEqual(sf.texture_path, "")
        self.assertEqual(sf.duration, 0.1)

    def test_sprite_frame_serialization(self) -> None:
        sf = SpriteFrame(texture_path="player.png", duration=0.15)
        data = sf.to_dict()
        restored = SpriteFrame.from_dict(data)
        self.assertEqual(restored.texture_path, "player.png")
        self.assertEqual(restored.duration, 0.15)

    def test_sprite_animation_default(self) -> None:
        anim = SpriteAnimation()
        self.assertEqual(anim.name, "default")
        self.assertEqual(anim.frames, [])
        self.assertEqual(anim.speed, 10.0)
        self.assertEqual(anim.loop_mode, "loop")

    def test_sprite_frames_add_animation(self) -> None:
        sframes = SpriteFrames()
        anim = sframes.add_animation("run")
        self.assertIn("run", sframes.animations)
        self.assertEqual(anim.name, "run")

    def test_sprite_frames_add_frame(self) -> None:
        sframes = SpriteFrames()
        sframes.add_frame("idle", "frame1.png", 0.2)
        self.assertIn("idle", sframes.animations)
        self.assertEqual(len(sframes.animations["idle"].frames), 1)
        self.assertEqual(sframes.animations["idle"].frames[0].texture_path, "frame1.png")
        self.assertEqual(sframes.animations["idle"].frames[0].duration, 0.2)

    def test_sprite_frames_remove_animation(self) -> None:
        sframes = SpriteFrames()
        sframes.add_animation("temp")
        sframes.remove_animation("temp")
        self.assertNotIn("temp", sframes.animations)

    def test_sprite_frames_set_speed(self) -> None:
        sframes = SpriteFrames()
        sframes.add_animation("walk")
        sframes.set_animation_speed("walk", 15.0)
        self.assertEqual(sframes.animations["walk"].speed, 15.0)

    def test_sprite_frames_set_loop(self) -> None:
        sframes = SpriteFrames()
        sframes.add_animation("walk")
        sframes.set_animation_loop("walk", "pingpong")
        self.assertEqual(sframes.animations["walk"].loop_mode, "pingpong")

    def test_sprite_frames_serialization_roundtrip(self) -> None:
        sframes = SpriteFrames(resource_id="sf_001")
        sframes.add_frame("idle", "idle_1.png", 0.1)
        sframes.add_frame("idle", "idle_2.png", 0.1)
        sframes.set_animation_speed("idle", 8.0)
        data = sframes.to_dict()
        restored = SpriteFrames.from_dict(data)
        self.assertEqual(restored.resource_id, "sf_001")
        self.assertIn("idle", restored.animations)
        self.assertEqual(len(restored.animations["idle"].frames), 2)
        self.assertEqual(restored.animations["idle"].speed, 8.0)


class TestComponentRegistryNewComponents(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = create_default_registry()

    def test_remote_transform_2d_registered(self) -> None:
        comp_class = self.registry.get("RemoteTransform2D")
        self.assertIsNotNone(comp_class)
        comp = self.registry.create("RemoteTransform2D", {})
        self.assertIsInstance(comp, RemoteTransform2D)

    def test_touch_screen_button_registered(self) -> None:
        comp_class = self.registry.get("TouchScreenButton")
        self.assertIsNotNone(comp_class)
        comp = self.registry.create("TouchScreenButton", {})
        self.assertIsInstance(comp, TouchScreenButton)

    def test_gpu_particles_2d_registered(self) -> None:
        comp_class = self.registry.get("GPUParticles2D")
        self.assertIsNotNone(comp_class)
        comp = self.registry.create("GPUParticles2D", {})
        self.assertIsInstance(comp, GPUParticles2D)


class TestInputSystemAccumulatedInput(unittest.TestCase):
    def test_accumulated_input_flag_exists(self) -> None:
        from engine.systems.input_system import InputSystem
        self.assertTrue(hasattr(InputSystem, "use_accumulated_input"))
        self.assertTrue(InputSystem.use_accumulated_input)

    def test_flush_buffered_events_empty(self) -> None:
        from engine.systems.input_system import InputSystem
        system = InputSystem()
        events = system.flush_buffered_events()
        self.assertEqual(events, [])


class TestRuntimeControllerProcessMode(unittest.TestCase):
    def test_filter_by_process_mode_method_exists(self) -> None:
        from engine.app.runtime_controller import RuntimeController
        self.assertTrue(hasattr(RuntimeController, "filter_by_process_mode"))


if __name__ == "__main__":
    unittest.main()
