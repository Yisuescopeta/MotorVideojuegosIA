"""
engine/editor/agent_panel.py - Panel visual del agente integrado del editor.

PROPOSITO:
    Capa de presentacion del agente nativo. Se encarga de:
      - Dibujar cabecera con selectores de provider y modelo.
      - Mostrar transcript con tarjetas por rol (user, assistant, tool, system).
      - Gestionar aprobaciones pendientes con preview expandible.
      - Ofrecer un composer pulido con soporte Enter/Shift+Enter.

    La logica del agente (`AgentSessionService`, runtime, providers, credenciales,
    live engine port, guards de secretos/rutas/comandos) permanece intacta.
    Este archivo solo orquesta UI e input.
"""

from __future__ import annotations

import os
import subprocess
from typing import Any, Callable

import pyray as rl

from engine.agent import (
    AgentActionStatus,
    AgentPermissionMode,
    AgentSessionService,
    EditorLiveAgentEnginePort,
    list_model_presets,
)
from engine.editor.render_safety import editor_scissor
from engine.project.project_service import ProjectService


class AgentPanel:
    """Panel visual del agente: chat, selector provider/modelo y aprobaciones."""

    # ========================================
    # Constantes de layout
    # ========================================
    HEADER_HEIGHT = 40
    CONTEXT_BAR_HEIGHT = 20
    COMPOSER_HEIGHT = 58
    LINE_HEIGHT = 14
    FONT_SIZE = 10
    # Compatibilidad con codigo previo que consultaba estas constantes.
    TOOLBAR_HEIGHT = HEADER_HEIGHT
    INPUT_HEIGHT = COMPOSER_HEIGHT

    # ========================================
    # Paleta Unity-dark
    # ========================================
    UNITY_BG = rl.Color(30, 30, 30, 255)
    UNITY_BG_DEEP = rl.Color(22, 22, 22, 255)
    UNITY_BG_MID = rl.Color(38, 38, 38, 255)
    UNITY_HEADER = rl.Color(42, 42, 42, 255)
    UNITY_BORDER = rl.Color(25, 25, 25, 255)
    UNITY_BORDER_DIM = rl.Color(54, 54, 54, 255)
    UNITY_BUTTON = rl.Color(58, 58, 58, 255)
    UNITY_BUTTON_HOVER = rl.Color(78, 78, 78, 255)
    UNITY_TEXT = rl.Color(210, 210, 210, 255)
    UNITY_TEXT_BRIGHT = rl.Color(235, 235, 235, 255)
    UNITY_TEXT_DIM = rl.Color(135, 135, 135, 255)
    UNITY_BLUE = rl.Color(44, 93, 135, 255)
    UNITY_BLUE_HOVER = rl.Color(60, 115, 165, 255)
    UNITY_WARN = rl.Color(205, 133, 63, 255)
    UNITY_ERR = rl.Color(220, 90, 90, 255)
    UNITY_OK = rl.Color(110, 180, 110, 255)
    UNITY_AMBER = rl.Color(220, 170, 80, 255)

    # Tarjetas por rol
    CARD_USER = rl.Color(44, 60, 80, 255)
    CARD_USER_BAR = rl.Color(95, 150, 220, 255)
    CARD_ASSISTANT = rl.Color(45, 45, 54, 255)
    CARD_ASSISTANT_BAR = rl.Color(170, 170, 195, 255)
    CARD_TOOL = rl.Color(44, 58, 46, 255)
    CARD_TOOL_BAR = rl.Color(130, 180, 130, 255)
    CARD_TOOL_ERR_BAR = rl.Color(210, 110, 110, 255)
    CARD_SYSTEM = rl.Color(52, 46, 36, 255)
    CARD_SYSTEM_BAR = rl.Color(200, 175, 110, 255)
    CARD_PENDING = rl.Color(68, 52, 32, 255)
    CARD_PENDING_BAR = rl.Color(220, 170, 80, 255)

    def __init__(self) -> None:
        # --- Estado publico (conservado) ---
        self.project_service: ProjectService | None = None
        self.live_game = None
        self.live_scene_manager = None
        self.agent_service: AgentSessionService | None = None
        self.session_id = ""
        self.permission_mode = AgentPermissionMode.CONFIRM_ACTIONS
        self.input_text = ""
        self.has_focus = False
        self.status_text = "No active project"
        self.preview_action_id = ""  # compatibilidad con API previa
        self.pending_login_provider = ""
        self.login_input_text = ""
        self.login_has_focus = False
        self.live_port_connected = False
        self._binding_key: tuple[str, int, int] | None = None
        self.content_rect = rl.Rectangle(0, 0, 0, 0)
        self.input_rect = rl.Rectangle(0, 0, 0, 0)

        # --- Estado UI nuevo ---
        self._panel_rect = rl.Rectangle(0, 0, 0, 0)
        self._header_rect = rl.Rectangle(0, 0, 0, 0)
        self._context_rect = rl.Rectangle(0, 0, 0, 0)
        self._transcript_rect = rl.Rectangle(0, 0, 0, 0)
        self._approvals_rect = rl.Rectangle(0, 0, 0, 0)
        self._composer_rect = rl.Rectangle(0, 0, 0, 0)
        self._scroll_offset = 0.0
        self._auto_scroll = True
        self._last_event_count = 0
        self._expanded_action_ids: set[str] = set()
        # Dropdowns
        self._provider_dropdown_open = False
        self._model_dropdown_open = False
        self._provider_chip_rect = rl.Rectangle(0, 0, 0, 0)
        self._model_chip_rect = rl.Rectangle(0, 0, 0, 0)
        # Editor de modelo custom
        self._model_custom_editing = False
        self._model_custom_buffer = ""
        self._model_custom_rect = rl.Rectangle(0, 0, 0, 0)
        self._model_custom_has_focus = False

    # ========================================
    # API publica (firmas preservadas)
    # ========================================
    def set_project_service(self, project_service: ProjectService | None) -> None:
        self.project_service = project_service
        if project_service is None or not project_service.has_project:
            self.agent_service = None
            self.session_id = ""
            self._binding_key = None
            self.status_text = "No active project"
            return
        self._restart_project_session()

    def set_live_engine(
        self,
        *,
        game: Any = None,
        scene_manager: Any = None,
        project_service: ProjectService | None = None,
    ) -> None:
        self.live_game = game
        self.live_scene_manager = scene_manager
        if project_service is not None:
            self.project_service = project_service
        if self.project_service is not None and self.project_service.has_project:
            self._restart_project_session()

    def set_agent_service(self, service: AgentSessionService | None) -> None:
        self.agent_service = service
        self.session_id = ""
        self._binding_key = None
        if service is not None:
            session = service.create_session(
                permission_mode=self.permission_mode.value, title="Editor Agent"
            )
            self.session_id = str(session["session_id"])
            self.status_text = "Agent ready"

    def shutdown(self) -> None:
        if self.agent_service is not None and self.session_id:
            try:
                self.agent_service.cancel_session(self.session_id)
            except Exception:
                pass
        self.status_text = "Agent stopped"

    def captures_keyboard(self) -> bool:
        return self.has_focus or self._model_custom_has_focus

    # ========================================
    # Orquestacion de sesion
    # ========================================
    def _restart_project_session(self) -> None:
        if self.project_service is None or not self.project_service.has_project:
            self.agent_service = None
            self.session_id = ""
            self._binding_key = None
            self.live_port_connected = False
            self.status_text = "No active project"
            return
        binding_key = (
            self.project_service.project_root_display.as_posix(),
            id(self.live_game),
            id(self.live_scene_manager),
        )
        if self._binding_key == binding_key and self.agent_service is not None and self.session_id:
            return
        if self.agent_service is not None and self.session_id:
            try:
                self.agent_service.cancel_session(self.session_id)
            except Exception:
                pass
        self._binding_key = binding_key
        engine_port = None
        if self.live_game is not None and self.live_scene_manager is not None:
            engine_port = EditorLiveAgentEnginePort(
                game=self.live_game,
                scene_manager=self.live_scene_manager,
                project_service=self.project_service,
            )
        self.live_port_connected = engine_port is not None
        self.agent_service = AgentSessionService(
            project_root=self.project_service.project_root_display,
            engine_port=engine_port,
        )
        provider_id = "fake"
        model = ""
        stream = False
        try:
            status = self.agent_service.get_provider_status()
            provider_id = str(status.get("default_provider_id", "fake") or "fake")
            settings = dict(status.get("settings", {}))
            model = str(settings.get("model", ""))
            stream = bool(settings.get("stream", False))
            if provider_id != "fake":
                selected = self.agent_service.get_provider_status(provider_id)
                if (
                    selected.get("auth_status") == "missing"
                    or not selected.get("runtime_ready", False)
                ):
                    provider_id = "fake"
                    model = ""
                    stream = False
        except Exception:
            provider_id = "fake"
        session = self.agent_service.create_session(
            permission_mode=self.permission_mode.value,
            title="Editor Agent",
            provider_id=provider_id,
            model=model,
            stream=stream,
        )
        self.session_id = str(session["session_id"])
        project_name = (
            self.project_service.project_name if self.project_service.has_project else "project"
        )
        self.status_text = f"Agent ready: {project_name}"
        self._reset_scroll()

    def _new_session(self) -> None:
        """Crea una sesion nueva preservando provider/model/stream actuales."""
        if self.agent_service is None:
            return
        provider_id, model, stream = self._current_session_config()
        if self.session_id:
            try:
                self.agent_service.cancel_session(self.session_id)
            except Exception:
                pass
        try:
            session = self.agent_service.create_session(
                permission_mode=self.permission_mode.value,
                title="Editor Agent",
                provider_id=provider_id or "fake",
                model=model,
                stream=stream,
            )
            self.session_id = str(session["session_id"])
            self.status_text = "Nueva sesion creada"
            self._expanded_action_ids.clear()
            self._reset_scroll()
        except Exception as exc:
            self.status_text = f"New session failed: {exc}"

    def _apply_provider_change(self, provider_id: str) -> None:
        """Persiste el provider como predeterminado y recrea sesion si cambia."""
        if self.agent_service is None:
            return
        new_provider = str(provider_id or "").strip()
        if not new_provider:
            return
        try:
            status = self._safe_provider_status(new_provider)
            model = self._recommended_model(new_provider, status)
            self.agent_service.set_default_provider(new_provider, model=model)
            self._binding_key = None
            self._restart_project_session()
            self.status_text = f"Provider = {new_provider}"
            if (
                str(status.get("auth_status", "")) == "missing"
                and bool(status.get("login_supported", False))
            ):
                self.status_text = f"Provider = {new_provider} (auth missing: usa Login)"
        except Exception as exc:
            self.status_text = f"Provider error: {exc}"

    def _apply_model_change(self, model: str) -> None:
        """Persiste el modelo como predeterminado y lo aplica a la sesion viva."""
        if self.agent_service is None or not self.session_id:
            return
        new_model = str(model or "").strip()
        if not new_model:
            return
        provider_id, _current_model, _stream = self._current_session_config()
        try:
            self.agent_service.set_default_provider(provider_id or "fake", model=new_model)
        except Exception as exc:
            self.status_text = f"Model persist error: {exc}"
            return
        try:
            self._send_text(f"/model {new_model}")
        except Exception as exc:
            self.status_text = f"Model set error: {exc}"

    def _apply_streaming_toggle(self) -> None:
        if self.agent_service is None:
            return
        provider_id, model, stream = self._current_session_config()
        new_stream = not stream
        try:
            self.agent_service.provider_settings_store.set_default_provider(
                provider_id or "fake",
                model=model,
                stream=new_stream,
            )
            self._binding_key = None
            self._restart_project_session()
            self.status_text = f"Streaming = {'on' if new_stream else 'off'}"
        except Exception as exc:
            self.status_text = f"Streaming error: {exc}"

    def _current_session_config(self) -> tuple[str, str, bool]:
        """Devuelve (provider_id, model, stream) de la sesion activa."""
        provider_id = "fake"
        model = ""
        stream = False
        if self.agent_service is None or not self.session_id:
            return provider_id, model, stream
        try:
            session = self.agent_service.get_session(self.session_id)
            provider_id = str(session.get("provider_id", "fake") or "fake")
            runtime = session.get("runtime_config", {}) or {}
            model = str(runtime.get("model", "") or "")
            stream = bool(runtime.get("stream", False))
        except Exception:
            pass
        return provider_id, model, stream

    def _recommended_model(self, provider_id: str, status: dict | None = None) -> str:
        presets = list_model_presets(provider_id)
        if presets:
            return presets[0]
        if status and status.get("default_model"):
            return str(status.get("default_model", ""))
        return ""

    # ========================================
    # Input
    # ========================================
    def update_input(self, active: bool) -> None:
        if not active:
            return
        mouse = rl.get_mouse_position()
        clicked = rl.is_mouse_button_pressed(rl.MOUSE_BUTTON_LEFT)
        if clicked:
            self.has_focus = rl.check_collision_point_rec(mouse, self.input_rect)
            self._model_custom_has_focus = (
                self._model_custom_editing
                and rl.check_collision_point_rec(mouse, self._model_custom_rect)
            )

        # Scroll con rueda sobre el transcript
        if rl.check_collision_point_rec(mouse, self._transcript_rect):
            wheel = rl.get_mouse_wheel_move()
            if wheel:
                self._scroll_offset = max(0.0, self._scroll_offset + float(wheel) * 24.0)
                self._auto_scroll = self._scroll_offset <= 0.5

        if self._model_custom_has_focus:
            self._update_custom_model_input()
            return
        if not self.has_focus:
            return

        target = "login" if self.pending_login_provider else "chat"
        ctrl_down = rl.is_key_down(rl.KEY_LEFT_CONTROL) or rl.is_key_down(rl.KEY_RIGHT_CONTROL)
        shift_down = rl.is_key_down(rl.KEY_LEFT_SHIFT) or rl.is_key_down(rl.KEY_RIGHT_SHIFT)

        if ctrl_down:
            if rl.is_key_pressed(rl.KEY_C):
                text_to_copy = self.login_input_text if target == "login" else self.input_text
                rl.set_clipboard_text(text_to_copy)
            elif rl.is_key_pressed(rl.KEY_V):
                clipboard_content = rl.get_clipboard_text()
                if clipboard_content:
                    if target == "login" and len(self.login_input_text) + len(clipboard_content) <= 2000:
                        self.login_input_text += clipboard_content
                    elif target == "chat" and len(self.input_text) + len(clipboard_content) <= 2000:
                        self.input_text += clipboard_content

        if rl.is_key_pressed(rl.KEY_BACKSPACE):
            if target == "login" and self.login_input_text:
                self.login_input_text = self.login_input_text[:-1]
            elif target == "chat" and self.input_text:
                self.input_text = self.input_text[:-1]

        while True:
            codepoint = rl.get_char_pressed()
            if codepoint == 0:
                break
            if codepoint in (10, 13):
                continue
            try:
                char = chr(codepoint)
            except ValueError:
                continue
            if char.isprintable():
                if target == "login" and len(self.login_input_text) < 2000:
                    self.login_input_text += char
                elif target == "chat" and len(self.input_text) < 2000:
                    self.input_text += char

        if rl.is_key_pressed(rl.KEY_ENTER) or rl.is_key_pressed(rl.KEY_KP_ENTER):
            if target == "chat" and shift_down and len(self.input_text) < 2000:
                # Shift+Enter: salto de linea manual
                self.input_text += "\n"
            else:
                self._send_current_input()

    def _update_custom_model_input(self) -> None:
        ctrl_down = rl.is_key_down(rl.KEY_LEFT_CONTROL) or rl.is_key_down(rl.KEY_RIGHT_CONTROL)
        if ctrl_down:
            if rl.is_key_pressed(rl.KEY_V):
                clipboard_content = rl.get_clipboard_text()
                if clipboard_content and len(self._model_custom_buffer) + len(clipboard_content) <= 200:
                    self._model_custom_buffer += clipboard_content
            elif rl.is_key_pressed(rl.KEY_C):
                rl.set_clipboard_text(self._model_custom_buffer)
        if rl.is_key_pressed(rl.KEY_BACKSPACE) and self._model_custom_buffer:
            self._model_custom_buffer = self._model_custom_buffer[:-1]
        while True:
            codepoint = rl.get_char_pressed()
            if codepoint == 0:
                break
            if codepoint in (10, 13):
                continue
            try:
                char = chr(codepoint)
            except ValueError:
                continue
            if char.isprintable() and len(self._model_custom_buffer) < 200:
                self._model_custom_buffer += char
        if rl.is_key_pressed(rl.KEY_ENTER) or rl.is_key_pressed(rl.KEY_KP_ENTER):
            self._apply_custom_model()
        elif rl.is_key_pressed(rl.KEY_ESCAPE):
            self._model_custom_editing = False
            self._model_custom_has_focus = False

    def _apply_custom_model(self) -> None:
        model = self._model_custom_buffer.strip()
        self._model_custom_editing = False
        self._model_custom_has_focus = False
        self._model_custom_buffer = ""
        self._model_dropdown_open = False
        if model:
            self._apply_model_change(model)

    # ========================================
    # Render
    # ========================================
    def render(self, x: int, y: int, width: int, height: int) -> None:
        self._panel_rect = rl.Rectangle(
            float(x), float(y), float(max(0, width)), float(max(0, height))
        )
        self._compute_layout(x, y, width, height)
        rl.draw_rectangle_rec(self._panel_rect, self.UNITY_BG)

        self._draw_header_bar()
        self._draw_context_bar()
        with editor_scissor(self._transcript_rect):
            self._draw_transcript()
        self._draw_pending_approvals()
        self._draw_composer()
        self._draw_overlay_dropdowns()

    def _compute_layout(self, x: int, y: int, width: int, height: int) -> None:
        hh = self.HEADER_HEIGHT
        cbh = self.CONTEXT_BAR_HEIGHT
        composer_h = self.COMPOSER_HEIGHT
        self._header_rect = rl.Rectangle(float(x), float(y), float(width), float(hh))
        self._context_rect = rl.Rectangle(float(x), float(y + hh), float(width), float(cbh))

        pending_h = self._measure_pending_height(width)
        top = y + hh + cbh
        bottom = y + height - composer_h
        # Reservamos un minimo para el transcript: no dejamos que approvals lo aplaste.
        min_transcript = 60
        max_pending = max(0, (bottom - top) - min_transcript)
        pending_h = min(pending_h, max_pending)
        transcript_bottom = max(top, bottom - pending_h)

        self._transcript_rect = rl.Rectangle(
            float(x), float(top), float(width), float(max(0, transcript_bottom - top))
        )
        self._approvals_rect = rl.Rectangle(
            float(x), float(transcript_bottom), float(width), float(max(0, bottom - transcript_bottom))
        )
        self._composer_rect = rl.Rectangle(float(x), float(bottom), float(width), float(composer_h))

        # Rects de compatibilidad
        self.content_rect = self._transcript_rect
        input_pad = 10
        self.input_rect = rl.Rectangle(
            float(x + input_pad),
            float(bottom + 10),
            float(max(0, width - input_pad * 2)),
            float(composer_h - 20),
        )

    def _reset_scroll(self) -> None:
        self._scroll_offset = 0.0
        self._auto_scroll = True

    # ========================================
    # Header
    # ========================================
    def _draw_header_bar(self) -> None:
        rl.draw_rectangle_rec(self._header_rect, self.UNITY_HEADER)
        rl.draw_line(
            int(self._header_rect.x),
            int(self._header_rect.y + self._header_rect.height - 1),
            int(self._header_rect.x + self._header_rect.width),
            int(self._header_rect.y + self._header_rect.height - 1),
            self.UNITY_BORDER,
        )
        y_mid = int(self._header_rect.y + (self._header_rect.height - 22) / 2)
        x = int(self._header_rect.x + 10)
        right_x = int(self._header_rect.x + self._header_rect.width - 8)

        # Titulo
        rl.draw_text("Agent", x, int(self._header_rect.y + 6), 10, self.UNITY_TEXT_BRIGHT)
        rl.draw_text(
            "integrated editor",
            x,
            int(self._header_rect.y + 20),
            9,
            self.UNITY_TEXT_DIM,
        )
        x += 110

        provider_id, model, stream = self._current_session_config()
        status = self._safe_provider_status(provider_id)

        # Provider chip
        provider_label = f"@{provider_id}"
        provider_w = 160
        self._provider_chip_rect = self._draw_chip(
            x,
            y_mid,
            provider_w,
            provider_label,
            status_color=self._status_color(status),
            is_open=self._provider_dropdown_open,
        )
        if self._is_chip_clicked(self._provider_chip_rect):
            self._provider_dropdown_open = not self._provider_dropdown_open
            self._model_dropdown_open = False
        x += provider_w + 6

        # Model chip
        model_label = f"# {model or 'auto'}"
        model_w = 220
        self._model_chip_rect = self._draw_chip(
            x,
            y_mid,
            model_w,
            model_label,
            status_color=None,
            is_open=self._model_dropdown_open,
        )
        if self._is_chip_clicked(self._model_chip_rect):
            self._model_dropdown_open = not self._model_dropdown_open
            self._provider_dropdown_open = False
        x += model_w + 6

        # Botones derechos (orden inverso: Stop, Clear, Status, New)
        btns = [
            ("Stop", self._action_stop, self.UNITY_BUTTON),
            ("Clear", self._action_clear, self.UNITY_BUTTON),
            ("Status", self._action_status, self.UNITY_BUTTON),
            ("New", self._new_session, self.UNITY_BUTTON),
        ]
        btn_h = 22
        for label, handler, base_bg in btns:
            btn_w = rl.measure_text(label, 10) + 18
            if right_x - btn_w < x + 4:
                break
            rect = rl.Rectangle(float(right_x - btn_w), float(y_mid), float(btn_w), float(btn_h))
            if self._draw_flat_button(rect, label, base_bg):
                handler()
            right_x -= int(btn_w + 4)

        # Permisos
        perm_label = (
            "Full access"
            if self.permission_mode == AgentPermissionMode.FULL_ACCESS
            else "Confirm actions"
        )
        perm_color = (
            self.UNITY_WARN
            if self.permission_mode == AgentPermissionMode.FULL_ACCESS
            else self.UNITY_BLUE
        )
        perm_w = rl.measure_text(perm_label, 10) + 22
        if right_x - perm_w > x + 4:
            perm_rect = rl.Rectangle(float(right_x - perm_w), float(y_mid), float(perm_w), float(btn_h))
            if self._draw_flat_button(perm_rect, perm_label, perm_color):
                self._toggle_permission_mode()
            right_x -= int(perm_w + 4)

        # Streaming (si soportado)
        if status.get("supports_streaming"):
            stream_label = "Stream on" if stream else "Stream off"
            stream_color = self.UNITY_OK if stream else self.UNITY_BUTTON
            stream_w = rl.measure_text(stream_label, 10) + 22
            if right_x - stream_w > x + 4:
                stream_rect = rl.Rectangle(
                    float(right_x - stream_w), float(y_mid), float(stream_w), float(btn_h)
                )
                if self._draw_flat_button(stream_rect, stream_label, stream_color):
                    self._apply_streaming_toggle()
                right_x -= int(stream_w + 4)

    def _draw_chip(
        self,
        x: int,
        y: int,
        width: int,
        label: str,
        *,
        status_color: rl.Color | None,
        is_open: bool,
        height: int = 22,
    ) -> rl.Rectangle:
        rect = rl.Rectangle(float(x), float(y), float(width), float(height))
        hover = rl.check_collision_point_rec(rl.get_mouse_position(), rect)
        bg = self.UNITY_BLUE if is_open else (self.UNITY_BUTTON_HOVER if hover else self.UNITY_BUTTON)
        rl.draw_rectangle_rec(rect, bg)
        rl.draw_rectangle_lines_ex(rect, 1, self.UNITY_BORDER)
        text_x = int(x + 10)
        if status_color is not None:
            rl.draw_circle(int(x + 10), int(y + height / 2), 4, status_color)
            text_x = int(x + 20)
        max_text_w = int(width - (text_x - x) - 22)
        clipped = self._clip_text(label, max_text_w)
        rl.draw_text(clipped, text_x, int(y + (height - 10) / 2), 10, self.UNITY_TEXT_BRIGHT)
        # Caret abajo
        caret_x = int(x + width - 12)
        caret_y = int(y + height / 2)
        rl.draw_triangle(
            rl.Vector2(float(caret_x - 4), float(caret_y - 2)),
            rl.Vector2(float(caret_x + 4), float(caret_y - 2)),
            rl.Vector2(float(caret_x), float(caret_y + 3)),
            self.UNITY_TEXT_DIM,
        )
        return rect

    def _is_chip_clicked(self, rect: rl.Rectangle) -> bool:
        if not rl.is_mouse_button_pressed(rl.MOUSE_BUTTON_LEFT):
            return False
        return rl.check_collision_point_rec(rl.get_mouse_position(), rect)

    def _draw_flat_button(self, rect: rl.Rectangle, label: str, base_bg: rl.Color) -> bool:
        hover = rl.check_collision_point_rec(rl.get_mouse_position(), rect)
        bg = self.UNITY_BUTTON_HOVER if hover else base_bg
        rl.draw_rectangle_rec(rect, bg)
        rl.draw_rectangle_lines_ex(rect, 1, self.UNITY_BORDER)
        text_w = rl.measure_text(label, 10)
        rl.draw_text(
            label,
            int(rect.x + (rect.width - text_w) / 2),
            int(rect.y + (rect.height - 10) / 2),
            10,
            self.UNITY_TEXT_BRIGHT,
        )
        return hover and rl.is_mouse_button_pressed(rl.MOUSE_BUTTON_LEFT)

    # ========================================
    # Barra de contexto (proyecto + live + auth)
    # ========================================
    def _draw_context_bar(self) -> None:
        rl.draw_rectangle_rec(self._context_rect, self.UNITY_BG_MID)
        rl.draw_line(
            int(self._context_rect.x),
            int(self._context_rect.y + self._context_rect.height - 1),
            int(self._context_rect.x + self._context_rect.width),
            int(self._context_rect.y + self._context_rect.height - 1),
            self.UNITY_BORDER,
        )
        y = int(self._context_rect.y + 4)
        x = int(self._context_rect.x + 10)

        if self.project_service is not None and self.project_service.has_project:
            project_label = f"Proyecto: {self.project_service.project_name}"
            rl.draw_text(project_label, x, y, 10, self.UNITY_TEXT)
            x += rl.measure_text(project_label, 10) + 14
            live_label = "live engine" if self.live_port_connected else "file tools only"
            live_color = self.UNITY_OK if self.live_port_connected else self.UNITY_TEXT_DIM
            rl.draw_circle(x + 3, y + 5, 3, live_color)
            rl.draw_text(live_label, x + 12, y, 10, self.UNITY_TEXT_DIM)
            x += rl.measure_text(live_label, 10) + 22
        else:
            rl.draw_text("Sin proyecto activo", x, y, 10, self.UNITY_TEXT_DIM)
            x += rl.measure_text("Sin proyecto activo", 10) + 14

        provider_id, _model, _stream = self._current_session_config()
        status = self._safe_provider_status(provider_id)
        auth_status = str(status.get("auth_status", ""))
        login_supported = bool(status.get("login_supported", False))
        if auth_status == "configured":
            rl.draw_circle(x + 3, y + 5, 3, self.UNITY_OK)
            rl.draw_text("auth configurada", x + 12, y, 10, self.UNITY_TEXT_DIM)
        elif login_supported:
            rl.draw_circle(x + 3, y + 5, 3, self.UNITY_AMBER)
            rl.draw_text("auth missing", x + 12, y, 10, self.UNITY_AMBER)
            x_btn = x + 12 + rl.measure_text("auth missing", 10) + 8
            login_rect = rl.Rectangle(float(x_btn), float(y - 2), 56.0, 16.0)
            if self._draw_flat_button(login_rect, "Login", self.UNITY_BLUE):
                self._send_text(f"/login {provider_id}")
        else:
            rl.draw_circle(x + 3, y + 5, 3, self.UNITY_TEXT_DIM)
            rl.draw_text("offline/test", x + 12, y, 10, self.UNITY_TEXT_DIM)

        # Status message a la derecha
        status_msg = self.status_text or ""
        clipped_status = self._clip_text(
            status_msg, int(self._context_rect.width / 2 - 10)
        )
        status_w = rl.measure_text(clipped_status, 10)
        rl.draw_text(
            clipped_status,
            int(self._context_rect.x + self._context_rect.width - status_w - 10),
            y,
            10,
            self.UNITY_TEXT_DIM,
        )

    # ========================================
    # Transcript
    # ========================================
    def _draw_transcript(self) -> None:
        rl.draw_rectangle_rec(self._transcript_rect, self.UNITY_BG)
        if self.agent_service is None or not self.session_id:
            rl.draw_text(
                "Abre un proyecto para iniciar la sesion del agente.",
                int(self._transcript_rect.x + 12),
                int(self._transcript_rect.y + 12),
                10,
                self.UNITY_TEXT_DIM,
            )
            return
        try:
            session = self.agent_service.get_session(self.session_id)
        except Exception as exc:
            rl.draw_text(
                f"Agent unavailable: {exc}",
                int(self._transcript_rect.x + 12),
                int(self._transcript_rect.y + 12),
                10,
                self.UNITY_WARN,
            )
            return

        events = session.get("events", []) or []
        if len(events) != self._last_event_count:
            self._last_event_count = len(events)
            # Auto-scroll al fondo si el usuario no ha movido scroll
            if self._auto_scroll:
                self._scroll_offset = 0.0

        messages = list(session.get("messages", []) or [])
        cards = self._prepare_message_cards(messages)

        width_inner = int(self._transcript_rect.width - 16)
        total_height = 0
        card_layouts: list[tuple[int, dict, int]] = []
        for card in cards:
            card_height = self._measure_card_height(card, width_inner)
            card_layouts.append((total_height, card, card_height))
            total_height += card_height + 6

        visible_h = int(self._transcript_rect.height)
        max_scroll = max(0.0, float(total_height) - float(visible_h))
        self._scroll_offset = min(max(0.0, self._scroll_offset), max_scroll)

        # Pintamos desde el fondo hacia arriba: lo mas reciente queda abajo.
        base_y = int(self._transcript_rect.y + self._transcript_rect.height - 6)
        y_cursor = base_y + int(self._scroll_offset)
        for top_offset, card, card_height in reversed(card_layouts):
            y_top = y_cursor - card_height
            if y_top > self._transcript_rect.y + self._transcript_rect.height:
                y_cursor -= card_height + 6
                continue
            if y_cursor < self._transcript_rect.y:
                break
            self._draw_message_card(card, y_top, width_inner)
            y_cursor -= card_height + 6

        # Streaming indicator
        if events:
            last_kind = str(events[-1].get("kind", ""))
            if last_kind in {"assistant_delta", "provider_stream_started"}:
                rl.draw_text(
                    "streaming...",
                    int(self._transcript_rect.x + 12),
                    int(self._transcript_rect.y + 6),
                    10,
                    self.UNITY_OK,
                )

        # Scrollbar simple
        if total_height > visible_h and visible_h > 0:
            ratio = visible_h / float(total_height)
            bar_h = max(20.0, visible_h * ratio)
            scrolled = 0.0 if max_scroll <= 0 else self._scroll_offset / max_scroll
            bar_y = self._transcript_rect.y + (visible_h - bar_h) * (1.0 - scrolled)
            bar_x = self._transcript_rect.x + self._transcript_rect.width - 4
            rl.draw_rectangle(int(bar_x), int(bar_y), 3, int(bar_h), self.UNITY_BUTTON)

    def _prepare_message_cards(self, messages: list[dict]) -> list[dict]:
        cards: list[dict] = []
        for message in messages:
            role = str(message.get("role", "")) or "assistant"
            content = str(message.get("content", "") or "")
            tool_result = message.get("tool_result")
            cards.append(
                {
                    "role": role,
                    "content": content,
                    "tool_result": tool_result if isinstance(tool_result, dict) else None,
                }
            )
        return cards

    def _measure_card_height(self, card: dict, width: int) -> int:
        inner_width = max(80, width - 28)
        content = self._card_effective_content(card)
        lines = self._wrap_text(content, inner_width, 10)
        base = 22
        content_h = max(1, len(lines)) * self.LINE_HEIGHT
        return base + content_h + 6

    def _card_effective_content(self, card: dict) -> str:
        role = card.get("role", "assistant")
        content = str(card.get("content", "") or "").strip()
        tool_result = card.get("tool_result")
        if role == "tool" and tool_result is not None and not content:
            if tool_result.get("success", True):
                content = str(tool_result.get("output", "") or "(sin salida)")
            else:
                content = str(tool_result.get("error", "") or "(error sin detalle)")
        return content

    def _draw_message_card(self, card: dict, y: int, width: int) -> None:
        role = card.get("role", "assistant")
        bg, bar, label = self._card_colors(role)
        x = int(self._transcript_rect.x + 8)
        card_w = int(width)
        card_h = self._measure_card_height(card, width) - 4
        if card_h <= 0:
            return

        card_rect = rl.Rectangle(float(x), float(y), float(card_w), float(card_h))
        rl.draw_rectangle_rec(card_rect, bg)
        rl.draw_rectangle_lines_ex(card_rect, 1, self.UNITY_BORDER_DIM)
        rl.draw_rectangle(int(x), int(y), 3, int(card_h), bar)

        tool_result = card.get("tool_result")
        role_label = label
        if role == "tool" and tool_result is not None:
            tool_name = str(tool_result.get("tool_name", "tool"))
            success = bool(tool_result.get("success", True))
            role_label = f"{label} {tool_name} - {'ok' if success else 'error'}"
            err_bar = self.CARD_TOOL_BAR if success else self.CARD_TOOL_ERR_BAR
            rl.draw_rectangle(int(x), int(y), 3, int(card_h), err_bar)
        rl.draw_text(role_label, int(x + 10), int(y + 5), 10, self.UNITY_TEXT_BRIGHT)

        content = self._card_effective_content(card)
        inner_width = max(80, width - 28)
        lines = self._wrap_text(content, inner_width, 10)
        content_y = y + 22
        for line in lines:
            rl.draw_text(line, int(x + 10), int(content_y), 10, self.UNITY_TEXT)
            content_y += self.LINE_HEIGHT

    def _card_colors(self, role: str) -> tuple[rl.Color, rl.Color, str]:
        if role == "user":
            return self.CARD_USER, self.CARD_USER_BAR, "Tu"
        if role == "assistant":
            return self.CARD_ASSISTANT, self.CARD_ASSISTANT_BAR, "Assistant"
        if role == "tool":
            return self.CARD_TOOL, self.CARD_TOOL_BAR, "Tool"
        return self.CARD_SYSTEM, self.CARD_SYSTEM_BAR, "System"

    # ========================================
    # Aprobaciones pendientes
    # ========================================
    def _measure_pending_height(self, width: int) -> int:
        if self.agent_service is None or not self.session_id:
            return 0
        try:
            session = self.agent_service.get_session(self.session_id)
        except Exception:
            return 0
        pending = [
            action
            for action in session.get("pending_actions", [])
            if action.get("status") == AgentActionStatus.PENDING.value
        ]
        if not pending:
            return 0
        max_cards = min(3, len(pending))
        inner_width = max(80, int(width) - 28)
        height = 8
        for action in pending[:max_cards]:
            reason = str(action.get("reason", ""))
            reason_lines = self._wrap_text(reason, inner_width - 8, 10) if reason else []
            card_h = 36 + max(0, len(reason_lines) - 1) * self.LINE_HEIGHT
            action_id = str(action.get("action_id", ""))
            if action_id in self._expanded_action_ids:
                preview_lines = str(action.get("preview", "")).splitlines()[:6]
                card_h += 4 + len(preview_lines) * self.LINE_HEIGHT
            height += card_h + 4
        if len(pending) > max_cards:
            height += 14
        return height

    def _draw_pending_approvals(self) -> None:
        if self._approvals_rect.height <= 0 or self.agent_service is None or not self.session_id:
            return
        try:
            session = self.agent_service.get_session(self.session_id)
        except Exception:
            return
        pending = [
            action
            for action in session.get("pending_actions", [])
            if action.get("status") == AgentActionStatus.PENDING.value
        ]
        if not pending:
            return

        rl.draw_rectangle_rec(self._approvals_rect, self.UNITY_BG_MID)
        rl.draw_line(
            int(self._approvals_rect.x),
            int(self._approvals_rect.y),
            int(self._approvals_rect.x + self._approvals_rect.width),
            int(self._approvals_rect.y),
            self.UNITY_BORDER,
        )
        x = int(self._approvals_rect.x + 8)
        y = int(self._approvals_rect.y + 6)
        card_w = int(self._approvals_rect.width - 16)
        inner_width = max(80, card_w - 24)
        max_cards = min(3, len(pending))

        for action in pending[:max_cards]:
            action_id = str(action.get("action_id", ""))
            tool = str(action.get("tool_call", {}).get("tool_name", "tool"))
            reason = str(action.get("reason", ""))
            expanded = action_id in self._expanded_action_ids
            reason_lines = self._wrap_text(reason, inner_width, 10) if reason else []
            preview_lines: list[str] = []
            if expanded:
                preview_lines = str(action.get("preview", "")).splitlines()[:6]
            card_h = 36 + max(0, len(reason_lines) - 1) * self.LINE_HEIGHT
            if expanded:
                card_h += 4 + len(preview_lines) * self.LINE_HEIGHT

            card_rect = rl.Rectangle(float(x), float(y), float(card_w), float(card_h))
            rl.draw_rectangle_rec(card_rect, self.CARD_PENDING)
            rl.draw_rectangle_lines_ex(card_rect, 1, self.UNITY_BORDER_DIM)
            rl.draw_rectangle(int(x), int(y), 3, int(card_h), self.CARD_PENDING_BAR)

            rl.draw_text("PENDING", int(x + 10), int(y + 6), 10, self.CARD_PENDING_BAR)
            rl.draw_text(tool, int(x + 72), int(y + 6), 10, self.UNITY_TEXT_BRIGHT)

            btn_y = y + 4
            right = int(x + card_w - 8)
            approve_w, reject_w, preview_w = 72, 66, 78
            approve_rect = rl.Rectangle(float(right - approve_w), float(btn_y), float(approve_w), 20.0)
            reject_rect = rl.Rectangle(
                float(right - approve_w - reject_w - 4), float(btn_y), float(reject_w), 20.0
            )
            preview_rect = rl.Rectangle(
                float(right - approve_w - reject_w - preview_w - 8),
                float(btn_y),
                float(preview_w),
                20.0,
            )

            if self._draw_flat_button(approve_rect, "Approve", self.UNITY_BLUE):
                try:
                    self.agent_service.approve_action(self.session_id, action_id, True)
                    self._expanded_action_ids.discard(action_id)
                except Exception as exc:
                    self.status_text = f"Approve error: {exc}"
            if self._draw_flat_button(reject_rect, "Reject", self.UNITY_BUTTON):
                try:
                    self.agent_service.approve_action(self.session_id, action_id, False)
                    self._expanded_action_ids.discard(action_id)
                except Exception as exc:
                    self.status_text = f"Reject error: {exc}"
            preview_label = "Hide diff" if expanded else "View diff"
            if self._draw_flat_button(preview_rect, preview_label, self.UNITY_BUTTON):
                if expanded:
                    self._expanded_action_ids.discard(action_id)
                else:
                    self._expanded_action_ids.add(action_id)

            reason_y = y + 20
            for line in reason_lines:
                rl.draw_text(line, int(x + 10), int(reason_y), 10, self.UNITY_TEXT_DIM)
                reason_y += self.LINE_HEIGHT

            if expanded and preview_lines:
                pv_y = reason_y + 2
                for preview_line in preview_lines:
                    rl.draw_text(preview_line[:200], int(x + 18), int(pv_y), 10, self.UNITY_TEXT)
                    pv_y += self.LINE_HEIGHT

            y += card_h + 4

        if len(pending) > max_cards:
            rl.draw_text(
                f"+{len(pending) - max_cards} aprobaciones pendientes mas",
                int(x + 10),
                int(y),
                10,
                self.UNITY_TEXT_DIM,
            )

    # ========================================
    # Composer
    # ========================================
    def _draw_composer(self) -> None:
        rl.draw_rectangle_rec(self._composer_rect, self.UNITY_BG_DEEP)
        rl.draw_line(
            int(self._composer_rect.x),
            int(self._composer_rect.y),
            int(self._composer_rect.x + self._composer_rect.width),
            int(self._composer_rect.y),
            self.UNITY_BORDER,
        )
        pad = 10
        field_rect = rl.Rectangle(
            float(self._composer_rect.x + pad),
            float(self._composer_rect.y + 8),
            float(self._composer_rect.width - pad * 2),
            float(self._composer_rect.height - 16),
        )
        self.input_rect = field_rect
        bg = self.UNITY_BG_MID
        border = self.UNITY_BLUE if self.has_focus else self.UNITY_BORDER_DIM
        rl.draw_rectangle_rec(field_rect, bg)
        rl.draw_rectangle_lines_ex(field_rect, 1, border)

        text_x = int(field_rect.x + 10)
        text_y = int(field_rect.y + 8)
        if self.pending_login_provider:
            if self.login_input_text:
                display = "*" * min(len(self.login_input_text), 200)
                color = self.UNITY_TEXT
            else:
                display = f"Pega la API key de {self.pending_login_provider} y pulsa Enter..."
                color = self.UNITY_TEXT_DIM
            rl.draw_text(
                self._clip_text(display, int(field_rect.width - 24)),
                text_x,
                text_y,
                10,
                color,
            )
            return

        if self.input_text:
            self._draw_multiline(
                self.input_text, text_x, text_y, int(field_rect.width - 24), self.UNITY_TEXT
            )
        else:
            placeholder = "Escribe al agente... (Enter enviar, Shift+Enter salto de linea)"
            rl.draw_text(
                self._clip_text(placeholder, int(field_rect.width - 24)),
                text_x,
                text_y,
                10,
                self.UNITY_TEXT_DIM,
            )
        hint = "/help"
        hint_w = rl.measure_text(hint, 9)
        rl.draw_text(
            hint,
            int(field_rect.x + field_rect.width - hint_w - 10),
            int(field_rect.y + field_rect.height - 14),
            9,
            self.UNITY_TEXT_DIM,
        )

    def _draw_multiline(
        self, text: str, x: int, y: int, max_width: int, color: rl.Color
    ) -> None:
        line_y = y
        lines = text.split("\n")
        visible = lines[-3:]
        for line in visible:
            rl.draw_text(self._clip_text(line, max_width), x, line_y, 10, color)
            line_y += self.LINE_HEIGHT

    # ========================================
    # Overlays de dropdown
    # ========================================
    def _draw_overlay_dropdowns(self) -> None:
        mouse = rl.get_mouse_position()
        clicked = rl.is_mouse_button_pressed(rl.MOUSE_BUTTON_LEFT)
        if self._provider_dropdown_open:
            self._draw_provider_dropdown(mouse, clicked)
        if self._model_dropdown_open:
            self._draw_model_dropdown(mouse, clicked)

    def _draw_provider_dropdown(self, mouse: Any, clicked: bool) -> None:
        if self.agent_service is None:
            self._provider_dropdown_open = False
            return
        try:
            providers = self.agent_service.list_providers()
        except Exception:
            providers = []
        if not providers:
            self._provider_dropdown_open = False
            return
        anchor = self._provider_chip_rect
        item_h = 26
        width = max(280.0, anchor.width + 120.0)
        height = len(providers) * item_h + 8
        x = float(anchor.x)
        y = float(anchor.y + anchor.height + 2)
        if x + width > self._panel_rect.x + self._panel_rect.width:
            x = self._panel_rect.x + self._panel_rect.width - width - 4
        rect = rl.Rectangle(x, y, width, float(height))
        if (
            clicked
            and not rl.check_collision_point_rec(mouse, rect)
            and not rl.check_collision_point_rec(mouse, anchor)
        ):
            self._provider_dropdown_open = False
            return
        rl.draw_rectangle_rec(rect, self.UNITY_BG_MID)
        rl.draw_rectangle_lines_ex(rect, 1, self.UNITY_BORDER)
        cy = y + 4
        current_provider, _model, _stream = self._current_session_config()
        for provider in providers:
            provider_id = str(provider.get("provider_id", ""))
            provider_kind = str(provider.get("provider_kind", "unknown"))
            auth = str(provider.get("auth_status", ""))
            is_current = provider_id == current_provider
            item_rect = rl.Rectangle(x + 2, cy, width - 4, float(item_h - 2))
            hover = rl.check_collision_point_rec(mouse, item_rect)
            if is_current:
                rl.draw_rectangle_rec(item_rect, self.UNITY_BLUE)
            elif hover:
                rl.draw_rectangle_rec(item_rect, self.UNITY_BUTTON_HOVER)
            rl.draw_circle(int(x + 14), int(cy + item_h / 2 - 1), 4, self._status_color(provider))
            rl.draw_text(provider_id, int(x + 26), int(cy + 4), 10, self.UNITY_TEXT_BRIGHT)
            meta = provider_kind
            if provider.get("test_only"):
                meta += " - test/offline"
            elif auth:
                meta += f" - auth {auth}"
            meta_w = rl.measure_text(meta, 9)
            rl.draw_text(
                meta,
                int(x + width - meta_w - 10),
                int(cy + 6),
                9,
                self.UNITY_TEXT_DIM,
            )
            if hover and clicked:
                self._provider_dropdown_open = False
                if not is_current:
                    self._apply_provider_change(provider_id)
                return
            cy += item_h

    def _draw_model_dropdown(self, mouse: Any, clicked: bool) -> None:
        if self.agent_service is None:
            self._model_dropdown_open = False
            return
        provider_id, current_model, _stream = self._current_session_config()
        presets = list_model_presets(provider_id)
        options = list(dict.fromkeys(presets))
        if current_model and current_model not in options:
            options.insert(0, current_model)
        anchor = self._model_chip_rect
        item_h = 24
        width = max(280.0, anchor.width + 80.0)
        editor_h = 34 if self._model_custom_editing else 0
        # options + "Custom..." + opcional editor
        total_items = len(options) + 1
        height = total_items * item_h + 10 + editor_h
        x = float(anchor.x)
        y = float(anchor.y + anchor.height + 2)
        if x + width > self._panel_rect.x + self._panel_rect.width:
            x = self._panel_rect.x + self._panel_rect.width - width - 4
        rect = rl.Rectangle(x, y, width, float(height))
        inside = rl.check_collision_point_rec(mouse, rect) or rl.check_collision_point_rec(
            mouse, anchor
        )
        # Si hay editor activo, tambien consideramos clicks dentro de su rect.
        if self._model_custom_editing:
            inside = inside or rl.check_collision_point_rec(mouse, self._model_custom_rect)
        if clicked and not inside:
            self._model_dropdown_open = False
            self._model_custom_editing = False
            self._model_custom_has_focus = False
            return

        rl.draw_rectangle_rec(rect, self.UNITY_BG_MID)
        rl.draw_rectangle_lines_ex(rect, 1, self.UNITY_BORDER)
        cy = y + 4
        if not options:
            rl.draw_text(
                "Sin presets - usa Custom...",
                int(x + 10),
                int(cy + 4),
                10,
                self.UNITY_TEXT_DIM,
            )
            cy += item_h
        else:
            for option in options:
                item_rect = rl.Rectangle(x + 2, cy, width - 4, float(item_h - 2))
                hover = rl.check_collision_point_rec(mouse, item_rect)
                is_current = option == current_model
                if is_current:
                    rl.draw_rectangle_rec(item_rect, self.UNITY_BLUE)
                elif hover:
                    rl.draw_rectangle_rec(item_rect, self.UNITY_BUTTON_HOVER)
                rl.draw_text(
                    option,
                    int(x + 14),
                    int(cy + 4),
                    10,
                    self.UNITY_TEXT_BRIGHT,
                )
                if hover and clicked:
                    self._model_dropdown_open = False
                    if not is_current:
                        self._apply_model_change(option)
                    return
                cy += item_h

        # Custom...
        custom_rect = rl.Rectangle(x + 2, cy, width - 4, float(item_h - 2))
        hover = rl.check_collision_point_rec(mouse, custom_rect)
        if hover:
            rl.draw_rectangle_rec(custom_rect, self.UNITY_BUTTON_HOVER)
        rl.draw_text("Custom...", int(x + 14), int(cy + 4), 10, self.UNITY_TEXT)
        if hover and clicked and not self._model_custom_editing:
            self._model_custom_editing = True
            self._model_custom_has_focus = True
            self._model_custom_buffer = current_model or ""
        cy += item_h

        if self._model_custom_editing:
            field_rect = rl.Rectangle(x + 8, cy + 4, width - 80, 24.0)
            self._model_custom_rect = field_rect
            border = (
                self.UNITY_BLUE if self._model_custom_has_focus else self.UNITY_BORDER_DIM
            )
            rl.draw_rectangle_rec(field_rect, self.UNITY_BG_DEEP)
            rl.draw_rectangle_lines_ex(field_rect, 1, border)
            display = (
                self._model_custom_buffer
                or "gpt-5, opencode-go/claude-sonnet-4.5, ..."
            )
            color = self.UNITY_TEXT if self._model_custom_buffer else self.UNITY_TEXT_DIM
            rl.draw_text(
                self._clip_text(display, int(field_rect.width - 10)),
                int(field_rect.x + 6),
                int(field_rect.y + 7),
                10,
                color,
            )
            if clicked and rl.check_collision_point_rec(mouse, field_rect):
                self._model_custom_has_focus = True
            ok_rect = rl.Rectangle(x + width - 66, cy + 4, 60.0, 24.0)
            if self._draw_flat_button(ok_rect, "Set", self.UNITY_BLUE):
                self._apply_custom_model()

    # ========================================
    # Quick actions
    # ========================================
    def _action_stop(self) -> None:
        if self.agent_service is not None and self.session_id:
            try:
                self.agent_service.cancel_session(self.session_id)
                self.status_text = "Agent stopped"
            except Exception as exc:
                self.status_text = f"Stop error: {exc}"

    def _action_clear(self) -> None:
        self._expanded_action_ids.clear()
        self._send_text("/clear")

    def _action_status(self) -> None:
        self._send_text("/status")

    def _toggle_permission_mode(self) -> None:
        self.permission_mode = (
            AgentPermissionMode.FULL_ACCESS
            if self.permission_mode == AgentPermissionMode.CONFIRM_ACTIONS
            else AgentPermissionMode.CONFIRM_ACTIONS
        )
        self._send_text(f"/permissions {self.permission_mode.value}")

    # ========================================
    # Envio / login / rebind (logica conservada)
    # ========================================
    def _send_current_input(self) -> None:
        if self.pending_login_provider:
            self._complete_login()
            return
        text = self.input_text.strip()
        if not text:
            return
        self.input_text = ""
        self._send_text(text)

    def _send_text(self, text: str) -> None:
        if self.agent_service is None or not self.session_id:
            self.status_text = "No active project"
            return
        try:
            self._maybe_rebind_authenticated_provider()
            result = self.agent_service.send_message(self.session_id, text)
            command_result = (
                dict(result.get("command_result", {})) if isinstance(result, dict) else {}
            )
            if command_result.get("action") == "open_login":
                self.pending_login_provider = str(
                    command_result.get("provider_id", "opencode-go")
                )
                self.login_input_text = ""
                self.status_text = str(command_result.get("message", "Enter API key."))
            elif command_result.get("action") == "launch_codex_login":
                self.pending_login_provider = ""
                self.login_input_text = ""
                self._launch_codex_login(command_result)
                self.status_text = str(command_result.get("message", "Codex login started."))
            elif command_result:
                self.status_text = str(command_result.get("message", "Agent command processed"))
            else:
                self.status_text = "Agent ready"
            self._auto_scroll = True
        except Exception as exc:
            self.status_text = f"Agent error: {exc}"

    def _maybe_rebind_authenticated_provider(self) -> None:
        if self.agent_service is None or not self.session_id:
            return
        try:
            session = self.agent_service.get_session(self.session_id)
            current_provider = str(session.get("provider_id", "fake") or "fake")
            status = self.agent_service.get_provider_status()
            default_provider_id = str(status.get("default_provider_id", "fake") or "fake")
            if default_provider_id == current_provider:
                return
            selected = self.agent_service.get_provider_status(default_provider_id)
            if not selected.get("runtime_ready", False):
                return
            self._binding_key = None
            self._restart_project_session()
        except Exception:
            return

    def _launch_codex_login(self, command_result: dict[str, object]) -> None:
        raw_command = command_result.get("command", [])
        if (
            not isinstance(raw_command, list)
            or not raw_command
            or not all(isinstance(item, str) for item in raw_command)
        ):
            raise RuntimeError("Invalid Codex login command payload.")
        env = os.environ.copy()
        codex_home = str(command_result.get("codex_home", "") or "").strip()
        if codex_home:
            env["CODEX_HOME"] = codex_home
        kwargs: dict[str, object] = {"env": env}
        if os.name == "nt":
            kwargs["creationflags"] = getattr(subprocess, "CREATE_NEW_CONSOLE", 0)
        subprocess.Popen(raw_command, **kwargs)

    def _complete_login(self) -> None:
        if self.agent_service is None or not self.pending_login_provider:
            return
        api_key = self.login_input_text.strip()
        provider_id = self.pending_login_provider
        self.login_input_text = ""
        self.pending_login_provider = ""
        if not api_key:
            self.status_text = "Login cancelled"
            return
        try:
            result = self.agent_service.login_provider(provider_id, api_key=api_key)
            self.status_text = str(result.get("message", "Provider configured"))
            self._binding_key = None
            self._restart_project_session()
        except Exception as exc:
            self.status_text = f"Login failed: {exc}"

    # ========================================
    # Helpers
    # ========================================
    def _safe_provider_status(self, provider_id: str) -> dict:
        if self.agent_service is None or not provider_id:
            return {}
        try:
            status = self.agent_service.get_provider_status(provider_id)
            return dict(status) if isinstance(status, dict) else {}
        except Exception:
            return {}

    def _status_color(self, status: dict) -> rl.Color:
        if not status:
            return self.UNITY_TEXT_DIM
        if bool(status.get("runtime_ready", False)):
            return self.UNITY_OK
        if (
            status.get("auth_status") == "missing"
            and bool(status.get("login_supported", False))
        ):
            return self.UNITY_AMBER
        if bool(status.get("test_only", False)) or bool(status.get("offline", False)):
            return self.UNITY_TEXT_DIM
        return self.UNITY_TEXT_DIM

    def _clip_text(self, text: str, max_width: int) -> str:
        if max_width <= 0:
            return ""
        if rl.measure_text(text, 10) <= max_width:
            return text
        ellipsis = "..."
        ellipsis_w = rl.measure_text(ellipsis, 10)
        if max_width <= ellipsis_w:
            return ellipsis[: max(0, len(ellipsis) - 1)]
        trimmed = text
        while trimmed and rl.measure_text(trimmed + ellipsis, 10) > max_width:
            trimmed = trimmed[:-1]
        return trimmed + ellipsis if trimmed else ellipsis

    def _wrap_text(self, text: str, max_width: int, font_size: int) -> list[str]:
        if not text:
            return [""]
        lines: list[str] = []
        for paragraph in text.splitlines() or [""]:
            if not paragraph:
                lines.append("")
                continue
            words = paragraph.split(" ")
            current = ""
            for word in words:
                candidate = word if not current else current + " " + word
                if rl.measure_text(candidate, font_size) <= max_width:
                    current = candidate
                    continue
                if current:
                    lines.append(current)
                # Palabra mas larga que el ancho: corte duro.
                while rl.measure_text(word, font_size) > max_width and len(word) > 1:
                    cut = len(word)
                    while cut > 1 and rl.measure_text(word[:cut], font_size) > max_width:
                        cut -= 1
                    lines.append(word[:cut])
                    word = word[cut:]
                current = word
            lines.append(current)
        if not lines:
            lines.append("")
        return lines
