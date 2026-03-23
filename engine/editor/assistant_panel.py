from __future__ import annotations

import threading
from typing import Any, Dict, List

import pyray as rl


class AssistantPanel:
    HEADER_HEIGHT = 148
    INPUT_HEIGHT = 150
    PADDING = 8
    MODEL_PICKER_HEIGHT = 176
    PROPOSAL_PREVIEW_HEIGHT = 132
    MINIMIZED_WIDTH = 44

    BG = rl.Color(36, 36, 36, 255)
    BG_MID = rl.Color(48, 48, 48, 255)
    BG_LIGHT = rl.Color(60, 60, 60, 255)
    BORDER = rl.Color(25, 25, 25, 255)
    TEXT = rl.Color(220, 220, 220, 255)
    TEXT_DIM = rl.Color(150, 150, 150, 255)
    USER = rl.Color(88, 160, 220, 255)
    ASSISTANT = rl.Color(170, 210, 120, 255)
    WARNING = rl.Color(240, 170, 90, 255)
    DANGER = rl.Color(200, 90, 90, 255)

    def __init__(self) -> None:
        self.api = None
        self.current_session_id: str = ""
        self.session_data: Dict[str, Any] = {}
        self.messages: List[Dict[str, str]] = [
            {
                "role": "assistant",
                "content": "Assistant ready. Start in Plan mode, review proposals, then apply with confirmation.",
                "kind": "text",
            }
        ]
        self.input_text: str = ""
        self.model_name: str = ""
        self.input_focused: bool = False
        self.scroll_offset: float = 0.0
        self.allow_python: bool = False
        self.provider_label: str = "No provider"
        self.provider_models_text: str = ""
        self.available_models: List[str] = []
        self.models_error: str = ""
        self.connection_hint: str = ""
        self.show_model_picker: bool = False
        self.interaction_mode: str = "plan"
        self.status_line: str = "Idle"
        self.provider_target: str = "ollama_local"
        self.is_minimized: bool = False
        self._worker_thread: threading.Thread | None = None
        self._worker_lock = threading.Lock()
        self._worker_pending: Dict[str, Any] | None = None
        self._worker_result: Dict[str, Any] | None = None
        self._busy_label: str = ""
        self._fit_cache: Dict[tuple[str, int, int], str] = {}
        self._wrap_cache: Dict[tuple[str, int], List[str]] = {}
        self._message_layout_cache: Dict[tuple[str, str, str, int], tuple[List[str], int]] = {}

    def set_api(self, api) -> None:
        self.api = api
        self._refresh_provider_info()
        session = self.api.get_ai_session() if self.api is not None else {}
        if session:
            self._sync_session(session)
        else:
            self._create_new_session()

    def update(self, rect: rl.Rectangle) -> None:
        self._consume_worker_result()
        if self.is_minimized:
            self.input_focused = False
            return

        mouse = rl.get_mouse_position()
        input_rect = self._input_rect(rect)
        if rl.is_mouse_button_pressed(rl.MOUSE_BUTTON_LEFT):
            self.input_focused = rl.check_collision_point_rec(mouse, input_rect)

        if (rl.is_key_down(rl.KEY_LEFT_SHIFT) or rl.is_key_down(rl.KEY_RIGHT_SHIFT)) and rl.is_key_pressed(rl.KEY_TAB):
            self._toggle_interaction_mode()

        if rl.check_collision_point_rec(mouse, self._messages_rect(rect)):
            self.scroll_offset -= rl.get_mouse_wheel_move() * 28
            self.scroll_offset = max(0.0, self.scroll_offset)

        if not self.input_focused:
            return

        if (rl.is_key_down(rl.KEY_LEFT_SHIFT) or rl.is_key_down(rl.KEY_RIGHT_SHIFT)) and (
            rl.is_key_pressed(rl.KEY_ENTER) or rl.is_key_pressed(rl.KEY_KP_ENTER)
        ):
            self.input_text += "\n"
            return

        if rl.is_key_pressed(rl.KEY_ENTER) or rl.is_key_pressed(rl.KEY_KP_ENTER):
            self._submit_input()
            return

        if rl.is_key_pressed(rl.KEY_BACKSPACE) and self.input_text:
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
                self.input_text += char

    def render(self, x: int, y: int, width: int, height: int) -> None:
        rect = rl.Rectangle(float(x), float(y), float(width), float(height))
        rl.draw_rectangle_rec(rect, self.BG)
        rl.draw_line(int(rect.x), int(rect.y), int(rect.x), int(rect.y + rect.height), self.BORDER)
        if self.is_minimized:
            self._draw_minimized(rect)
            return
        self._draw_header(rect)
        if self.show_model_picker:
            self._draw_model_picker(rect)
        if self._has_proposal():
            self._draw_proposal_preview(rect)
        self._draw_messages(rect)
        self._draw_input(rect)

    def _draw_header(self, rect: rl.Rectangle) -> None:
        header = rl.Rectangle(rect.x, rect.y, rect.width, self.HEADER_HEIGHT)
        rl.draw_rectangle_rec(header, self.BG_MID)
        rl.draw_line(int(header.x), int(header.y + header.height - 1), int(header.x + header.width), int(header.y + header.height - 1), self.BORDER)

        session_title = str(self.session_data.get("title", "") or "AI Assistant")
        self._draw_text_fit(session_title, int(header.x + self.PADDING), int(header.y + 7), 18, self.TEXT, int(header.width - self.PADDING * 2))

        info_width = int(header.width - self.PADDING * 2)
        info_x = int(header.x + self.PADDING)
        info_y = int(header.y + 30)
        self._draw_text_fit(f"Provider: {self.provider_label}", info_x, info_y, 10, self.TEXT_DIM, info_width)
        status_text = f"Status: {self.status_line}"
        if self._is_busy():
            status_text = f"{status_text} | {self._busy_label or 'Working...'}"
        self._draw_text_fit(status_text, info_x, info_y + 16, 10, self.WARNING if self._is_busy() else self.TEXT_DIM, info_width)
        mode_label = "Plan" if self.interaction_mode == "plan" else "Build"
        model_label = f"Model: {self.model_name}" if self.model_name else "Model: not set"
        self._draw_text_fit(
            f"Mode: {mode_label} | {model_label}",
            info_x,
            info_y + 32,
            10,
            self.WARNING if self.interaction_mode == "plan" else self.ASSISTANT,
            info_width,
        )
        if self.connection_hint:
            self._draw_text_fit(self.connection_hint, info_x, info_y + 48, 9, self.WARNING, info_width)

        minimize_label = "Min"
        minimize_rect = rl.Rectangle(header.x + header.width - 52, header.y + 6, 44, 18)
        if self._draw_button(minimize_rect, minimize_label):
            self.toggle_minimized()

        narrow = header.width < 320
        row_1, row_2, row_3 = self._header_button_rows(header, narrow)

        self.allow_python = self._draw_toggle(row_1[0], "Python", self.allow_python)
        if self._draw_button(row_1[1], "New"):
            self._create_new_session()

        if narrow:
            if self._draw_button(row_2[0], "Model"):
                self._toggle_model_picker()
            if self._draw_button(
                row_2[1],
                "Plan" if self.interaction_mode == "build" else "Build",
                active=self.interaction_mode == "build",
            ):
                self._toggle_interaction_mode()
            if self._draw_button(row_3[1], "Undo", active=self._can_undo_last_apply()):
                self._undo_last_apply()
            return

        if self._draw_button(row_1[2], "Model"):
            self._toggle_model_picker()
        if self._draw_button(
            row_1[3],
            "Plan" if self.interaction_mode == "build" else "Build",
            active=self.interaction_mode == "build",
        ):
            self._toggle_interaction_mode()

        if self._draw_button(row_2[1], "Undo", active=self._can_undo_last_apply()):
            self._undo_last_apply()

    def _draw_minimized(self, rect: rl.Rectangle) -> None:
        header_height = min(64.0, rect.height)
        header = rl.Rectangle(rect.x, rect.y, rect.width, header_height)
        rl.draw_rectangle_rec(header, self.BG_MID)
        rl.draw_line(int(rect.x), int(rect.y + header_height - 1), int(rect.x + rect.width), int(rect.y + header_height - 1), self.BORDER)

        title = str(self.session_data.get("title", "") or "AI")
        self._draw_text_fit(title, int(header.x + self.PADDING), int(header.y + 6), 12, self.TEXT, int(header.width - 12))
        self._draw_text_fit(self.status_line, int(header.x + self.PADDING), int(header.y + 22), 9, self.TEXT_DIM, int(header.width - 12))
        if self._busy_label:
            self._draw_text_fit(self._busy_label, int(header.x + self.PADDING), int(header.y + 36), 9, self.WARNING, int(header.width - 12))

        button_width = max(28, int(header.width - self.PADDING * 2))
        button_label = ">" if header.width < 64 else "Max"
        button_rect = rl.Rectangle(header.x + self.PADDING, header.y + header_height - 26, button_width, 18)
        if self._draw_button(button_rect, button_label):
            self.toggle_minimized()

    def _draw_messages(self, rect: rl.Rectangle) -> None:
        messages_rect = self._messages_rect(rect)
        if messages_rect.width <= 0 or messages_rect.height <= 0:
            return
        rl.begin_scissor_mode(int(messages_rect.x), int(messages_rect.y), int(messages_rect.width), int(messages_rect.height))
        try:
            cursor_y = int(messages_rect.y + self.PADDING - self.scroll_offset)
            max_width = int(messages_rect.width - self.PADDING * 2)
            visible_bottom = int(messages_rect.y + messages_rect.height)
            for entry in self.messages:
                role = entry.get("role", "assistant")
                kind = entry.get("kind", "text")
                text = entry.get("content", "")
                prefix = "You" if role == "user" else ("Plan" if kind == "plan" else "AI")
                color = self.USER if role == "user" else (self.WARNING if kind == "question" else (self.TEXT_DIM if kind == "plan" else self.ASSISTANT))
                wrapped, box_height = self._get_message_layout(role, kind, text, max_width)
                if cursor_y > visible_bottom:
                    break
                if cursor_y + box_height < messages_rect.y:
                    cursor_y += box_height + 6
                    continue
                background = self.BG_LIGHT if role == "user" else (rl.Color(44, 46, 52, 255) if kind == "plan" else (self.BG_MID if kind != "question" else rl.Color(72, 58, 34, 255)))
                rl.draw_rectangle(int(messages_rect.x + self.PADDING), cursor_y, max_width, box_height, background)
                rl.draw_text(prefix, int(messages_rect.x + self.PADDING + 6), cursor_y + 4, 10, color)
                line_y = cursor_y + 18
                for line in wrapped:
                    rl.draw_text(line, int(messages_rect.x + self.PADDING + 6), line_y, 10, self.TEXT)
                    line_y += 14
                cursor_y += box_height + 6
        finally:
            rl.end_scissor_mode()

    def _draw_input(self, rect: rl.Rectangle) -> None:
        input_rect = self._input_rect(rect)
        if input_rect.width <= 0 or input_rect.height <= 0:
            return
        rl.draw_rectangle_rec(input_rect, self.BG_MID)
        border = self.WARNING if self.input_focused else self.BORDER
        rl.draw_rectangle_lines_ex(input_rect, 1, border)

        title = "Siguiente decision" if self._pending_questions() else ("Prompt" if self.interaction_mode == "build" else "Analisis")
        self._draw_text_fit(title, int(input_rect.x + 6), int(input_rect.y + 6), 10, self.TEXT_DIM, int(input_rect.width - 12))

        text_y = int(input_rect.y + 24)
        pending_questions = self._pending_questions()
        if pending_questions:
            current_question = pending_questions[0]
            self._draw_text_fit(current_question["text"], int(input_rect.x + 6), int(input_rect.y + 22), 10, self.WARNING, int(input_rect.width - 12))
            rationale = str(current_question.get("rationale", "") or "")
            if rationale:
                self._draw_text_fit(rationale, int(input_rect.x + 6), int(input_rect.y + 38), 9, self.TEXT_DIM, int(input_rect.width - 12))
            choices = [str(item) for item in current_question.get("choices", [])][:3]
            if choices:
                self._draw_quick_choices(input_rect, choices)
                text_y = int(input_rect.y + 92)
            else:
                text_y = int(input_rect.y + 58)

        preview = self.input_text or (self._input_placeholder() if not self.input_focused else "")
        for idx, line in enumerate(self._wrap_text(preview, max_chars=max(16, int(input_rect.width) // 7 - 2))[:3]):
            rl.draw_text(line, int(input_rect.x + 6), text_y + idx * 14, 10, self.TEXT if self.input_text else self.TEXT_DIM)

        diff = self._current_diff()
        if diff and self.interaction_mode == "build":
            self._draw_text_fit(f"Diff: {diff.get('summary', '')}", int(input_rect.x + 6), int(input_rect.y + input_rect.height - 54), 10, self.TEXT_DIM, int(input_rect.width - 84))
        footer_text = "Enter envia. Shift+Enter inserta salto." if self.interaction_mode == "plan" else "Build ejecuta al enviar y deja Undo disponible."
        self._draw_text_fit(footer_text, int(input_rect.x + 6), int(input_rect.y + input_rect.height - 38), 10, self.TEXT_DIM, int(input_rect.width - 84))
        button_label = "..." if self._is_busy() else ("Responder" if pending_questions else ("Analizar" if self.interaction_mode == "plan" else "Ejecutar"))
        if self._draw_button(rl.Rectangle(input_rect.x + input_rect.width - 72, input_rect.y + input_rect.height - 28, 64, 22), button_label, disabled=self._is_busy()):
            self._submit_input()

    def _draw_proposal_preview(self, rect: rl.Rectangle) -> None:
        preview_rect = self._proposal_preview_rect(rect)
        if preview_rect.width <= 0 or preview_rect.height <= 0:
            return
        rl.draw_rectangle_rec(preview_rect, self.BG_MID)
        rl.draw_rectangle_lines_ex(preview_rect, 1, self.WARNING)
        self._draw_text_fit("Proposal Preview", int(preview_rect.x + 6), int(preview_rect.y + 6), 10, self.WARNING, int(preview_rect.width - 12))

        approval = self.session_data.get("approval", {}) or {}
        diff = approval.get("diff", {}) or {}
        summary = str(approval.get("summary", "") or diff.get("summary", ""))
        line_y = int(preview_rect.y + 22)
        for line in self._wrap_text(summary, max_chars=max(20, int(preview_rect.width) // 7 - 2))[:2]:
            self._draw_text_fit(line, int(preview_rect.x + 6), line_y, 10, self.TEXT, int(preview_rect.width - 12))
            line_y += 14

        details = self._build_proposal_details(diff, approval.get("tool_calls", []) or [])
        for detail in details[:5]:
            self._draw_text_fit(detail, int(preview_rect.x + 6), line_y, 10, self.TEXT_DIM, int(preview_rect.width - 12))
            line_y += 14

    def _messages_rect(self, rect: rl.Rectangle) -> rl.Rectangle:
        extra_top = 0
        if self.show_model_picker:
            extra_top += self.MODEL_PICKER_HEIGHT
        if self._has_proposal():
            extra_top += self.PROPOSAL_PREVIEW_HEIGHT
        body_height = max(0.0, rect.height - self.HEADER_HEIGHT - extra_top - self.INPUT_HEIGHT)
        return rl.Rectangle(
            rect.x,
            rect.y + self.HEADER_HEIGHT + extra_top,
            rect.width,
            body_height,
        )

    def _input_rect(self, rect: rl.Rectangle) -> rl.Rectangle:
        width = max(0.0, rect.width - self.PADDING * 2)
        height = max(0.0, self.INPUT_HEIGHT - self.PADDING * 2)
        return rl.Rectangle(
            rect.x + self.PADDING,
            rect.y + rect.height - self.INPUT_HEIGHT + self.PADDING,
            width,
            height,
        )

    def _proposal_preview_rect(self, rect: rl.Rectangle) -> rl.Rectangle:
        top = rect.y + self.HEADER_HEIGHT + (self.MODEL_PICKER_HEIGHT if self.show_model_picker else 0)
        return rl.Rectangle(
            rect.x + self.PADDING,
            top + self.PADDING,
            max(0.0, rect.width - self.PADDING * 2),
            max(0.0, self.PROPOSAL_PREVIEW_HEIGHT - self.PADDING * 2),
        )

    def _submit_input(self) -> None:
        if self.api is None:
            self._append_local_message("assistant", "EngineAPI not connected to assistant panel.")
            return
        if self._is_busy():
            return
        text = self.input_text.strip()
        if not text:
            return
        if not self.current_session_id:
            self._create_new_session()
        self.input_text = ""
        pending_questions = self._pending_questions()
        if pending_questions:
            self._start_background_call(
                "Resolviendo...",
                self.api.answer_ai_question,
                answer=text,
                session_id=self.current_session_id,
                question_id=pending_questions[0].get("id"),
                mode=self.interaction_mode,
                allow_python=self.allow_python,
            )
            return
        self._start_background_call(
            "Pensando...",
            self.api.submit_ai_message,
            prompt=text,
            session_id=self.current_session_id,
            mode=self.interaction_mode,
            allow_python=self.allow_python,
        )

    def _apply_last_proposal(self) -> None:
        if self.api is None or not self.current_session_id or self._is_busy():
            return
        self._start_background_call(
            "Aplicando...",
            self.api.approve_ai_proposal,
            session_id=self.current_session_id,
            allow_python=self.allow_python,
        )

    def _reject_last_proposal(self) -> None:
        if self.api is None or not self.current_session_id or self._is_busy():
            return
        self._start_background_call("Cancelando...", self.api.reject_ai_proposal, session_id=self.current_session_id)

    def _undo_last_apply(self) -> None:
        if self.api is None or not self.current_session_id or self._is_busy():
            return
        self._start_background_call("Revirtiendo...", self.api.undo_ai_last_apply, session_id=self.current_session_id)

    def _create_new_session(self) -> None:
        if self.api is None:
            return
        session = self.api.start_ai_session(title="Game Authoring", mode=self.interaction_mode, activate=True)
        self._sync_session(session)

    def _sync_session(self, session: Dict[str, Any]) -> None:
        if not session:
            return
        self.session_data = dict(session)
        self.current_session_id = str(session.get("id", "") or self.current_session_id)
        self.messages = [dict(item) for item in session.get("messages", [])] or self.messages
        self.status_line = str(session.get("status", "Idle") or "Idle")
        self._invalidate_text_caches()
        self._refresh_provider_info()

    def _toggle_model_picker(self) -> None:
        if self.api is None:
            return
        self._refresh_provider_info()
        self.show_model_picker = not self.show_model_picker

    def _connect_provider(self, provider_id: str, model_name: str = "") -> None:
        if self.api is None:
            return
        mode = "local" if provider_id == "ollama_local" else "hybrid"
        endpoint = "http://127.0.0.1:11434" if provider_id == "ollama_local" else "http://127.0.0.1:8000/v1"
        self.api.update_ai_project_memory(
            {
                "provider_policy": {
                    "mode": mode,
                    "preferred_provider": provider_id,
                    "model_name": model_name.strip(),
                    "endpoint": endpoint,
                }
            }
        )
        self.provider_target = provider_id
        self._refresh_provider_info()
        self.show_model_picker = False

    def _toggle_interaction_mode(self) -> None:
        if self._is_busy():
            return
        previous_mode = self.interaction_mode
        self.interaction_mode = "build" if self.interaction_mode == "plan" else "plan"
        if self.current_session_id and self.api is not None:
            session = self.api.get_ai_session(self.current_session_id)
            if session:
                self._sync_session(session)
                if (
                    previous_mode == "plan"
                    and self.interaction_mode == "build"
                    and not self.input_text.strip()
                    and not self._has_proposal()
                    and bool((self.session_data.get("plan_response", {}) or {}).get("can_build_now", False))
                    and str(self.session_data.get("prompt", "") or "").strip()
                ):
                    self._start_background_call(
                        "Construyendo...",
                        self.api.submit_ai_message,
                        prompt=str(self.session_data.get("prompt", "") or ""),
                        session_id=self.current_session_id,
                        mode="build",
                        answers=dict(self.session_data.get("answers", {}) or {}),
                        allow_python=self.allow_python,
                    )

    def _refresh_provider_info(self) -> None:
        if self.api is None:
            self.provider_label = "No provider"
            self.provider_models_text = ""
            self.connection_hint = ""
            return
        diagnostics = self.api.get_ai_provider_diagnostics()
        policy = diagnostics.get("policy", {}) or {}
        self.model_name = str(policy.get("model_name", "") or "")
        self.provider_label = str(diagnostics.get("selected_provider", "unknown"))
        self.provider_target = self.provider_label
        models = diagnostics.get("models", []) or []
        self.available_models = [str(item) for item in models]
        self.models_error = str(diagnostics.get("models_error", "") or "")
        self.provider_models_text = ", ".join(self.available_models[:3]) if self.available_models else self.models_error
        if self.provider_target == "ollama_local" and not self.available_models:
            self.connection_hint = "Local AI offline: run `ollama serve` and load a model."
        else:
            self.connection_hint = ""
        if not self.model_name and self.available_models:
            self.model_name = self.available_models[0]

    def _draw_model_picker(self, rect: rl.Rectangle) -> None:
        picker = rl.Rectangle(
            rect.x + self.PADDING,
            rect.y + self.HEADER_HEIGHT + self.PADDING,
            rect.width - self.PADDING * 2,
            self.MODEL_PICKER_HEIGHT - self.PADDING * 2,
        )
        if picker.width <= 0 or picker.height <= 0:
            return
        rl.draw_rectangle_rec(picker, self.BG_MID)
        rl.draw_rectangle_lines_ex(picker, 1, self.WARNING)
        self._draw_text_fit("Provider / Model", int(picker.x + 6), int(picker.y + 6), 10, self.TEXT, int(picker.width - 92))

        if self._draw_button(rl.Rectangle(picker.x + picker.width - 70, picker.y + 4, 60, 20), "Refresh"):
            self._refresh_provider_info()

        provider_row = self._split_row(picker.x + 6, picker.y + 28, picker.width - 12, 2, 22)
        if self._draw_button(provider_row[0], "Use Ollama", active=self.provider_target == "ollama_local"):
            self._connect_provider("ollama_local", self.model_name)
        if self._draw_button(provider_row[1], "Use OpenAI HTTP", active=self.provider_target == "openai_compatible_http"):
            self._connect_provider("openai_compatible_http", self.model_name)

        row_y = picker.y + 58
        if not self.available_models:
            self._draw_text_fit(
                self.models_error or "No models detected for the selected provider.",
                int(picker.x + 6),
                int(row_y),
                10,
                self.WARNING,
                int(picker.width - 12),
            )
            if self._draw_button(rl.Rectangle(picker.x + 6, picker.y + picker.height - 28, 72, 22), "Close"):
                self.show_model_picker = False
            return

        for model in self.available_models[:4]:
            is_current = model == self.model_name
            label = f"{model} {'(active)' if is_current else ''}"
            if self._draw_button(rl.Rectangle(picker.x + 6, row_y, picker.width - 12, 22), label, active=is_current):
                self._connect_provider(self.provider_target, model)
            row_y += 26

    def _draw_quick_choices(self, input_rect: rl.Rectangle, choices: List[str]) -> None:
        rl.draw_text("Opciones rapidas", int(input_rect.x + 6), int(input_rect.y + 54), 10, self.TEXT_DIM)
        row_y = input_rect.y + 54
        button_width = input_rect.width - 12
        for index, choice in enumerate(choices[:3]):
            rect = rl.Rectangle(input_rect.x + 6, row_y + index * 20, button_width, 18)
            if self._draw_button(rect, self._format_choice_label(choice)):
                self.input_text = choice
                self._submit_input()

    def _draw_button(self, rect: rl.Rectangle, label: str, active: bool = False, disabled: bool = False) -> bool:
        mouse = rl.get_mouse_position()
        hover = rl.check_collision_point_rec(mouse, rect)
        color = self.TEXT_DIM if disabled else (self.WARNING if active else (self.BG_LIGHT if hover else self.BG_MID))
        rl.draw_rectangle_rec(rect, color)
        rl.draw_rectangle_lines_ex(rect, 1, self.BORDER)
        self._draw_text_fit(label, int(rect.x + 6), int(rect.y + 6), 10, self.TEXT, max(0, int(rect.width - 12)))
        return not disabled and hover and rl.is_mouse_button_pressed(rl.MOUSE_BUTTON_LEFT)

    def _draw_toggle(self, rect: rl.Rectangle, label: str, value: bool) -> bool:
        mouse = rl.get_mouse_position()
        hover = rl.check_collision_point_rec(mouse, rect)
        color = self.WARNING if value else (self.BG_LIGHT if hover else self.BG_MID)
        rl.draw_rectangle_rec(rect, color)
        rl.draw_rectangle_lines_ex(rect, 1, self.BORDER)
        self._draw_text_fit(label, int(rect.x + 6), int(rect.y + 5), 10, self.TEXT, max(0, int(rect.width - 12)))
        if hover and rl.is_mouse_button_pressed(rl.MOUSE_BUTTON_LEFT):
            return not value
        return value

    def _draw_text_fit(self, text: str, x: int, y: int, size: int, color: rl.Color, max_width: int) -> None:
        rl.draw_text(self._fit_text(text, max_width, size), x, y, size, color)

    def _fit_text(self, text: str, max_width: int, size: int) -> str:
        if not text or max_width <= 0:
            return ""
        text = str(text)
        cache_key = (text, int(max_width), int(size))
        cached = self._fit_cache.get(cache_key)
        if cached is not None:
            return cached
        if self._text_width(text, size) <= max_width:
            self._fit_cache[cache_key] = text
            return text

        low = 0
        high = len(text)
        best = "..."
        while low <= high:
            mid = (low + high) // 2
            candidate = f"{text[:mid]}..."
            if self._text_width(candidate, size) <= max_width:
                best = candidate
                low = mid + 1
            else:
                high = mid - 1
        self._fit_cache[cache_key] = best
        return best

    def _text_width(self, text: str, size: int) -> int:
        measure = getattr(rl, "measure_text", None)
        if callable(measure):
            try:
                return int(measure(text, size))
            except TypeError:
                return int(measure(text))
        return int(len(text) * max(1, size // 2))

    def _split_row(self, x: float, y: float, width: float, count: int, height: int, gap: int = 6) -> List[rl.Rectangle]:
        count = max(1, count)
        available = max(0.0, width - gap * (count - 1))
        base = available / count if count else available
        rects: List[rl.Rectangle] = []
        cursor = float(x)
        for index in range(count):
            button_width = base
            if index == count - 1:
                button_width = max(base, float(x + width - cursor))
            button_width = max(34.0, button_width)
            rects.append(rl.Rectangle(cursor, float(y), button_width, float(height)))
            cursor += button_width + gap
        return rects

    def _header_button_rows(self, header: rl.Rectangle, narrow: bool) -> List[List[rl.Rectangle]]:
        left = header.x + self.PADDING
        width = header.width - self.PADDING * 2
        if narrow:
            return [
                self._split_row(left, header.y + 70, width, 2, 22),
                self._split_row(left, header.y + 96, width, 2, 22),
                self._split_row(left, header.y + 122, width, 3, 22),
            ]
        return [
            self._split_row(left, header.y + 70, width, 4, 22),
            self._split_row(left, header.y + 96, width, 3, 22),
            [],
        ]

    def _wrap_text(self, text: str, max_chars: int) -> List[str]:
        cache_key = (str(text or ""), int(max_chars))
        cached = self._wrap_cache.get(cache_key)
        if cached is not None:
            return list(cached)
        if not text:
            self._wrap_cache[cache_key] = [""]
            return [""]
        lines: List[str] = []
        for paragraph in text.replace("\r", "").split("\n"):
            words = paragraph.split()
            if not words:
                lines.append("")
                continue
            current = words[0]
            for word in words[1:]:
                if len(current) + 1 + len(word) <= max_chars:
                    current = f"{current} {word}"
                else:
                    lines.append(current)
                    current = word
            lines.append(current)
        self._wrap_cache[cache_key] = list(lines)
        return lines

    def _format_choice_label(self, value: str) -> str:
        text = str(value or "").strip().replace("_", " ")
        if not text:
            return ""
        return text[:1].upper() + text[1:]

    def _input_placeholder(self) -> str:
        if self.interaction_mode == "plan":
            return "Describe el cambio y el asistente analizara el proyecto."
        return "Describe el cambio a ejecutar sobre el proyecto."

    def _append_local_message(self, role: str, content: str, kind: str = "text") -> None:
        self.messages.append({"role": role, "content": content, "kind": kind})
        self.scroll_offset = 0.0
        self._invalidate_text_caches()

    def _start_background_call(self, busy_label: str, fn, **kwargs: Any) -> None:
        if self._is_busy():
            return
        self._busy_label = busy_label
        self.status_line = "working"
        with self._worker_lock:
            self._worker_pending = {"fn": fn, "kwargs": dict(kwargs)}
            self._worker_result = None
        self._worker_thread = threading.Thread(target=self._run_background_call, daemon=True)
        self._worker_thread.start()

    def _run_background_call(self) -> None:
        with self._worker_lock:
            pending = dict(self._worker_pending or {})
        if not pending:
            return
        fn = pending.get("fn")
        kwargs = dict(pending.get("kwargs", {}) or {})
        try:
            result = fn(**kwargs) if callable(fn) else {}
        except Exception as exc:
            result = {"__assistant_error__": str(exc)}
        with self._worker_lock:
            self._worker_result = result
            self._worker_pending = None

    def _consume_worker_result(self) -> None:
        with self._worker_lock:
            result = self._worker_result
            if result is None:
                return
            self._worker_result = None
        self._worker_thread = None
        self._busy_label = ""
        if "__assistant_error__" in result:
            self.status_line = "blocked"
            self._append_local_message("assistant", str(result.get("__assistant_error__", "Assistant request failed.")))
            return
        self._sync_session(result)

    def _is_busy(self) -> bool:
        return self._worker_thread is not None and self._worker_thread.is_alive()

    def _drain_background_tasks_for_tests(self) -> None:
        worker = self._worker_thread
        if worker is not None:
            worker.join(timeout=2.0)
        self._consume_worker_result()

    def _pending_questions(self) -> List[Dict[str, Any]]:
        return list(self.session_data.get("pending_questions", []) or [])

    def _current_diff(self) -> Dict[str, Any]:
        approval = self.session_data.get("approval", {}) or {}
        return approval.get("diff", {}) or {}

    def _has_proposal(self) -> bool:
        approval = self.session_data.get("approval", {}) or {}
        return bool(approval and approval.get("tool_calls") and approval.get("status") in {"pending", "proposal_ready"})

    def _can_undo_last_apply(self) -> bool:
        last_apply = self.session_data.get("last_apply", {}) or {}
        return bool(last_apply.get("snapshot_id"))

    def toggle_minimized(self) -> None:
        self.is_minimized = not self.is_minimized
        if self.is_minimized:
            self.show_model_picker = False
            self.input_focused = False

    def set_minimized(self, minimized: bool) -> None:
        self.is_minimized = bool(minimized)
        if self.is_minimized:
            self.show_model_picker = False
            self.input_focused = False

    def _build_proposal_details(self, diff: Dict[str, Any], tool_calls: List[Dict[str, Any]]) -> List[str]:
        details: List[str] = []
        if tool_calls:
            details.append(f"Tools: {len(tool_calls)}")
        entities = diff.get("entities", []) or []
        files = diff.get("files", []) or []
        tools = diff.get("tools", []) or []
        risks = diff.get("risk_notes", []) or []
        if entities:
            details.append("Entities: " + ", ".join(str(item) for item in entities[:3]))
        if files:
            details.append("Files: " + ", ".join(str(item) for item in files[:2]))
        if tools:
            details.append("Calls: " + ", ".join(str(item) for item in tools[:3]))
        if risks:
            details.append("Risk: " + str(risks[0]))
        return details

    def _get_message_layout(self, role: str, kind: str, text: str, max_width: int) -> tuple[List[str], int]:
        max_chars = max(18, max_width // 7)
        cache_key = (str(role), str(kind), str(text), int(max_chars))
        cached = self._message_layout_cache.get(cache_key)
        if cached is not None:
            wrapped, box_height = cached
            return list(wrapped), int(box_height)
        wrapped = self._wrap_text(text, max_chars=max_chars)
        box_height = 18 + len(wrapped) * 14 + 8
        self._message_layout_cache[cache_key] = (list(wrapped), box_height)
        return wrapped, box_height

    def _invalidate_text_caches(self) -> None:
        self._fit_cache.clear()
        self._wrap_cache.clear()
        self._message_layout_cache.clear()
