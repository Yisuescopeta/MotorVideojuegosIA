import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.append(os.getcwd())

import pyray as rl

from engine.core.game import Game
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
            layout.handle_bottom_tab_input(rl.Vector2(80, 544))
            self.assertEqual(layout.active_bottom_tab, "CONSOLE")
            layout.handle_bottom_tab_input(rl.Vector2(152, 544))
            self.assertEqual(layout.active_bottom_tab, "TERMINAL")

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

        self.assertEqual(created[0].cwd, service.project_root.as_posix())
        self.assertEqual(panel.current_cwd, service.project_root.as_posix())

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
        self.assertEqual(created[-1].cwd, second_service.project_root.as_posix())

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

    def test_font_codepoints_cover_terminal_unicode_blocks(self) -> None:
        codepoints = TerminalPanel.build_font_codepoints()

        self.assertIn(ord("A"), codepoints)
        self.assertIn(ord("ó"), codepoints)
        self.assertIn(ord("│"), codepoints)
        self.assertIn(ord("█"), codepoints)
        self.assertIn(ord("✓"), codepoints)
        self.assertIn(ord("⣿"), codepoints)

    def test_font_metrics_use_loaded_font_measurements(self) -> None:
        panel = TerminalPanel()
        panel.render_font = Mock(baseSize=18)
        panel._font_ready = True

        with patch("pyray.measure_text_ex", return_value=rl.Vector2(11.0, 18.0)):
            panel._update_font_metrics()

        self.assertEqual(panel.cell_width, 11.0)
        self.assertEqual(panel.line_height, 18.0)
        self.assertEqual(panel.row_step, 18.0)

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

        self.assertEqual(backend.writes[0], "\x1b[4;320;960t")
        self.assertEqual(backend.writes[1], "\x1b[?0u")
        self.assertEqual(backend.writes[2], "\x1b[?996;10;18n")


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

    def test_open_project_restarts_terminal_panel_for_new_root(self) -> None:
        self.game.set_project_service(self.project_service)
        self.game.terminal_panel.backend = _FakeBackend(self.project_root.as_posix(), 80, 24, self.game.terminal_panel._on_backend_output)
        self.game.terminal_panel._session_started = True
        with patch.object(self.game.terminal_panel, "restart_session") as mock_restart:
            result = self.game.open_project(self.second_project_root.as_posix())

        self.assertTrue(result)
        self.assertGreaterEqual(mock_restart.call_count, 1)
        self.assertEqual(self.game.terminal_panel.last_project_root, self.second_project_root.as_posix())
