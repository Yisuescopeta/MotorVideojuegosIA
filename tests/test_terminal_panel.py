import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import pyray as rl

from engine.agent import AgentSessionService
from engine.core.game import Game
from engine.editor.agent_panel import AgentPanel
from engine.editor.editor_layout import EditorLayout
from engine.editor.terminal_panel import TerminalPanel, _TerminalScreen
from engine.levels.component_registry import create_default_registry
from engine.project.project_service import ProjectService
from engine.scenes.scene_manager import SceneManager


class _FakeBackend:
    def __init__(self, cwd: str, cols: int, rows: int, on_output) -> None:
        self.cwd = cwd
        self.cols = cols
        self.rows = rows
        self.on_output = on_output
        self.writes: list[str] = []
        self.closed = False
        self.exit_code = None

    def write_text(self, text: str) -> None:
        self.writes.append(text)

    def resize(self, cols: int, rows: int) -> None:
        self.cols = cols
        self.rows = rows

    def poll(self):
        return self.exit_code

    def close(self) -> None:
        self.closed = True
        self.exit_code = 0


class TerminalPanelTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temp_dir = tempfile.TemporaryDirectory()
        self.workspace = Path(self._temp_dir.name)
        self.global_state_dir = self.workspace / "global_state"

    def tearDown(self) -> None:
        self._temp_dir.cleanup()

    def _make_project(self, name: str) -> ProjectService:
        return ProjectService(self.workspace / name, global_state_dir=self.global_state_dir)

    def test_bottom_content_rect_starts_below_shared_header(self) -> None:
        with patch.object(EditorLayout, "_resize_render_textures", lambda *args, **kwargs: None):
            layout = EditorLayout(1280, 720)

        self.assertEqual(layout.get_bottom_content_rect().y, layout.bottom_header_rect.y + layout.bottom_header_rect.height)
        self.assertEqual(layout.get_bottom_content_rect().height + layout.bottom_header_rect.height, layout.bottom_rect.height)

    def test_handle_bottom_tab_input_switches_between_panels(self) -> None:
        with patch.object(EditorLayout, "_resize_render_textures", lambda *args, **kwargs: None):
            layout = EditorLayout(1280, 720)

        layout.bottom_header_rect = rl.Rectangle(0, 540, 1280, layout.TAB_HEIGHT)
        with patch("pyray.is_mouse_button_pressed", return_value=True):
            layout.handle_bottom_tab_input(rl.Vector2(100, 544))
            self.assertEqual(layout.active_bottom_tab, "FLOW")
            layout.handle_bottom_tab_input(rl.Vector2(170, 544))
            self.assertEqual(layout.active_bottom_tab, "CONSOLE")
            layout.handle_bottom_tab_input(rl.Vector2(240, 544))
            self.assertEqual(layout.active_bottom_tab, "TERMINAL")
            layout.handle_bottom_tab_input(rl.Vector2(310, 544))
            self.assertEqual(layout.active_bottom_tab, "AGENT")
            layout.handle_bottom_tab_input(rl.Vector2(20, 544))
            self.assertEqual(layout.active_bottom_tab, "PROJECT")

    def test_window_agent_action_opens_agent_bottom_panel(self) -> None:
        with patch.object(EditorLayout, "_resize_render_textures", lambda *args, **kwargs: None):
            layout = EditorLayout(1280, 720)

        layout._execute_menu_action("bottom_agent")

        self.assertEqual(layout.active_bottom_tab, "AGENT")

    def test_bottom_panel_height_round_trips_preferences(self) -> None:
        with patch.object(EditorLayout, "_resize_render_textures", lambda *args, **kwargs: None):
            layout = EditorLayout(1280, 720)

        layout.apply_editor_preferences({"editor_bottom_panel_height": 260})

        self.assertEqual(layout.bottom_height, 260)
        self.assertEqual(layout.export_editor_preferences()["editor_bottom_panel_height"], 260)

    def test_ensure_session_uses_active_project_root_as_cwd(self) -> None:
        service = self._make_project("TerminalProject")
        panel = TerminalPanel()
        panel.set_project_service(service)
        created: list[_FakeBackend] = []

        def _fake_create_backend(cwd: str, cols: int, rows: int):
            backend = _FakeBackend(cwd, cols, rows, panel._on_backend_output)
            created.append(backend)
            return backend

        panel.content_rect = rl.Rectangle(0, 0, 800, 240)
        with patch.object(panel, "_create_backend", side_effect=_fake_create_backend):
            panel.ensure_session()

        self.assertEqual(created[0].cwd, service.project_root_display.as_posix())
        self.assertEqual(panel.current_cwd, service.project_root_display.as_posix())
        self.assertIn("[policy: inherit]", panel.status_text)

    def test_terminal_builds_inherit_command_by_default(self) -> None:
        service = self._make_project("TerminalDefaultPolicy")
        panel = TerminalPanel()
        panel.set_project_service(service)

        self.assertEqual(panel._build_terminal_command(), "powershell.exe -NoLogo -NoProfile")

    def test_terminal_builds_remotesigned_command_when_enabled(self) -> None:
        service = self._make_project("TerminalRemoteSigned")
        service.save_project_settings(
            {
                "startup_scene": "levels/main_scene.json",
                "template": "empty",
                "terminal": {"execution_policy": "RemoteSigned"},
                "api": {"path_sandbox": False},
            }
        )
        panel = TerminalPanel()
        panel.set_project_service(service)

        self.assertEqual(panel._build_terminal_command(), "powershell.exe -NoLogo -NoProfile -ExecutionPolicy RemoteSigned")

    def test_terminal_builds_bypass_command_only_when_enabled(self) -> None:
        service = self._make_project("TerminalBypass")
        service.save_project_settings(
            {
                "startup_scene": "levels/main_scene.json",
                "template": "empty",
                "terminal": {"execution_policy": "Bypass"},
                "api": {"path_sandbox": False},
            }
        )
        panel = TerminalPanel()
        panel.set_project_service(service)

        self.assertEqual(panel._build_terminal_command(), "powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass")

    def test_switching_projects_restarts_terminal_session(self) -> None:
        first_service = self._make_project("FirstProject")
        second_service = self._make_project("SecondProject")
        panel = TerminalPanel()
        created: list[_FakeBackend] = []

        def _fake_create_backend(cwd: str, cols: int, rows: int):
            backend = _FakeBackend(cwd, cols, rows, panel._on_backend_output)
            created.append(backend)
            return backend

        panel.content_rect = rl.Rectangle(0, 0, 800, 240)
        panel.set_project_service(first_service)
        with patch.object(panel, "_create_backend", side_effect=_fake_create_backend):
            panel.ensure_session()
            first_backend = panel.backend
            panel.set_project_service(second_service)

        self.assertEqual(len(created), 2)
        self.assertTrue(first_backend.closed)
        self.assertEqual(created[-1].cwd, second_service.project_root_display.as_posix())

    def test_terminal_status_displays_active_policy_from_project_settings(self) -> None:
        service = self._make_project("TerminalPolicyStatus")
        service.save_project_settings(
            {
                "startup_scene": "levels/main_scene.json",
                "template": "empty",
                "terminal": {"execution_policy": "RemoteSigned"},
                "api": {"path_sandbox": False},
            }
        )
        panel = TerminalPanel()
        panel.set_project_service(service)
        panel.content_rect = rl.Rectangle(0, 0, 800, 240)

        with patch.object(panel, "_create_backend", return_value=_FakeBackend(service.project_root.as_posix(), 80, 24, panel._on_backend_output)):
            panel.ensure_session()

        self.assertIn("[policy: RemoteSigned]", panel.status_text)

    def test_terminal_does_not_start_without_active_project(self) -> None:
        service = ProjectService(self.workspace, global_state_dir=self.global_state_dir, auto_ensure=False)
        panel = TerminalPanel()
        panel.set_project_service(service)

        with patch.object(panel, "_create_backend") as mock_create_backend:
            panel.ensure_session()

        mock_create_backend.assert_not_called()
        self.assertEqual(panel.status_text, "No active project")

    def test_terminal_appends_backend_output_and_exit_status(self) -> None:
        panel = TerminalPanel()
        backend = _FakeBackend("C:/demo", 80, 24, panel._on_backend_output)
        backend.exit_code = 7
        panel.backend = backend

        panel._on_backend_output("PS> dir\nline2\n")
        panel._drain_output_queue()

        self.assertTrue(any(line.startswith("PS> dir") for line in panel.screen.visible_lines()))
        self.assertEqual(panel.status_text, "process exited with code 7")

    def test_terminal_screen_supports_basic_ansi_and_alternate_screen(self) -> None:
        screen = _TerminalScreen(20, 6)

        screen.feed("hello\r\nworld")
        self.assertTrue(any(line.startswith("hello") for line in screen.visible_lines()))
        self.assertTrue(any(line.startswith("world") for line in screen.visible_lines()))

        screen.feed("\x1b[2J")
        self.assertEqual(screen.visible_lines()[-1].strip(), "")

        screen.feed("\x1b[?1049h\x1b[HALT")
        self.assertTrue(screen.use_alt_buffer)
        self.assertEqual(screen.visible_lines()[0].startswith("ALT"), True)

        screen.feed("\x1b[?1049l")
        self.assertFalse(screen.use_alt_buffer)

    def test_terminal_screen_ignores_osc_titles_and_erases_chars(self) -> None:
        screen = _TerminalScreen(30, 6)

        screen.feed("prompt>\x1b]0;ignored title\x07")
        screen.feed("\x1b[1;3H\x1b[5X")

        self.assertFalse(any("ignored title" in line for line in screen.visible_lines()))
        self.assertTrue(screen.visible_lines()[0].startswith("pr"))

    def test_terminal_screen_ignores_unknown_private_csi_sequences(self) -> None:
        screen = _TerminalScreen(30, 6)

        screen.feed("hello")
        screen.feed("\x1b[>0q")
        screen.feed(" world")

        self.assertTrue(any(line.startswith("hello world") for line in screen.visible_lines()))

    def test_terminal_screen_uses_wrap_pending_instead_of_immediate_line_wrap(self) -> None:
        screen = _TerminalScreen(40, 6)

        screen.feed("1234567890123456789012345678901234567890")

        self.assertTrue(screen.visible_lines()[0].startswith("1234567890123456789012345678901234567890"))
        cursor = screen.visible_cursor()
        self.assertEqual((cursor.row, cursor.col), (0, 39))

        screen.feed("A")

        self.assertTrue(screen.visible_lines()[1].startswith("A"))
        cursor = screen.visible_cursor()
        self.assertEqual((cursor.row, cursor.col), (1, 1))

    def test_terminal_screen_defers_visible_updates_during_synchronized_output(self) -> None:
        screen = _TerminalScreen(30, 6)

        screen.feed("\x1b[1;1Hplaceholder")
        visible_before = screen.visible_lines()[0]

        screen.feed("\x1b[?2026h")
        screen.feed("\x1b[1;1Hhola")

        self.assertTrue(screen.visible_lines()[0].startswith(visible_before.strip()))
        self.assertFalse(screen.visible_lines()[0].startswith("hola"))

        screen.feed("\x1b[?2026l")

        self.assertTrue(screen.visible_lines()[0].startswith("hola"))

    def test_terminal_screen_commits_cursor_and_visibility_atomically_after_synchronized_output(self) -> None:
        screen = _TerminalScreen(30, 6)

        screen.feed("\x1b[1;1Hstart")
        initial_cursor = screen.visible_cursor()
        self.assertTrue(screen.visible_show_cursor())

        screen.feed("\x1b[?2026h")
        screen.feed("\x1b[4;6H\x1b[?25l")

        visible_during = screen.visible_cursor()
        self.assertEqual((visible_during.row, visible_during.col), (initial_cursor.row, initial_cursor.col))
        self.assertTrue(screen.visible_show_cursor())

        screen.feed("\x1b[?2026l")

        committed_cursor = screen.visible_cursor()
        self.assertEqual((committed_cursor.row, committed_cursor.col), (3, 5))
        self.assertFalse(screen.visible_show_cursor())

    def test_terminal_screen_replays_input_without_exposing_intermediate_placeholder_frame(self) -> None:
        screen = _TerminalScreen(40, 8)

        screen.feed("\x1b[2;3HAsk anything...")
        self.assertIn("Ask anything...", screen.visible_lines()[1])

        screen.feed("\x1b[?2026h")
        screen.feed("\x1b[2;3H\x1b[20X")
        screen.feed("\x1b[2;3Hhola")

        lines_during = screen.visible_lines()
        self.assertIn("Ask anything...", lines_during[1])
        self.assertNotIn("hola", lines_during[1])

        screen.feed("\x1b[?2026l")

        committed_line = screen.visible_lines()[1]
        self.assertIn("hola", committed_line)
        self.assertNotIn("Ask anything...", committed_line)

    def test_text_font_codepoints_cover_terminal_text_and_exclude_shapes(self) -> None:
        codepoints = TerminalPanel.build_text_font_codepoints()

        self.assertIn(ord("A"), codepoints)
        self.assertIn(ord("\u00f3"), codepoints)
        self.assertIn(ord("\u00bf"), codepoints)
        self.assertIn(ord("\u2026"), codepoints)
        self.assertIn(ord("\u2022"), codepoints)
        self.assertIn(TerminalPanel.REPLACEMENT_CODEPOINT, codepoints)
        self.assertNotIn(ord("\u2502"), codepoints)
        self.assertNotIn(ord("\u2588"), codepoints)
        self.assertNotIn(ord("\u28ff"), codepoints)

    def test_font_metrics_prefer_pillow_measurements_when_available(self) -> None:
        panel = TerminalPanel()
        panel.render_font = Mock(baseSize=18)
        panel._font_ready = True

        with patch.object(panel, "_resolve_font_path", return_value=Path("dummy.ttf")):
            with patch.object(panel, "_measure_font_metrics_with_pillow", return_value=(9.0, 19.0, 15.0, 0.0)):
                panel._update_font_metrics()

        self.assertEqual(panel.cell_width, 9.0)
        self.assertEqual(panel.line_height, 19.0)
        self.assertEqual(panel.row_step, 19.0)
        self.assertEqual(panel.text_baseline_offset, 15.0)
        self.assertEqual(panel.glyph_draw_offset_y, 0.0)

    def test_font_metrics_fall_back_to_raylib_when_pillow_is_unavailable(self) -> None:
        panel = TerminalPanel()
        panel.render_font = Mock(baseSize=18)
        panel._font_ready = True

        with patch.object(panel, "_resolve_font_path", return_value=Path("dummy.ttf")):
            with patch.object(panel, "_measure_font_metrics_with_pillow", return_value=None):
                with patch("pyray.measure_text_ex", return_value=rl.Vector2(11.0, 18.0)):
                    panel._update_font_metrics()

        self.assertEqual(panel.cell_width, 11.0)
        self.assertEqual(panel.line_height, 18.0)
        self.assertEqual(panel.row_step, 18.0)

    def test_terminal_panel_flags_special_render_cells(self) -> None:
        panel = TerminalPanel()

        self.assertTrue(panel._cell_requires_shape_renderer("\u2580"))
        self.assertTrue(panel._cell_requires_shape_renderer("\u2502"))
        self.assertTrue(panel._cell_requires_shape_renderer("\u2503"))
        self.assertTrue(panel._cell_requires_shape_renderer("\u2579"))
        self.assertTrue(panel._cell_requires_shape_renderer("\u28ff"))
        self.assertFalse(panel._cell_requires_shape_renderer("A"))

    def test_terminal_drawable_rect_uses_padding_in_main_buffer_and_top_inset_in_alt_buffer(self) -> None:
        panel = TerminalPanel()
        panel.content_rect = rl.Rectangle(10, 20, 300, 200)

        panel.screen.use_alt_buffer = False
        main_rect = panel.get_terminal_drawable_rect()
        self.assertEqual((main_rect.x, main_rect.y, main_rect.width, main_rect.height), (16.0, 22.0, 288.0, 196.0))

        panel.screen.use_alt_buffer = True
        alt_rect = panel.get_terminal_drawable_rect()
        self.assertEqual((alt_rect.x, alt_rect.y, alt_rect.width, alt_rect.height), (10.0, 24.0, 300.0, 196.0))

    def test_renderable_text_char_uses_replacement_when_glyph_is_missing(self) -> None:
        panel = TerminalPanel()
        panel._font_ready = True
        panel.render_font = Mock()
        panel._question_glyph_index = 31

        with patch("pyray.get_glyph_index", side_effect=[31, 42]):
            self.assertEqual(panel._renderable_text_char("\u00E1"), "\uFFFD")

    def test_renderable_text_char_keeps_supported_ascii(self) -> None:
        panel = TerminalPanel()
        panel._font_ready = True
        panel.render_font = Mock()
        panel._question_glyph_index = 31

        with patch("pyray.get_glyph_index", return_value=12):
            self.assertEqual(panel._renderable_text_char("A"), "A")

    def test_terminal_screen_applies_sgr_styles_to_cells(self) -> None:
        screen = _TerminalScreen(20, 6)

        screen.feed("\x1b[38;2;10;20;30;48;5;25;1;4mA\x1b[39;49;22;24mB")
        first_cell = screen.buffer[0][0]
        second_cell = screen.buffer[0][1]

        self.assertEqual(first_cell.char, "A")
        self.assertEqual(first_cell.style.fg, (10, 20, 30, 255))
        self.assertEqual(first_cell.style.bg, (0, 95, 175, 255))
        self.assertTrue(first_cell.style.bold)
        self.assertTrue(first_cell.style.underline)
        self.assertEqual(second_cell.char, "B")
        self.assertEqual(second_cell.style.fg, screen.default_style.fg)
        self.assertEqual(second_cell.style.bg, screen.default_style.bg)
        self.assertFalse(second_cell.style.bold)
        self.assertFalse(second_cell.style.underline)

    def test_terminal_sequence_handler_receives_queries(self) -> None:
        panel = TerminalPanel()
        backend = _FakeBackend("C:/demo", 120, 30, panel._on_backend_output)
        panel.backend = backend
        panel.content_rect = rl.Rectangle(0, 0, 960, 320)
        panel.cell_width = 10.0
        panel.line_height = 18.0
        panel.row_step = 18.0

        panel.screen.feed("\x1b[14t\x1b[?u\x1b[?996n\x1b]66;ignored\x07")

        self.assertEqual(backend.writes[0], "\x1b[4;316;948t")
        self.assertEqual(backend.writes[1], "\x1b[?0u")
        self.assertEqual(backend.writes[2], "\x1b[?996;10;18n")

    def test_terminal_sequence_handler_reports_alt_buffer_drawable_size_with_top_inset(self) -> None:
        panel = TerminalPanel()
        backend = _FakeBackend("C:/demo", 120, 30, panel._on_backend_output)
        panel.backend = backend
        panel.content_rect = rl.Rectangle(0, 0, 960, 320)
        panel.screen.use_alt_buffer = True

        panel.screen.feed("\x1b[14t")

        self.assertEqual(backend.writes[0], "\x1b[4;316;960t")


class AgentPanelTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temp_dir = tempfile.TemporaryDirectory()
        self.workspace = Path(self._temp_dir.name)
        self.global_state_dir = self.workspace / "global_state"
        self.project_service = ProjectService(self.workspace / "AgentPanelProject", global_state_dir=self.global_state_dir)

    def tearDown(self) -> None:
        self._temp_dir.cleanup()

    def test_agent_panel_launches_codex_login_when_openai_login_is_requested(self) -> None:
        panel = AgentPanel()
        service = AgentSessionService(project_root=self.project_service.project_root_display, global_state_dir=self.global_state_dir)
        panel.set_agent_service(service)

        with patch.object(service.login_service.codex_auth_store, "_resolve_cli_command", return_value="codex"):
            with patch.object(panel, "_launch_codex_login") as mock_launch:
                panel._send_text("/login openai")

        mock_launch.assert_called_once()
        self.assertIn("Codex login", panel.status_text)

    def test_agent_panel_rebinds_when_default_provider_becomes_runtime_ready(self) -> None:
        panel = AgentPanel()
        service = AgentSessionService(project_root=self.project_service.project_root_display, global_state_dir=self.global_state_dir)
        panel.set_agent_service(service)

        with patch.object(service, "get_session", return_value={"provider_id": "fake"}):
            with patch.object(
                service,
                "get_provider_status",
                side_effect=[
                    {"default_provider_id": "openai"},
                    {"runtime_ready": True},
                ],
            ):
                with patch.object(panel, "_restart_project_session") as mock_restart:
                    panel._maybe_rebind_authenticated_provider()

        mock_restart.assert_called_once()


class GameTerminalIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temp_dir = tempfile.TemporaryDirectory()
        self.workspace = Path(self._temp_dir.name)
        self.global_state_dir = self.workspace / "global_state"
        self.project_root = self.workspace / "GameProject"
        self.second_project_root = self.workspace / "GameProjectTwo"
        self.project_service = ProjectService(self.project_root, global_state_dir=self.global_state_dir)
        ProjectService(self.second_project_root, global_state_dir=self.global_state_dir)
        self.game = Game()
        self.game.set_scene_manager(SceneManager(create_default_registry()))
        with patch.object(EditorLayout, "_resize_render_textures", lambda *args, **kwargs: None):
            self.game.editor_layout = EditorLayout(1280, 720)
        self.game.set_project_service(self.project_service)
        self.game.set_scene_manager(self.game._scene_manager)

    def tearDown(self) -> None:
        self._temp_dir.cleanup()

    def test_set_project_service_propagates_to_terminal_panel(self) -> None:
        with patch.object(self.game.terminal_panel, "set_project_service") as mock_set_project_service:
            self.game.set_project_service(self.project_service)

        mock_set_project_service.assert_called_once_with(self.project_service)
        self.assertIs(self.game.editor_layout.terminal_panel, self.game.terminal_panel)

    def test_set_project_service_connects_agent_panel_to_live_engine_port(self) -> None:
        self.game.set_project_service(self.project_service)

        self.assertIsNotNone(self.game.agent_panel.agent_service)
        self.assertIsNotNone(self.game.agent_panel.agent_service.engine_port)
        self.assertIs(self.game.editor_layout.agent_panel, self.game.agent_panel)

    def test_set_project_service_reuses_agent_panel_binding_without_redundant_restarts(self) -> None:
        session_id_inicial = self.game.agent_panel.session_id

        with patch.object(
            self.game.agent_panel,
            "_restart_project_session",
            wraps=self.game.agent_panel._restart_project_session,
        ) as mock_restart:
            self.game.set_project_service(self.project_service)

        self.assertLessEqual(mock_restart.call_count, 1)
        self.assertEqual(self.game.agent_panel.session_id, session_id_inicial)

    def test_open_project_rebinds_agent_panel_to_active_project_and_clears_no_active_project_status(self) -> None:
        result = self.game.open_project(self.second_project_root.as_posix())

        self.assertTrue(result)
        self.assertIsNotNone(self.game.agent_panel.agent_service)
        self.assertTrue(self.game.agent_panel.session_id)
        self.assertEqual(self.game.agent_panel.agent_service.project_root, self.second_project_root.resolve())
        self.assertTrue(self.game.agent_panel.live_port_connected)
        self.assertNotEqual(self.game.agent_panel.status_text, "No active project")
        self.assertIn("GameProjectTwo", self.game.agent_panel.status_text)

    def test_open_project_cancels_previous_agent_session_before_binding_new_project(self) -> None:
        servicio_anterior = self.game.agent_panel.agent_service
        session_id_anterior = self.game.agent_panel.session_id

        result = self.game.open_project(self.second_project_root.as_posix())

        self.assertTrue(result)
        self.assertIsNotNone(servicio_anterior)
        self.assertTrue(servicio_anterior.get_session(session_id_anterior)["cancelled"])
        self.assertNotEqual(self.game.agent_panel.session_id, session_id_anterior)
        self.assertEqual(self.game.agent_panel.agent_service.project_root, self.second_project_root.resolve())

    def test_agent_panel_live_engine_port_serves_engine_tools(self) -> None:
        self.game.set_project_service(self.project_service)
        service = self.game.agent_panel.agent_service

        result = service.send_message(self.game.agent_panel.session_id, "capabilities")

        tool_messages = [message for message in result["messages"] if message["role"] == "tool"]
        self.assertTrue(tool_messages)
        self.assertTrue(tool_messages[-1]["tool_result"]["success"])

    def test_open_project_restarts_terminal_panel_for_new_root(self) -> None:
        self.game.set_project_service(self.project_service)
        self.game.terminal_panel.backend = _FakeBackend(self.project_root.as_posix(), 80, 24, self.game.terminal_panel._on_backend_output)
        self.game.terminal_panel._session_started = True
        with patch.object(self.game.terminal_panel, "restart_session") as mock_restart:
            result = self.game.open_project(self.second_project_root.as_posix())

        self.assertTrue(result)
        self.assertGreaterEqual(mock_restart.call_count, 1)
        self.assertEqual(self.game.terminal_panel.last_project_root, self.second_project_root.as_posix())
