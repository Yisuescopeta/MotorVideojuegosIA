import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.append(os.getcwd())

from engine.api import EngineAPI
from engine.ai.providers import ModelProvider
from engine.ai.types import ProviderPolicy


class FakeGenerativeBuildProvider(ModelProvider):
    id = "fake_generative_build"
    provider_kind = "local"

    def is_available(self, policy: ProviderPolicy | None = None) -> bool:
        return True

    def describe(self) -> str:
        return "Fake provider for deterministic build synthesis tests"

    def complete(self, prompt: str, system_prompt: str, policy: ProviderPolicy) -> str:
        payload = json.loads(prompt)
        entities = {
            str(item.get("name", "")).strip()
            for item in payload.get("context", {}).get("entities", [])
            if isinstance(item, dict)
        }
        if "Enemy" not in entities:
            return json.dumps(
                {
                    "summary": "Necesito una entidad enemiga concreta para adjuntar el comportamiento.",
                    "reasoning": "No existe una entidad Enemy en la escena activa.",
                    "can_build_now": False,
                    "blocking_questions": [
                        {
                            "id": "target_entity",
                            "text": "No encuentro la entidad enemiga. Selecciona una o escribe su nombre exacto.",
                            "rationale": "Necesito una entidad concreta para adjuntar el comportamiento.",
                            "choices": [],
                        }
                    ],
                    "tool_calls": [],
                }
            )
        return json.dumps(
            {
                "summary": "Voy a adjuntar un comportamiento de persecución al enemigo.",
                "reasoning": "Se puede resolver con un ScriptBehaviour editando solo scripts/ y la escena actual.",
                "can_build_now": True,
                "blocking_questions": [],
                "tool_calls": [
                    {
                        "tool_name": "write_script",
                        "summary": "Escribir script de persecución del enemigo",
                        "arguments": {
                            "target": "scripts/enemy_chase_generated.py",
                            "content": "from __future__ import annotations\n\n\ndef on_play(context) -> None:\n    context.public_data.setdefault('target_entity', 'Player')\n    context.public_data.setdefault('speed', 90.0)\n\n\ndef on_update(context, dt: float) -> None:\n    transform = context.get_component('Transform')\n    if transform is None:\n        return\n    target_name = str(context.public_data.get('target_entity', 'Player'))\n    target = context.world.get_entity_by_name(target_name)\n    if target is None:\n        return\n    target_transform = None\n    for component in target.get_all_components():\n        if type(component).__name__ == 'Transform':\n            target_transform = component\n            break\n    if target_transform is None:\n        return\n    speed = float(context.public_data.get('speed', 90.0))\n    dx = float(target_transform.x) - float(transform.x)\n    dy = float(target_transform.y) - float(transform.y)\n    step = max(float(dt), 0.0) * speed\n    if abs(dx) > 1.0:\n        transform.x += max(-step, min(step, dx))\n    if abs(dy) > 1.0:\n        transform.y += max(-step, min(step, dy))\n",
                        },
                    },
                    {
                        "tool_name": "add_script_behaviour",
                        "summary": "Adjuntar persecución al enemigo",
                        "arguments": {
                            "entity_name": "Enemy",
                            "module_path": "scripts/enemy_chase_generated",
                            "public_data": {"target_entity": "Player", "speed": 90.0},
                            "run_in_edit_mode": False,
                            "enabled": True,
                        },
                    },
                ],
            }
        )

    def plan_turn(
        self,
        prompt: str,
        answers: dict,
        policy: ProviderPolicy,
        context: dict,
        available_tools: list[dict],
        session_mode: str,
    ) -> dict | None:
        return {
            "summary": "Puedo intentar implementarlo generando un comportamiento sobre el proyecto actual.",
            "reasoning": "No hace falta una receta hardcodeada si el modelo puede traducir la petición a tool calls.",
            "project_findings": ["Proveedor de prueba activo"],
            "next_steps": ["Generar script", "Adjuntarlo a la entidad objetivo", "Validar el ciclo PLAY/STOP"],
            "can_build_now": True,
            "blocking_questions": [],
            "tool_calls": [],
        }


