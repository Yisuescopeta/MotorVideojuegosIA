import tempfile
import unittest
from pathlib import Path

from engine.components.scriptbehaviour import ScriptBehaviour
from engine.core.hot_reload import HotReloadManager
from engine.ecs.world import World
from engine.events.callable_resolver import CallableResolver, CallableResolverContext
from engine.events.event_bus import EventBus
from engine.project.project_service import ProjectService
from engine.services.registro_servicios import RegistroServicios
from engine.systems.script_behaviour_system import ScriptBehaviourSystem


class CallableResolverTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self._temp_dir.name)
        self.project_service = ProjectService(self.root)
        scripts_dir = self.root / "scripts"
        scripts_dir.mkdir(parents=True, exist_ok=True)
        (scripts_dir / "signal_actor.py").write_text(
            "def on_signal(context, amount, source=None):\n"
            "    context.public_data['amount'] = amount\n"
            "    context.public_data['source'] = source\n",
            encoding="utf-8",
        )

        self.world = World()
        actor = self.world.create_entity("Actor")
        actor.add_component(
            ScriptBehaviour(
                module_path="signal_actor",
                public_data={},
            )
        )

        self.event_bus = EventBus()
        self.script_behaviour_system = ScriptBehaviourSystem()
        self.script_behaviour_system.set_hot_reload_manager(HotReloadManager((self.root / "scripts").as_posix()))
        self.script_behaviour_system.set_project_service(self.project_service)
        self.registry = RegistroServicios()
        self.resolver = CallableResolver(
            CallableResolverContext(
                get_world=lambda: self.world,
                get_script_behaviour_system=lambda: self.script_behaviour_system,
                get_event_bus=lambda: self.event_bus,
                get_service_registry=lambda: self.registry,
            )
        )

    def tearDown(self) -> None:
        self._temp_dir.cleanup()

    def test_resolve_entity_script_callable_invokes_script_method(self) -> None:
        callable_obj = self.resolver.resolve(
            {"kind": "entity", "name": "Actor", "component": "ScriptBehaviour"},
            {"method": "on_signal"},
        )

        self.assertIsNotNone(callable_obj)
        self.assertTrue(callable_obj(5, source="button"))
        actor = self.world.get_entity_by_name("Actor")
        script = actor.get_component(ScriptBehaviour)
        self.assertEqual(script.public_data["amount"], 5)
        self.assertEqual(script.public_data["source"], "button")

    def test_resolve_event_bus_callable_emits_payload(self) -> None:
        captured: list[dict] = []
        self.event_bus.subscribe("enemy.defeated", lambda event: captured.append(dict(event.data)))
        callable_obj = self.resolver.resolve(
            {"kind": "event_bus"},
            {"event": "enemy.defeated"},
        )

        self.assertIsNotNone(callable_obj)
        self.assertTrue(callable_obj({"entity": "Enemy", "points": 10}))
        self.assertEqual(captured, [{"entity": "Enemy", "points": 10}])

    def test_resolve_service_callable_invokes_service_method(self) -> None:
        class GameState:
            def __init__(self):
                self.score = 0

            def add_score(self, points: int) -> None:
                self.score += points

        game_state = GameState()
        self.registry.registrar_builtin("GameState", game_state)
        callable_obj = self.resolver.resolve(
            {"kind": "service", "name": "GameState"},
            {"method": "add_score"},
        )

        self.assertIsNotNone(callable_obj)
        self.assertTrue(callable_obj(5))
        self.assertEqual(game_state.score, 5)

    def test_resolve_service_callable_returns_none_when_service_missing(self) -> None:
        # La resolución es lazy: devuelve callable incluso si el servicio no existe aún.
        callable_obj = self.resolver.resolve(
            {"kind": "service", "name": "MissingService"},
            {"method": "do_thing"},
        )

        self.assertIsNotNone(callable_obj)
        self.assertFalse(callable_obj())

    def test_resolve_service_callable_returns_none_when_method_missing(self) -> None:
        class GameState:
            pass

        self.registry.registrar_builtin("GameState", GameState())
        callable_obj = self.resolver.resolve(
            {"kind": "service", "name": "GameState"},
            {"method": "missing_method"},
        )

        self.assertIsNotNone(callable_obj)
        self.assertFalse(callable_obj())


class RuntimeControllerCallableResolverIntegrationTests(unittest.TestCase):
    def test_runtime_controller_exposes_callable_resolver(self) -> None:
        from engine.app.runtime_controller import RuntimeController
        from engine.core.engine_state import EngineState
        from engine.core.runtime_contracts import RuntimeControllerContext
        from engine.physics.registry import PhysicsBackendRegistry

        state = {"value": EngineState.EDIT}
        world_holder = {"world": World()}
        event_bus = EventBus()
        controller = RuntimeController(
            RuntimeControllerContext(
                get_state=lambda: state["value"],
                set_state=lambda value: state.__setitem__("value", value),
                get_world=lambda: world_holder["world"],
                set_world=lambda world: world_holder.__setitem__("world", world),
                get_scene_runtime=lambda: None,
                get_rule_system=lambda: None,
                get_script_behaviour_system=lambda: None,
                get_event_bus=lambda: event_bus,
                get_animation_system=lambda: None,
                get_input_system=lambda: None,
                get_player_controller_system=lambda: None,
                get_character_controller_system=lambda: None,
                get_physics_system=lambda: None,
                get_collision_system=lambda: None,
                get_audio_system=lambda: None,
                get_scene_transition_controller=lambda: None,
                get_physics_backend_registry=lambda: PhysicsBackendRegistry(),
                reset_profiler=lambda **_kwargs: None,
                set_physics_backend=lambda *_args, **_kwargs: None,
                edit_animation_speed=0.35,
            )
        )

        self.assertIsNotNone(controller.callable_resolver)
        callable_obj = controller.callable_resolver.resolve(
            {"kind": "event_bus"},
            {"event": "tick"},
        )
        self.assertIsNotNone(callable_obj)

        captured: list[dict] = []
        event_bus.subscribe("tick", lambda event: captured.append(dict(event.data)))
        self.assertTrue(callable_obj({"frame": 1}))
        self.assertEqual(captured, [{"frame": 1}])


if __name__ == "__main__":
    unittest.main()
