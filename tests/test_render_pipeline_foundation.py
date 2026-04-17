import unittest
from unittest.mock import patch

from engine.components.renderorder2d import RenderOrder2D
from engine.components.sprite import Sprite
from engine.components.transform import Transform
from engine.ecs.world import World
from engine.rendering.pipeline_types import FramePlan2D, RenderCommand2D, RenderPassPlan2D
from engine.systems.render_system import RenderSystem


class RenderPipelineFoundationTests(unittest.TestCase):
    def _make_sprite_entity(
        self,
        world: World,
        name: str,
        *,
        x: float,
        sorting_layer: str = "Default",
        order_in_layer: int = 0,
        render_pass: str = "World",
    ) -> None:
        entity = world.create_entity(name)
        entity.add_component(Transform(x=x, y=0.0, rotation=0.0, scale_x=1.0, scale_y=1.0))
        entity.add_component(Sprite(texture_path="assets/shared.png", width=32, height=32))
        entity.add_component(RenderOrder2D(sorting_layer=sorting_layer, order_in_layer=order_in_layer, render_pass=render_pass))

    def test_planner_adapts_legacy_frame_plan_without_changing_order_and_jobs(self) -> None:
        world = World()
        world.feature_metadata = {
            "render_2d": {
                "sorting_layers": ["Default", "Gameplay", "Foreground"],
                "minimap": {"enabled": True, "width": 160, "height": 100, "margin": 10},
            }
        }
        self._make_sprite_entity(world, "Ground", x=0.0, sorting_layer="Default")
        self._make_sprite_entity(world, "Hero", x=10.0, sorting_layer="Gameplay", order_in_layer=3)
        self._make_sprite_entity(world, "HudMarker", x=20.0, sorting_layer="Foreground", render_pass="Overlay")
        world.selected_entity_name = "Hero"

        render_system = RenderSystem()
        legacy_frame_plan = render_system._build_frame_plan(world, viewport_size=(320.0, 180.0))
        frame_plan = render_system._pipeline_planner.adapt_frame_plan_payload(legacy_frame_plan)

        self.assertIsInstance(frame_plan, FramePlan2D)
        self.assertEqual([pass_plan.name for pass_plan in frame_plan.passes], ["World", "Overlay", "Debug"])
        self.assertTrue(all(isinstance(pass_plan, RenderPassPlan2D) for pass_plan in frame_plan.passes))
        self.assertTrue(all(isinstance(command, RenderCommand2D) for pass_plan in frame_plan.passes for command in pass_plan.commands))
        self.assertEqual([command.entity_name for command in frame_plan.get_pass("World").commands], ["Ground", "Hero"])
        self.assertEqual([command.entity_name for command in frame_plan.get_pass("Overlay").commands], ["HudMarker"])
        self.assertEqual([job.kind for job in frame_plan.render_target_jobs], ["debug_overlay", "minimap"])
        self.assertEqual([job["name"] for job in legacy_frame_plan["render_targets"]], ["selection_overlay", "minimap"])

        frame_plan_via_helper = render_system._build_frame_plan_model(world, viewport_size=(320.0, 180.0))
        self.assertEqual([pass_plan.name for pass_plan in frame_plan_via_helper.passes], ["World", "Overlay", "Debug"])
        self.assertEqual([job.kind for job in frame_plan_via_helper.render_target_jobs], ["debug_overlay", "minimap"])

    def test_render_system_wrappers_delegate_typed_models_to_executor(self) -> None:
        world = World()
        world.feature_metadata = {
            "render_2d": {
                "sorting_layers": ["Default"],
                "minimap": {"enabled": True, "width": 160, "height": 100, "margin": 10},
            }
        }
        self._make_sprite_entity(world, "Hero", x=16.0)
        world.selected_entity_name = "Hero"

        render_system = RenderSystem()
        frame_plan = render_system._build_frame_plan_model(world, viewport_size=(320.0, 180.0))

        with patch.object(render_system._pipeline_executor, "render_pass") as render_pass:
            render_system._render_pass(frame_plan, "World")

        render_pass.assert_called_once_with(frame_plan, "World")

        with patch.object(render_system._pipeline_executor, "execute_render_target_job") as execute_job:
            render_system._render_debug_overlay(frame_plan, camera=None, viewport_size=(320.0, 180.0))

        execute_job.assert_called_once()
        self.assertEqual(execute_job.call_args.args[0].kind, "debug_overlay")

        with patch.object(render_system._pipeline_executor, "execute_render_target_job") as execute_job:
            render_system._render_minimap(world, frame_plan, viewport_size=(320.0, 180.0))

        execute_job.assert_called_once()
        self.assertEqual(execute_job.call_args.args[0].kind, "minimap")

    def test_executor_dispatches_world_pass_and_target_jobs_through_handlers(self) -> None:
        world = World()
        world.feature_metadata = {
            "render_2d": {
                "sorting_layers": ["Default"],
                "minimap": {"enabled": True, "width": 160, "height": 100, "margin": 10},
            }
        }
        self._make_sprite_entity(world, "Hero", x=16.0)
        world.selected_entity_name = "Hero"

        render_system = RenderSystem()
        frame_plan = render_system._build_frame_plan_model(world, viewport_size=(320.0, 180.0))

        with patch.object(render_system, "_begin_batch_state") as begin_state, patch.object(
            render_system,
            "_end_batch_state",
        ) as end_state, patch.object(render_system, "_render_entity") as render_entity:
            render_system._pipeline_executor.render_pass(frame_plan, "World")

        begin_state.assert_called_once()
        end_state.assert_called_once()
        render_entity.assert_called_once()

        debug_job = frame_plan.render_target_jobs[0]
        minimap_job = frame_plan.render_target_jobs[1]
        with patch.object(render_system, "_draw_selection_highlight") as draw_selection, patch.object(
            render_system._render_targets,
            "begin",
        ) as begin_target, patch.object(render_system._render_targets, "end") as end_target, patch.object(
            render_system._render_targets,
            "compose",
        ) as compose_target:
            render_system._pipeline_executor.execute_render_target_job(
                debug_job,
                world=world,
                camera=None,
                viewport_size=(320.0, 180.0),
            )

        draw_selection.assert_called_once()
        begin_target.assert_called_once()
        end_target.assert_called_once()
        compose_target.assert_called_once()

        with patch.object(render_system._render_targets, "begin") as begin_target, patch.object(
            render_system._render_targets,
            "end",
        ) as end_target, patch.object(render_system._render_targets, "compose") as compose_target, patch(
            "pyray.draw_circle"
        ) as draw_circle, patch("pyray.draw_rectangle_lines") as draw_rectangle_lines:
            render_system._pipeline_executor.execute_render_target_job(
                minimap_job,
                world=world,
                camera=None,
                viewport_size=(320.0, 180.0),
            )

        begin_target.assert_called_once()
        end_target.assert_called_once()
        compose_target.assert_called_once()
        draw_circle.assert_called_once()
        draw_rectangle_lines.assert_called_once()


if __name__ == "__main__":
    unittest.main()