class FakeLoosePathProvider(FakeGenerativeBuildProvider):
    id = "fake_loose_path_build"

    def complete(self, prompt: str, system_prompt: str, policy: ProviderPolicy) -> str:
        return json.dumps(
            {
                "summary": "Voy a generar el comportamiento con una ruta de script flexible.",
                "reasoning": "La ruta devuelta por el modelo necesita normalización antes de aplicar.",
                "can_build_now": True,
                "blocking_questions": [],
                "tool_calls": [
                    {
                        "tool_name": "write_script",
                        "summary": "Escribir script de persecución del enemigo",
                        "arguments": {
                            "target": "enemy_chase_generated.py",
                            "content": "from __future__ import annotations\n\n\ndef on_play(context) -> None:\n    context.public_data.setdefault('target_entity', 'Player')\n",
                        },
                    },
                    {
                        "tool_name": "add_script_behaviour",
                        "summary": "Adjuntar persecución al enemigo",
                        "arguments": {
                            "entity_name": "Enemy",
                            "module_path": "enemy_chase_generated.py",
                            "public_data": {"target_entity": "Player"},
                            "run_in_edit_mode": False,
                            "enabled": True,
                        },
                    },
                ],
            }
        )


class AISessionTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temp_dir = tempfile.TemporaryDirectory()
        self.workspace = Path(self._temp_dir.name)
        self.global_state_dir = self.workspace / "global_state"
        self.project_root = self.workspace / "SessionProject"
        self.api = EngineAPI(project_root=self.project_root.as_posix(), global_state_dir=self.global_state_dir.as_posix())
        self._write_level("bootstrap.json", "Bootstrap")
        self.api.load_level("levels/bootstrap.json")

    def tearDown(self) -> None:
        self.api.shutdown()
        self._temp_dir.cleanup()

    def _write_level(self, filename: str, scene_name: str) -> Path:
        level_path = self.project_root / "levels" / filename
        level_path.parent.mkdir(parents=True, exist_ok=True)
        level_path.write_text(json.dumps({"name": scene_name, "entities": [], "rules": []}, indent=4), encoding="utf-8")
        return level_path

    def _write_script(self, filename: str, content: str = "def on_update(context, dt):\n    pass\n") -> Path:
        script_path = self.project_root / "scripts" / filename
        script_path.parent.mkdir(parents=True, exist_ok=True)
        script_path.write_text(content, encoding="utf-8")
        return script_path

    def test_start_session_persists_as_active_editor_session(self) -> None:
        session = self.api.start_ai_session(title="Gameplay", mode="plan")

        self.assertTrue(session["id"])
        editor_state = self.api.get_editor_state()
        self.assertEqual(editor_state["active_ai_session_id"], session["id"])

    def test_multi_turn_questions_can_end_in_build_proposal(self) -> None:
        session = self.api.start_ai_session(title="Platformer", mode="plan")
        session = self.api.submit_ai_message("Crea un juego de plataformas", session_id=session["id"], mode="plan")

        self.assertEqual(session["status"], "needs_input")
        self.assertEqual(session["pending_questions"][0]["id"], "enemies")

        for answer in ("none", "none", "placeholders", "follow_platformer"):
            session = self.api.answer_ai_question(answer, session_id=session["id"])
            self.assertEqual(session["status"], "needs_input")

        session = self.api.answer_ai_question("basic_hud", session_id=session["id"], mode="build")

        self.assertEqual(session["status"], "applied")
        self.assertTrue(session["last_apply"]["success"])

    def test_approve_and_undo_restore_scene_and_scripts(self) -> None:
        self.api.create_entity(
            "Player",
            components={
                "Transform": {"enabled": True, "x": 0.0, "y": 0.0, "rotation": 0.0, "scale_x": 1.0, "scale_y": 1.0}
            },
        )

        session = self.api.start_ai_session(title="Movement", mode="build")
        session = self.api.submit_ai_message("anademe movimiento al jugador", session_id=session["id"], mode="direct")
        self.assertEqual(session["status"], "proposal_ready")

        session = self.api.approve_ai_proposal(session_id=session["id"], allow_python=True)
        self.assertEqual(session["status"], "applied")

        script_path = self.project_root / "scripts" / "player_movement_generated.py"
        self.assertTrue(script_path.exists())
        player = self.api.get_entity("Player")
        self.assertIn("ScriptBehaviour", player["components"])

        session = self.api.undo_ai_last_apply(session_id=session["id"])
        self.assertEqual(session["status"], "rolled_back")
        self.assertFalse(script_path.exists())
        player_after = self.api.get_entity("Player")
        self.assertNotIn("ScriptBehaviour", player_after["components"])
        self.assertNotIn("InputMap", player_after["components"])
        self.assertNotIn("RigidBody", player_after["components"])

    def test_engine_scope_requests_return_blocking_gap(self) -> None:
        session = self.api.start_ai_session(title="Engine", mode="build")
        session = self.api.submit_ai_message(
            "Edita engine/ai/orchestrator.py para cambiar el motor interno",
            session_id=session["id"],
            mode="build",
        )

        self.assertEqual(session["status"], "blocked")
        gap_ids = {gap["id"] for gap in session["gaps"]}
        self.assertIn("engine_write_scope", gap_ids)

    def test_session_persists_between_api_instances(self) -> None:
        self._write_script("existing_logic.py")
        session = self.api.start_ai_session(title="Persisted", mode="plan")
        session = self.api.submit_ai_message("Haz un plan general", session_id=session["id"], mode="plan")
        session_id = session["id"]
        self.api.shutdown()

        second_api = EngineAPI(project_root=self.project_root.as_posix(), global_state_dir=self.global_state_dir.as_posix())
        try:
            restored = second_api.get_ai_session()
            self.assertEqual(restored["id"], session_id)
            self.assertEqual(restored["status"], "planned")
        finally:
            second_api.shutdown()

    def test_list_ai_tools_and_context_window_expose_new_surface(self) -> None:
        self._write_script("platformer_character.py")
        tools = self.api.list_ai_tools()
        tool_names = {tool["name"] for tool in tools}
        self.assertIn("write_script", tool_names)
        self.assertIn("create_entity", tool_names)

        session = self.api.start_ai_session(title="Context", mode="plan")
        session = self.api.submit_ai_message("Haz un plan general", session_id=session["id"], mode="plan")
        context_window = session["context_window"]
        self.assertIn("recent_scripts", context_window)
        self.assertIn("capabilities", context_window)
        self.assertTrue(any(path.endswith("platformer_character.py") for path in context_window["recent_scripts"]))
        self.assertIn("plan_response", session)

    def test_diagnostics_include_active_session_and_provider_block(self) -> None:
        session = self.api.start_ai_session(title="Diagnostics", mode="plan")
        diagnostics = self.api.get_ai_diagnostics(session_id=session["id"])

        self.assertEqual(diagnostics["active_session_id"], session["id"])
        self.assertIn("provider", diagnostics)
        self.assertIn("providers", diagnostics["provider"])

    def test_spanish_mobility_prompt_enters_direct_movement_proposal(self) -> None:
        self.api.create_entity(
            "Player",
            components={
                "Transform": {"enabled": True, "x": 0.0, "y": 0.0, "rotation": 0.0, "scale_x": 1.0, "scale_y": 1.0}
            },
        )

        session = self.api.start_ai_session(title="Mobility", mode="build")
        session = self.api.submit_ai_message("anademe movilidad al jugador", session_id=session["id"], mode="direct")

        self.assertEqual(session["status"], "proposal_ready")
        tool_names = [item["tool_name"] for item in session["approval"]["tool_calls"]]
        self.assertIn("add_script_behaviour", tool_names)
        self.assertIn("write_script", tool_names)

    def test_plan_mode_with_existing_character_prepares_proposal_without_generic_questions(self) -> None:
        self.api.create_entity(
            "Player",
            components={
                "Transform": {"enabled": True, "x": 0.0, "y": 0.0, "rotation": 0.0, "scale_x": 1.0, "scale_y": 1.0}
            },
        )

        session = self.api.start_ai_session(title="Plan Movement", mode="plan")
        session = self.api.submit_ai_message("anademe movilidad al personaje", session_id=session["id"], mode="plan")

        self.assertEqual(session["status"], "planned")
        self.assertEqual(session["pending_questions"], [])
        self.assertIsNone(session["approval"])
        self.assertTrue(session["plan_response"]["can_build_now"])

    def test_failed_apply_restores_snapshot_and_surfaces_missing_entity_reason(self) -> None:
        session = self.api.start_ai_session(title="Missing Entity", mode="build")
        session = self.api.submit_ai_message("anademe movimiento al jugador", session_id=session["id"], mode="direct")

        self.assertEqual(session["status"], "proposal_ready")

        session = self.api.approve_ai_proposal(session_id=session["id"], allow_python=True)

        self.assertEqual(session["status"], "blocked")
        self.assertIn("la entidad objetivo Player no existe", session["messages"][-1]["content"])
        script_path = self.project_root / "scripts" / "player_movement_generated.py"
        self.assertFalse(script_path.exists())

    def test_engine_api_step_uses_runtime_step_when_step_frame_is_unavailable(self) -> None:
        class RuntimeOnlyGame:
            def __init__(self) -> None:
                self.calls = 0

            def step(self) -> None:
                self.calls += 1

        runtime_game = RuntimeOnlyGame()
        self.api.game = runtime_game  # type: ignore[assignment]

        self.api.step(3)

        self.assertEqual(runtime_game.calls, 3)

    def test_build_mode_executes_directly_without_manual_approve(self) -> None:
        self.api.create_entity(
            "Player",
            components={
                "Transform": {"enabled": True, "x": 0.0, "y": 0.0, "rotation": 0.0, "scale_x": 1.0, "scale_y": 1.0}
            },
        )

        session = self.api.start_ai_session(title="Build Movement", mode="build")
        session = self.api.submit_ai_message(
            "anademe movimiento al jugador",
            session_id=session["id"],
            mode="build",
            allow_python=True,
        )

        self.assertEqual(session["status"], "applied")
        self.assertTrue(session["last_apply"]["success"])

    def test_build_mode_uses_provider_generated_tool_calls_for_non_recipe_prompt(self) -> None:
        self.api.create_entity(
            "Player",
            components={
                "Transform": {"enabled": True, "x": 120.0, "y": 80.0, "rotation": 0.0, "scale_x": 1.0, "scale_y": 1.0}
            },
        )
        self.api.create_entity(
            "Enemy",
            components={
                "Transform": {"enabled": True, "x": 24.0, "y": 80.0, "rotation": 0.0, "scale_x": 1.0, "scale_y": 1.0}
            },
        )
        providers = self.api.ai_orchestrator._providers._providers  # type: ignore[attr-defined]
        providers[FakeGenerativeBuildProvider.id] = FakeGenerativeBuildProvider()
        self.api.set_ai_provider_policy(mode="local", preferred_provider=FakeGenerativeBuildProvider.id, model_name="fake-model")

        session = self.api.start_ai_session(title="Enemy Chase", mode="build")
        session = self.api.submit_ai_message(
            "hazme que el enemigo persiga al jugador",
            session_id=session["id"],
            mode="build",
            allow_python=True,
        )

        self.assertEqual(session["status"], "applied")
        script_path = self.project_root / "scripts" / "enemy_chase_generated.py"
        self.assertTrue(script_path.exists())
        enemy = self.api.get_entity("Enemy")
        self.assertIn("ScriptBehaviour", enemy["components"])

    def test_build_mode_normalizes_provider_script_paths_into_scripts_scope(self) -> None:
        self.api.create_entity(
            "Player",
            components={
                "Transform": {"enabled": True, "x": 120.0, "y": 80.0, "rotation": 0.0, "scale_x": 1.0, "scale_y": 1.0}
            },
        )
        self.api.create_entity(
            "Enemy",
            components={
                "Transform": {"enabled": True, "x": 24.0, "y": 80.0, "rotation": 0.0, "scale_x": 1.0, "scale_y": 1.0}
            },
        )
        providers = self.api.ai_orchestrator._providers._providers  # type: ignore[attr-defined]
        providers[FakeLoosePathProvider.id] = FakeLoosePathProvider()
        self.api.set_ai_provider_policy(mode="local", preferred_provider=FakeLoosePathProvider.id, model_name="fake-model")

        session = self.api.start_ai_session(title="Enemy Chase Paths", mode="build")
        session = self.api.submit_ai_message(
            "añádeme que el enemigo persiga al jugador",
            session_id=session["id"],
            mode="build",
            allow_python=True,
        )

        self.assertEqual(session["status"], "applied")
        script_path = self.project_root / "scripts" / "enemy_chase_generated.py"
        self.assertTrue(script_path.exists())
        enemy = self.api.get_entity("Enemy")
        self.assertEqual(enemy["components"]["ScriptBehaviour"]["module_path"], "scripts.enemy_chase_generated")


if __name__ == "__main__":
    unittest.main()
