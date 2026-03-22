import os
import sys
import unittest

sys.path.append(os.getcwd())

from engine.editor.assistant_panel import AssistantPanel


class FakeAssistantAPI:
    def __init__(self) -> None:
        self.provider_policy = {
            "mode": "local",
            "preferred_provider": "ollama_local",
            "model_name": "llama3.1:8b",
            "endpoint": "http://127.0.0.1:11434",
        }
        self.sessions = {
            "session-1": {
                "id": "session-1",
                "title": "Existing Session",
                "status": "planned",
                "mode": "plan",
                "provider": "ollama_local",
                "model_name": "llama3.1:8b",
                "prompt": "añademe movilidad al personaje",
                "answers": {},
                "messages": [
                    {"role": "assistant", "content": "Resumen del plan.\nAnalisis: Hay una ruta clara.\nPuedes pasar a Build para ejecutarlo sobre el proyecto.", "kind": "plan"},
                ],
                "pending_questions": [],
                "approval": None,
                "last_apply": None,
                "plan_response": {
                    "summary": "Resumen del plan.",
                    "reasoning": "Hay una ruta clara.",
                    "project_findings": ["Entidad seleccionada: Player"],
                    "next_steps": ["Preparar cambios", "Ejecutar en Build"],
                    "blocking_questions": [],
                    "can_build_now": True,
                },
                "context_window": {"recent_scripts": [], "capabilities": []},
            }
        }
        self.active_session_id = "session-1"
        self.answer_calls = []
        self.submit_calls = []
        self.approve_calls = []
        self.reject_calls = []
        self.undo_calls = []

    def start_ai_session(self, title: str = "", mode: str = "plan", activate: bool = True):
        session = {
            "id": "session-2",
            "title": title or "Game Authoring",
            "status": "idle",
            "mode": mode,
            "provider": self.provider_policy["preferred_provider"],
            "model_name": self.provider_policy["model_name"],
            "messages": [{"role": "assistant", "content": "Assistant ready.", "kind": "text"}],
            "pending_questions": [],
            "approval": None,
            "last_apply": None,
            "plan_response": {
                "summary": "",
                "reasoning": "",
                "project_findings": [],
                "next_steps": [],
                "blocking_questions": [],
                "can_build_now": False,
            },
            "context_window": {"recent_scripts": [], "capabilities": []},
        }
        self.sessions[session["id"]] = session
        if activate:
            self.active_session_id = session["id"]
        return session

    def get_ai_session(self, session_id=None):
        resolved = session_id or self.active_session_id
        return self.sessions.get(resolved, {})

    def submit_ai_message(self, prompt: str, session_id=None, mode: str = "plan", answers=None, allow_python: bool = False, allow_engine_changes: bool = False, activate: bool = True):
        self.submit_calls.append((session_id, prompt, mode))
        session = self.sessions[session_id or self.active_session_id]
        session["messages"] = session["messages"] + [{"role": "user", "content": prompt, "kind": "text"}]
        session["pending_questions"] = []
        if mode == "plan":
            session["status"] = "planned"
            session["approval"] = None
            session["plan_response"] = {
                "summary": "Plan listo para este cambio.",
                "reasoning": "He localizado una forma concreta de hacerlo.",
                "project_findings": ["Entidad seleccionada: Player"],
                "next_steps": ["Cambiar a Build", "Ejecutar sobre la escena"],
                "blocking_questions": [],
                "can_build_now": True,
            }
            session["messages"] = session["messages"] + [
                {"role": "assistant", "content": "Plan listo para este cambio.\nAnalisis: He localizado una forma concreta de hacerlo.\nPuedes pasar a Build para ejecutarlo sobre el proyecto.", "kind": "plan"},
            ]
        else:
            session["status"] = "applied"
            session["approval"] = {
                "id": "approval-1",
                "status": "applied",
                "summary": "Create gameplay slice",
                "diff": {
                    "summary": "3 tool call(s) prepared for review.",
                    "entities": ["Player", "MainCamera"],
                    "files": ["scripts/generated_platformer_logic.py"],
                    "tools": ["create_entity", "create_camera2d", "write_script"],
                    "risk_notes": ["elevated"],
                },
                "tool_calls": [
                    {"id": "call-1", "tool_name": "create_entity", "arguments": {"name": "Player"}},
                    {"id": "call-2", "tool_name": "create_camera2d", "arguments": {"name": "MainCamera"}},
                    {"id": "call-3", "tool_name": "write_script", "arguments": {"target": "scripts/generated_platformer_logic.py"}},
                ],
            }
            session["last_apply"] = {"snapshot_id": "snapshot-1"}
            session["messages"] = session["messages"] + [{"role": "assistant", "content": "Changes applied.", "kind": "text"}]
        if activate:
            self.active_session_id = session["id"]
        return session

    def answer_ai_question(self, answer: str, session_id=None, question_id=None, mode=None, allow_python: bool = False, allow_engine_changes: bool = False):
        self.answer_calls.append((session_id, question_id, answer, mode))
        session = self.sessions[session_id or self.active_session_id]
        session["messages"] = session["messages"] + [{"role": "user", "content": answer, "kind": "text"}]
        session["pending_questions"] = []
        if mode == "build":
            session["status"] = "applied"
            session["approval"] = {
                "id": "approval-question",
                "status": "applied",
                "summary": "Proposal from answer",
                "diff": {
                    "summary": "1 tool call(s) prepared for review.",
                    "entities": ["Player"],
                    "files": [],
                    "tools": ["add_component"],
                    "risk_notes": [],
                },
                "tool_calls": [
                    {"id": "call-answer", "tool_name": "add_component", "arguments": {"entity_name": "Player"}},
                ],
            }
            session["last_apply"] = {"snapshot_id": "snapshot-1"}
            session["messages"] = session["messages"] + [{"role": "assistant", "content": "Changes applied.", "kind": "text"}]
            return session
        session["status"] = "planned"
        session["plan_response"] = {
            "summary": "Plan ajustado.",
            "reasoning": "La respuesta ya permite cerrar el analisis.",
            "project_findings": [],
            "next_steps": ["Cambiar a Build"],
            "blocking_questions": [],
            "can_build_now": True,
        }
        return session

    def approve_ai_proposal(self, session_id=None, allow_python: bool = False, allow_engine_changes: bool = False):
        self.approve_calls.append((session_id, allow_python, allow_engine_changes))
        session = self.sessions[session_id or self.active_session_id]
        session["status"] = "applied"
        session["last_apply"] = {"snapshot_id": "snapshot-1"}
        session["messages"] = session["messages"] + [{"role": "assistant", "content": "Changes applied.", "kind": "text"}]
        return session

    def reject_ai_proposal(self, session_id=None):
        self.reject_calls.append(session_id)
        session = self.sessions[session_id or self.active_session_id]
        session["status"] = "rejected"
        return session

    def undo_ai_last_apply(self, session_id=None):
        self.undo_calls.append(session_id)
        session = self.sessions[session_id or self.active_session_id]
        session["status"] = "rolled_back"
        return session

    def get_ai_provider_diagnostics(self):
        return {
            "selected_provider": self.provider_policy["preferred_provider"],
            "policy": dict(self.provider_policy),
            "models": ["llama3.1:8b", "qwen2.5-coder:7b"],
            "providers": [
                {"id": "ollama_local", "available": True},
                {"id": "openai_compatible_http", "available": False},
            ],
        }

    def update_ai_project_memory(self, patch):
        self.provider_policy.update(patch.get("provider_policy", {}))
        return {"success": True}


