import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from uuid import uuid4

from engine.components.scriptbehaviour import ScriptBehaviour
from engine.core.hot_reload import HotReloadManager
from engine.ecs.component import Component
from engine.ecs.world import World
from engine.systems.script_behaviour_system import ScriptBehaviourContext, ScriptBehaviourSystem


class ProbeComponent(Component):
    def __init__(self, value: int = 0) -> None:
        self.enabled = True
        self.value = value


class ScriptBehaviourSystemTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self._temp_dir.name)
        self.scripts_dir = self.root / "scripts"
        self.scripts_dir.mkdir(parents=True, exist_ok=True)
        self.module_names: list[str] = []
        self.system = ScriptBehaviourSystem()
        self.system.set_hot_reload_manager(HotReloadManager(self.scripts_dir.as_posix()))

    def tearDown(self) -> None:
        for module_name in self.module_names:
            sys.modules.pop(module_name, None)
        scripts_path = self.scripts_dir.as_posix()
        while scripts_path in sys.path:
            sys.path.remove(scripts_path)
        self._temp_dir.cleanup()

    def _module_name(self, prefix: str) -> str:
        module_name = f"{prefix}_{uuid4().hex}"
        self.module_names.append(module_name)
        return module_name

    def _write_module(self, module_name: str, source: str, *, mtime: float | None = None) -> Path:
        path = self.scripts_dir / f"{module_name}.py"
        path.write_text(source, encoding="utf-8")
        if mtime is not None:
            os.utime(path, (mtime, mtime))
        return path

    def _world_with_script(
        self,
        module_name: str,
        *,
        entity_name: str = "Actor",
        public_data: dict | None = None,
        run_in_edit_mode: bool = False,
    ) -> tuple[World, ScriptBehaviour]:
        world = World()
        entity = world.create_entity(entity_name)
        script = ScriptBehaviour(
            module_path=module_name,
            public_data=public_data or {},
            run_in_edit_mode=run_in_edit_mode,
        )
        entity.add_component(script)
        return world, script

    def test_on_play_calls_compiled_hook_once(self) -> None:
        module_name = self._module_name("play_actor")
        self._write_module(
            module_name,
            "def on_play(context):\n"
            "    context.public_data['played'] = context.public_data.get('played', 0) + 1\n",
        )
        world, script = self._world_with_script(module_name, public_data={})

        self.system.on_play(world)
        self.system.update(world, 0.016)

        self.assertEqual(script.public_data["played"], 1)

    def test_play_update_calls_compiled_on_update_with_dt(self) -> None:
        module_name = self._module_name("update_actor")
        self._write_module(
            module_name,
            "def on_update(context, dt):\n"
            "    context.public_data['dt'] = dt\n"
            "    context.public_data['updates'] = context.public_data.get('updates', 0) + 1\n",
        )
        world, script = self._world_with_script(module_name, public_data={})

        self.system.on_play(world)
        invoked = self.system.update(world, 0.25)

        self.assertTrue(invoked)
        self.assertEqual(script.public_data["dt"], 0.25)
        self.assertEqual(script.public_data["updates"], 1)

    def test_on_stop_calls_compiled_hook_and_clears_cache(self) -> None:
        module_name = self._module_name("stop_actor")
        self._write_module(
            module_name,
            "def on_stop(context):\n"
            "    context.public_data['stopped'] = True\n",
        )
        world, script = self._world_with_script(module_name, public_data={})

        self.system.on_play(world)
        self.system.on_stop(world)

        self.assertTrue(script.public_data["stopped"])
        self.assertEqual(self.system._runtime_compiled_scripts, [])
        self.assertIsNone(self.system._runtime_world)

    def test_missing_hooks_do_not_fail(self) -> None:
        module_name = self._module_name("empty_actor")
        self._write_module(module_name, "VALUE = 1\n")
        world, script = self._world_with_script(module_name, public_data={})

        self.system.on_play(world)
        invoked = self.system.update(world, 0.016)
        self.system.on_stop(world)

        self.assertFalse(invoked)
        self.assertEqual(script.public_data, {})

    def test_edit_mode_keeps_run_in_edit_mode_filter(self) -> None:
        module_name = self._module_name("edit_actor")
        self._write_module(
            module_name,
            "def on_update(context, dt):\n"
            "    context.public_data['updates'] = context.public_data.get('updates', 0) + 1\n",
        )
        world = World()
        enabled_entity = world.create_entity("EditActor")
        enabled_script = ScriptBehaviour(module_path=module_name, public_data={}, run_in_edit_mode=True)
        enabled_entity.add_component(enabled_script)
        skipped_entity = world.create_entity("RuntimeOnlyActor")
        skipped_script = ScriptBehaviour(module_path=module_name, public_data={}, run_in_edit_mode=False)
        skipped_entity.add_component(skipped_script)

        invoked = self.system.update(world, 0.016, is_edit_mode=True)

        self.assertTrue(invoked)
        self.assertEqual(enabled_script.public_data["updates"], 1)
        self.assertEqual(skipped_script.public_data, {})

    def test_invoke_callable_uses_dynamic_resolution_path(self) -> None:
        module_name = self._module_name("callable_actor")
        self._write_module(
            module_name,
            "def custom_method(context, amount, source=None):\n"
            "    context.public_data['amount'] = amount\n"
            "    context.public_data['source'] = source\n",
        )
        world, script = self._world_with_script(module_name, public_data={})

        invoked = self.system.invoke_callable(world, "Actor", "custom_method", 7, source="signal")

        self.assertTrue(invoked)
        self.assertEqual(script.public_data["amount"], 7)
        self.assertEqual(script.public_data["source"], "signal")

    def test_context_get_component_uses_component_name(self) -> None:
        world = World()
        entity = world.create_entity("Actor")
        component = ProbeComponent(3)
        entity.add_component(component)
        context = ScriptBehaviourContext(world=world, entity_name="Actor", public_data={})

        self.assertIs(context.get_component("ProbeComponent"), component)

    def test_hot_reload_invalidates_runtime_cache(self) -> None:
        module_name = self._module_name("reload_actor")
        self._write_module(
            module_name,
            "def on_update(context, dt):\n"
            "    context.public_data['version'] = 'v1'\n",
        )
        world, script = self._world_with_script(module_name, public_data={})

        self.system.on_play(world)
        self.system.update(world, 0.016)
        self.assertEqual(script.public_data["version"], "v1")

        future_mtime = time.time() + 2.0
        self._write_module(
            module_name,
            "def on_update(context, dt):\n"
            "    context.public_data['version'] = 'v2 changed'\n",
            mtime=future_mtime,
        )

        self.system.update(world, 0.016)

        self.assertEqual(script.public_data["version"], "v2 changed")


if __name__ == "__main__":
    unittest.main()
