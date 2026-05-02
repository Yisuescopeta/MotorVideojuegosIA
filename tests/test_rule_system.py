import unittest
from unittest.mock import patch

from engine.components.animator import AnimationData, Animator
from engine.components.transform import Transform
from engine.core.game import Game
from engine.ecs.world import World
from engine.events.event_bus import EventBus
from engine.events.rule_system import RuleSystem


class RuleSystemTests(unittest.TestCase):
    def setUp(self) -> None:
        self.event_bus = EventBus()
        self.rule_system = RuleSystem(self.event_bus)

    def test_construction_without_world_loads_rules_and_subscribes(self) -> None:
        self.rule_system.load_rules([{"event": "tick", "do": []}])

        self.assertEqual(self.rule_system.rules_count, 1)
        self.assertEqual(self.event_bus.get_subscriber_count("tick"), 1)

    def test_non_world_actions_execute_without_world(self) -> None:
        captured_events: list[str] = []

        def on_secondary(event) -> None:
            captured_events.append(event.name)

        self.event_bus.subscribe("secondary", on_secondary)
        self.rule_system.load_rules(
            [
                {
                    "event": "tick",
                    "do": [
                        {"action": "emit_event", "event": "secondary", "data": {"value": 1}},
                        {"action": "log_message", "message": "Evento {event}"},
                    ],
                }
            ]
        )

        with patch("builtins.print") as print_mock:
            self.event_bus.emit("tick", {})

        self.assertEqual(captured_events, ["secondary"])
        self.assertEqual(self.rule_system.rules_executed_count, 1)
        printed_lines = [call.args[0] for call in print_mock.call_args_list if call.args]
        self.assertIn("[RULE] Evento tick", printed_lines)

    def test_world_actions_without_world_warn_and_do_not_raise(self) -> None:
        self.rule_system.load_rules(
            [
                {
                    "event": "tick",
                    "do": [
                        {"action": "set_position", "entity": "Player", "x": 10, "y": 20},
                        {"action": "spawn_entity", "name": "Enemy", "x": 4, "y": 5},
                        {"action": "destroy_entity", "entity": "Enemy"},
                    ],
                }
            ]
        )

        with patch("builtins.print") as print_mock:
            self.event_bus.emit("tick", {})

        self.assertEqual(self.rule_system.rules_executed_count, 1)
        printed_lines = [call.args[0] for call in print_mock.call_args_list if call.args]
        self.assertIn(
            "[WARNING] RuleSystem: accion 'set_position' ignorada porque no hay world enlazado",
            printed_lines,
        )
        self.assertIn(
            "[WARNING] RuleSystem: accion 'destroy_entity' ignorada porque no hay world enlazado",
            printed_lines,
        )
        self.assertIn(
            "[WARNING] RuleSystem: accion 'spawn_entity' ignorada porque no hay world enlazado",
            printed_lines,
        )

    def test_set_world_after_construction_enables_entity_actions(self) -> None:
        world = World()
        player = world.create_entity("Player")
        player.add_component(Transform(x=1, y=2))
        player.add_component(
            Animator(
                animations={
                    "idle": AnimationData(frames=[0]),
                    "hit": AnimationData(frames=[1]),
                },
                default_state="idle",
            )
        )

        self.rule_system.load_rules(
            [
                {
                    "event": "tick",
                    "do": [
                        {"action": "set_position", "entity": "Player", "x": 10, "y": 20},
                        {"action": "set_animation", "entity": "Player", "state": "hit"},
                    ],
                }
            ]
        )
        self.rule_system.set_world(world)

        self.event_bus.emit("tick", {})

        transform = player.get_component(Transform)
        animator = player.get_component(Animator)
        self.assertIsNotNone(transform)
        self.assertIsNotNone(animator)
        self.assertEqual(transform.x, 10.0)
        self.assertEqual(transform.y, 20.0)
        self.assertEqual(animator.current_state, "hit")

    def test_spawn_entity_creates_runtime_entity_with_transform(self) -> None:
        world = World()
        self.rule_system.set_world(world)
        self.rule_system.load_rules(
            [
                {
                    "event": "spawn",
                    "do": [
                        {"action": "spawn_entity", "name": "Enemy", "x": 100, "y": 50},
                    ],
                }
            ]
        )

        self.event_bus.emit("spawn", {})

        enemy = world.get_entity_by_name("Enemy")
        self.assertIsNotNone(enemy)
        transform = enemy.get_component(Transform) if enemy is not None else None
        self.assertIsNotNone(transform)
        self.assertEqual(transform.x, 100.0)
        self.assertEqual(transform.y, 50.0)

    def test_spawn_entity_duplicate_name_warns_and_does_not_replace(self) -> None:
        world = World()
        existing = world.create_entity("Enemy")
        existing.add_component(Transform(x=1, y=2))
        self.rule_system.set_world(world)
        self.rule_system.load_rules(
            [
                {
                    "event": "spawn",
                    "do": [
                        {"action": "spawn_entity", "name": "Enemy", "x": 100, "y": 50},
                    ],
                }
            ]
        )

        with patch("builtins.print") as print_mock:
            self.event_bus.emit("spawn", {})

        enemy = world.get_entity_by_name("Enemy")
        self.assertIs(enemy, existing)
        transform = enemy.get_component(Transform) if enemy is not None else None
        self.assertIsNotNone(transform)
        self.assertEqual(transform.x, 1)
        self.assertEqual(transform.y, 2)
        printed_lines = [call.args[0] for call in print_mock.call_args_list if call.args]
        self.assertIn("[WARNING] spawn_entity: entidad 'Enemy' ya existe", printed_lines)

    def test_bootstrap_smoke_supports_rule_system_without_world(self) -> None:
        game = Game()
        event_bus = EventBus()
        rule_system = RuleSystem(event_bus)

        game.set_event_bus(event_bus)
        game.set_rule_system(rule_system)

        self.assertIs(game._event_bus, event_bus)
        self.assertIs(game._rule_system, rule_system)


if __name__ == "__main__":
    unittest.main()