class AssistantPanelSmokeTests(unittest.TestCase):
    def test_panel_loads_existing_session_on_set_api(self) -> None:
        api = FakeAssistantAPI()
        panel = AssistantPanel()

        panel.set_api(api)

        self.assertEqual(panel.current_session_id, "session-1")
        self.assertEqual(panel.status_line, "planned")
        self.assertEqual(panel._pending_questions(), [])

    def test_panel_routes_question_answers_and_build_requests(self) -> None:
        api = FakeAssistantAPI()
        panel = AssistantPanel()
        panel.set_api(api)

        panel.session_data["pending_questions"] = [{"id": "enemies", "text": "What enemies do you want?", "choices": ["none", "slime"], "rationale": ""}]
        panel.input_text = "slime"
        panel._submit_input()
        panel._drain_background_tasks_for_tests()
        self.assertEqual(api.answer_calls[0][2], "slime")

        panel._create_new_session()
        panel.input_text = "Create a gameplay slice"
        panel.interaction_mode = "build"
        panel._submit_input()
        panel._drain_background_tasks_for_tests()
        self.assertEqual(api.submit_calls[-1][1], "Create a gameplay slice")
        self.assertTrue(panel._can_undo_last_apply())

    def test_panel_apply_reject_undo_and_reopen_smoke(self) -> None:
        api = FakeAssistantAPI()
        panel = AssistantPanel()
        panel.set_api(api)
        panel._create_new_session()
        panel.interaction_mode = "build"
        panel.input_text = "Create a gameplay slice"
        panel._submit_input()
        panel._drain_background_tasks_for_tests()

        self.assertTrue(panel._can_undo_last_apply())

        panel._undo_last_apply()
        panel._drain_background_tasks_for_tests()
        self.assertEqual(api.undo_calls[-1], "session-2")

        reopened = AssistantPanel()
        reopened.set_api(api)
        self.assertEqual(reopened.current_session_id, "session-2")
        self.assertEqual(reopened.provider_label, "ollama_local")

    def test_header_layout_switches_for_narrow_widths(self) -> None:
        panel = AssistantPanel()
        narrow_header = type("Header", (), {"x": 0.0, "y": 0.0, "width": 280.0})()
        wide_header = type("Header", (), {"x": 0.0, "y": 0.0, "width": 420.0})()

        narrow_rows = panel._header_button_rows(narrow_header, True)
        wide_rows = panel._header_button_rows(wide_header, False)

        self.assertEqual(len(narrow_rows[0]), 2)
        self.assertEqual(len(narrow_rows[1]), 2)
        self.assertEqual(len(narrow_rows[2]), 3)
        self.assertEqual(len(wide_rows[0]), 4)
        self.assertEqual(len(wide_rows[1]), 3)

    def test_panel_formats_choice_labels_for_question_buttons(self) -> None:
        panel = AssistantPanel()

        self.assertEqual(panel._format_choice_label("editar_proyecto_existente"), "Editar proyecto existente")

    def test_panel_auto_applies_when_build_answer_finishes_question_flow(self) -> None:
        api = FakeAssistantAPI()
        panel = AssistantPanel()
        panel.set_api(api)
        panel.session_data["pending_questions"] = [{"id": "enemies", "text": "What enemies do you want?", "choices": ["none", "slime"], "rationale": ""}]
        panel.interaction_mode = "build"
        panel.input_text = "slime"

        panel._submit_input()
        panel._drain_background_tasks_for_tests()

        self.assertEqual(api.answer_calls[-1][2], "slime")
        self.assertEqual(panel.status_line, "applied")

    def test_panel_switch_to_build_reuses_last_plan_when_ready(self) -> None:
        api = FakeAssistantAPI()
        panel = AssistantPanel()
        panel.set_api(api)

        panel._toggle_interaction_mode()
        panel._drain_background_tasks_for_tests()

        self.assertEqual(panel.interaction_mode, "build")
        self.assertTrue(api.submit_calls)
        self.assertEqual(api.submit_calls[-1][2], "build")

    def test_panel_enters_working_state_while_background_request_runs(self) -> None:
        api = FakeAssistantAPI()
        panel = AssistantPanel()
        panel.set_api(api)

        original_submit = api.submit_ai_message

        def delayed_submit(*args, **kwargs):
            import time
            time.sleep(0.05)
            return original_submit(*args, **kwargs)

        api.submit_ai_message = delayed_submit
        panel._create_new_session()
        panel.interaction_mode = "build"
        panel.input_text = "Create a gameplay slice"

        panel._submit_input()

        self.assertEqual(panel.status_line, "working")
        panel._drain_background_tasks_for_tests()
        self.assertEqual(panel.status_line, "applied")


if __name__ == "__main__":
    unittest.main()
