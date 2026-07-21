from __future__ import annotations

import types
import unittest

from engine.components.animator import Animator
from engine.components.polygon2d import Polygon2D
from engine.components.sprite import Sprite
from engine.components.transform import Transform
from engine.ecs.entity import Entity
from engine.systems.render_system import RenderBatch, RenderBatchKey, RenderCommand, RenderPass, RenderSystem


class SimpleSpriteBatcherTests(unittest.TestCase):
    def setUp(self) -> None:
        self.render_system = RenderSystem()
        self.render_system._load_texture = types.MethodType(self._fake_load_texture, self.render_system)

    def _fake_load_texture(self, owner: RenderSystem, reference: object, fallback_path: str, sync_callback: object = None) -> object:
        del owner, reference, sync_callback
        texture_id = 1 if fallback_path == "ground.png" else 2
        return types.SimpleNamespace(id=texture_id, width=32, height=32)

    def _entity(
        self,
        name: str,
        *,
        texture_path: str = "ground.png",
        rotation: float = 0.0,
        animated: bool = False,
        polygon: bool = False,
    ) -> Entity:
        entity = Entity(name)
        entity.add_component(Transform(x=0.0, y=0.0, rotation=rotation, scale_x=1.0, scale_y=1.0))
        entity.add_component(Sprite(texture_path=texture_path, width=32, height=32, origin_x=0.5, origin_y=0.5))
        if animated:
            entity.add_component(Animator(sprite_sheet="characters.png"))
        if polygon:
            entity.add_component(Polygon2D(points=[(0.0, 0.0), (32.0, 0.0), (32.0, 32.0)]))
        return entity

    def _command(self, entity: Entity) -> RenderCommand:
        return RenderCommand(kind="entity", entity=entity, entity_name=entity.name, batch_key=RenderBatchKey(atlas_id="ground.png"))

    def _batch(self, entities: list[Entity]) -> RenderBatch:
        return RenderBatch(key=RenderBatchKey(atlas_id="ground.png"), commands=[self._command(entity) for entity in entities])

    def test_simple_sprites_are_estimated_as_one_real_draw_call(self) -> None:
        entities = [self._entity(f"Ground_{index}") for index in range(50)]

        stats = self.render_system._estimate_simple_sprite_batch_stats([self._batch(entities)])

        self.assertEqual(stats["draw_calls"], 1)
        self.assertEqual(stats["sprite_batches"], 1)
        self.assertEqual(stats["batched_sprites"], 50)
        self.assertEqual(stats["sprite_batch_fallbacks"], 0)

    def test_rotation_animator_and_polygon_take_fallback_path(self) -> None:
        entities = [
            self._entity("Simple_A"),
            self._entity("Rotated", rotation=15.0),
            self._entity("Animated", animated=True),
            self._entity("Polygon", polygon=True),
            self._entity("Simple_B"),
        ]

        stats = self.render_system._estimate_simple_sprite_batch_stats([self._batch(entities)])

        self.assertEqual(stats["draw_calls"], 5)
        self.assertEqual(stats["sprite_batches"], 2)
        self.assertEqual(stats["batched_sprites"], 2)
        self.assertEqual(stats["sprite_batch_fallbacks"], 3)

    def test_order_is_preserved_by_flushing_before_fallback(self) -> None:
        entities = [
            self._entity("Batch_A"),
            self._entity("Fallback_B", rotation=45.0),
            self._entity("Batch_C"),
        ]

        stats = self.render_system._estimate_simple_sprite_batch_stats([self._batch(entities)])

        self.assertEqual(stats["draw_calls"], 3)
        self.assertEqual(stats["sprite_batches"], 2)
        self.assertEqual(stats["batched_sprites"], 2)
        self.assertEqual(stats["sprite_batch_fallbacks"], 1)

    def test_texture_changes_split_simple_sprite_batches(self) -> None:
        entities = [
            self._entity("Ground_A", texture_path="ground.png"),
            self._entity("Other", texture_path="other.png"),
            self._entity("Ground_B", texture_path="ground.png"),
        ]

        stats = self.render_system._estimate_simple_sprite_batch_stats([self._batch(entities)])

        self.assertEqual(stats["draw_calls"], 3)
        self.assertEqual(stats["sprite_batches"], 3)
        self.assertEqual(stats["batched_sprites"], 3)
        self.assertEqual(stats["sprite_batch_fallbacks"], 0)

    def test_graph_stats_keep_render_entity_count_but_reduce_draw_calls(self) -> None:
        entities = [self._entity(f"Ground_{index}") for index in range(10)]
        batch = self._batch(entities)
        pass_plan = RenderPass(
            name="World",
            commands=list(batch.commands),
            batches=[batch],
            stats={"render_entities": 10, "render_commands": 10, "draw_calls": 10, "batches": 1, "state_changes": 0},
        )
        graph = {
            "passes": [pass_plan],
            "totals": {
                "render_entities": 10,
                "render_commands": 10,
                "draw_calls": 10,
                "batches": 1,
                "state_changes": 0,
                "passes": {"World": dict(pass_plan.stats)},
            },
        }

        self.render_system._apply_simple_sprite_batch_stats_to_graph(graph)

        totals = graph["totals"]
        self.assertEqual(totals["render_entities"], 10)
        self.assertEqual(totals["draw_calls"], 1)
        self.assertEqual(totals["sprite_batches"], 1)
        self.assertEqual(totals["batched_sprites"], 10)
        self.assertEqual(graph["passes"][0].stats["draw_calls"], 1)


if __name__ == "__main__":
    unittest.main()
