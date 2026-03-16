from __future__ import annotations

from typing import Any, Dict, List

import pyray as rl


class AssistantPanel:
    HEADER_HEIGHT = 72
    INPUT_HEIGHT = 132
    PADDING = 8
    MODEL_PICKER_HEIGHT = 132
    PROPOSAL_PREVIEW_HEIGHT = 118

    BG = rl.Color(36, 36, 36, 255)
    BG_MID = rl.Color(48, 48, 48, 255)
    BG_LIGHT = rl.Color(60, 60, 60, 255)
    BORDER = rl.Color(25, 25, 25, 255)
    TEXT = rl.Color(220, 220, 220, 255)
    TEXT_DIM = rl.Color(150, 150, 150, 255)
    USER = rl.Color(88, 160, 220, 255)
    ASSISTANT = rl.Color(170, 210, 120, 255)
    WARNING = rl.Color(240, 170, 90, 255)

    def __init__(self) -> None:
        self.api = None
        self.messages: List[Dict[str, str]] = [
            {"role": "assistant", "text": "Assistant ready. Default mode is Normal. Press Shift+Tab to toggle Plan mode."}
        ]
        self.input_text: str = ""
        self.model_name: str = ""
        self.input_focused: bool = False
        self.scroll_offset: float = 0.0
        self.active_prompt: str = ""
        self.pending_questions: List[Dict[str, Any]] = []
        self.answers: Dict[str, Any] = {}
        self.last_response: Dict[str, Any] = {}
        self.allow_python: bool = False
        self.provider_label: str = "No provider"
        self.provider_models_text: str = ""
        self.available_models: List[str] = []
        self.models_error: str = ""
        self.show_model_picker: bool = False
        self.interaction_mode: str = "normal"

    def set_api(self, api) -> None:
        self.api = api
        self._refresh_provider_info()

    def update(self, rect: rl.Rectangle) -> None:
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
        rl.draw_text("AI Assistant", int(header.x + self.PADDING), int(header.y + 8), 18, self.TEXT)

        provider_label = self.provider_label if self.api is not None else "No provider"
        rl.draw_text(f"Provider: {provider_label}", int(header.x + self.PADDING), int(header.y + 34), 10, self.TEXT_DIM)
        rl.draw_text(
            f"Mode: {'Plan' if self.interaction_mode == 'plan' else 'Normal'}",
            int(header.x + self.PADDING),
            int(header.y + 48),
            10,
            self.WARNING if self.interaction_mode == "plan" else self.TEXT_DIM,
        )
        if self.model_name:
            rl.draw_text(f"Model: {self.model_name}", int(header.x + self.PADDING + 120), int(header.y + 34), 10, self.TEXT_DIM)

        btn_y = header.y + 38
        ollama_rect = rl.Rectangle(header.x + rect.width - 198, btn_y, 58, 24)
        mode_rect = rl.Rectangle(header.x + rect.width - 134, btn_y, 58, 24)
        apply_rect = rl.Rectangle(header.x + rect.width - 70, btn_y, 58, 24)
        if self._draw_button(ollama_rect, "Ollama"):
            self._toggle_ollama_picker()
        if self._draw_button(mode_rect, "Plan" if self.interaction_mode == "normal" else "Normal", active=self.interaction_mode == "plan"):
            self._toggle_interaction_mode()
        if self._draw_button(apply_rect, "Apply", active=self._has_proposal()):
            self._apply_last_proposal()
        python_rect = rl.Rectangle(header.x + rect.width - 262, header.y + 10, 84, 20)
        self.allow_python = self._draw_toggle(python_rect, "Python", self.allow_python)

    def _draw_messages(self, rect: rl.Rectangle) -> None:
        messages_rect = self._messages_rect(rect)
        rl.begin_scissor_mode(int(messages_rect.x), int(messages_rect.y), int(messages_rect.width), int(messages_rect.height))
        try:
            cursor_y = int(messages_rect.y + self.PADDING - self.scroll_offset)
            max_width = int(messages_rect.width - self.PADDING * 2)
            for entry in self.messages:
                role = entry.get("role", "assistant")
                text = entry.get("text", "")
                prefix = "You" if role == "user" else "AI"
                color = self.USER if role == "user" else self.ASSISTANT
                wrapped = self._wrap_text(text, max_chars=max(18, max_width // 7))
                box_height = 18 + len(wrapped) * 14 + 8
                rl.draw_rectangle(int(messages_rect.x + self.PADDING), cursor_y, max_width, box_height, self.BG_LIGHT if role == "user" else self.BG_MID)
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
        rl.draw_rectangle_rec(input_rect, self.BG_MID)
        border = self.WARNING if self.input_focused else self.BORDER
        rl.draw_rectangle_lines_ex(input_rect, 1, border)

        title = "Answer current question" if self.pending_questions else "Prompt"
        rl.draw_text(title, int(input_rect.x + 6), int(input_rect.y + 6), 10, self.TEXT_DIM)

        text_y = int(input_rect.y + 24)
        if self.pending_questions:
            rl.draw_text(self.pending_questions[0]["text"], int(input_rect.x + 6), int(input_rect.y + 22), 10, self.WARNING)
            choices = [str(item) for item in self.pending_questions[0].get("choices", [])][:3]
            if choices:
                self._draw_quick_choices(input_rect, choices)
                text_y = int(input_rect.y + 72)

        preview = self.input_text or ("Type here..." if not self.input_focused else "")
        for idx, line in enumerate(self._wrap_text(preview, max_chars=max(16, int(input_rect.width) // 7 - 2))[:3]):
            rl.draw_text(line, int(input_rect.x + 6), text_y + idx * 14, 10, self.TEXT if self.input_text else self.TEXT_DIM)

        rl.draw_text("Or write your own answer", int(input_rect.x + 6), int(input_rect.y + input_rect.height - 40), 10, self.TEXT_DIM)
        button_label = "Continue" if self.pending_questions else "Send"
        if self._draw_button(rl.Rectangle(input_rect.x + input_rect.width - 72, input_rect.y + input_rect.height - 28, 64, 22), button_label):
            self._submit_input(mode=self._send_mode())

    def _draw_proposal_preview(self, rect: rl.Rectangle) -> None:
        preview_rect = self._proposal_preview_rect(rect)
        rl.draw_rectangle_rec(preview_rect, self.BG_MID)
        rl.draw_rectangle_lines_ex(preview_rect, 1, self.WARNING)
        rl.draw_text("Proposal Preview", int(preview_rect.x + 6), int(preview_rect.y + 6), 10, self.WARNING)

        proposal = self.last_response.get("proposal", {}) or {}
        summary = str(proposal.get("summary", ""))
        lines = self._wrap_text(summary, max_chars=max(20, int(preview_rect.width) // 7 - 2))
        line_y = int(preview_rect.y + 22)
        for line in lines[:2]:
            rl.draw_text(line, int(preview_rect.x + 6), line_y, 10, self.TEXT)
            line_y += 14

        details = self._build_proposal_details(proposal)
        for detail in details[:4]:
            rl.draw_text(detail, int(preview_rect.x + 6), line_y, 10, self.TEXT_DIM)
            line_y += 14

    def _messages_rect(self, rect: rl.Rectangle) -> rl.Rectangle:
        extra_top = 0
        if self.show_model_picker:
            extra_top += self.MODEL_PICKER_HEIGHT
        if self._has_proposal():
            extra_top += self.PROPOSAL_PREVIEW_HEIGHT
        return rl.Rectangle(
            rect.x,
            rect.y + self.HEADER_HEIGHT + extra_top,
            rect.width,
            rect.height - self.HEADER_HEIGHT - extra_top - self.INPUT_HEIGHT,
        )

    def _input_rect(self, rect: rl.Rectangle) -> rl.Rectangle:
        return rl.Rectangle(
            rect.x + self.PADDING,
            rect.y + rect.height - self.INPUT_HEIGHT + self.PADDING,
            rect.width - self.PADDING * 2,
            self.INPUT_HEIGHT - self.PADDING * 2,
        )

    def _proposal_preview_rect(self, rect: rl.Rectangle) -> rl.Rectangle:
        top = rect.y + self.HEADER_HEIGHT + (self.MODEL_PICKER_HEIGHT if self.show_model_picker else 0)
        return rl.Rectangle(rect.x + self.PADDING, top + self.PADDING, rect.width - self.PADDING * 2, self.PROPOSAL_PREVIEW_HEIGHT - self.PADDING * 2)

    def _submit_input(self, mode: str) -> None:
        if self.api is None:
            self._append("assistant", "EngineAPI not connected to assistant panel.")
            return
        text = self.input_text.strip()
        if self.pending_questions:
            if not text:
                return
            question = self.pending_questions.pop(0)
            self.answers[question["id"]] = text
            self._append("user", text)
            self.input_text = ""
            if self.pending_questions:
                self._append("assistant", self.pending_questions[0]["text"])
                return
            response = self.api.handle_ai_request(self.active_prompt, mode="proposal", answers=self.answers)
            self._store_response(response)
            return

        if not text:
            return

        self.active_prompt = text
        self.answers = {}
        self._append("user", text)
        self.input_text = ""
        response = self.api.handle_ai_request(text, mode=mode)
        self._store_response(response)

    def _apply_last_proposal(self) -> None:
        if self.api is None or not self.active_prompt:
            return
        if self.pending_questions:
            self._append("assistant", "Finish the pending plan questions before applying changes.")
            return
        response = self.api.handle_ai_request(
            self.active_prompt,
            mode="execute",
            answers=self.answers,
            confirmed=True,
            allow_python=self.allow_python,
        )
        self._store_response(response)
        validation = response.get("validation") or {}
        if validation:
            self._append("assistant", f"Validation success: {validation.get('success')}")

    def _store_response(self, response: Dict[str, Any]) -> None:
        self.last_response = response
        self._append("assistant", response.get("message", "No response"))
        questions = response.get("plan", {}).get("questions", []) or []
        self.pending_questions = list(questions)
        if self.pending_questions:
            self._append("assistant", self.pending_questions[0]["text"])

    def _toggle_ollama_picker(self) -> None:
        if self.api is None:
            return
        self._refresh_provider_info()
        self.show_model_picker = not self.show_model_picker
        if self.show_model_picker:
            if self.available_models:
                self._append("assistant", f"Ollama detectado. Selecciona un modelo: {', '.join(self.available_models[:4])}")
            else:
                detail = self.models_error or "No local models detected"
                self._append("assistant", f"No se pudieron cargar modelos de Ollama. {detail}")

    def _connect_ollama(self, model_name: str) -> None:
        if self.api is None:
            return
        patch = {
            "provider_policy": {
                "mode": "local",
                "preferred_provider": "ollama_local",
                "model_name": model_name.strip(),
            }
        }
        self.api.update_ai_project_memory(patch)
        self._refresh_provider_info()
        model_label = self.provider_models_text or "No local models detected"
        self._append("assistant", f"Local provider selected: {self.provider_label}. Models: {model_label}")
        self.show_model_picker = False

    def _append(self, role: str, text: str) -> None:
        self.messages.append({"role": role, "text": text})
        self.scroll_offset = 0.0

    def _toggle_interaction_mode(self) -> None:
        self.interaction_mode = "plan" if self.interaction_mode == "normal" else "normal"
        label = "Plan" if self.interaction_mode == "plan" else "Normal"
        self._append("assistant", f"Mode changed to {label}.")

    def _send_mode(self) -> str:
        return "plan" if self.interaction_mode == "plan" else "direct"

    def _has_proposal(self) -> bool:
        proposal = self.last_response.get("proposal")
        return bool(proposal and proposal.get("actions"))

    def _build_proposal_details(self, proposal: Dict[str, Any]) -> List[str]:
        details: List[str] = []
        actions = proposal.get("actions", []) or []
        files: List[str] = []
        components: List[str] = []
        for action in actions:
            action_type = str(action.get("action_type", ""))
            args = action.get("args", {}) or {}
            kwargs = args.get("kwargs", {}) or {}
            if action_type == "python_write":
                files.append(str(args.get("target", "")))
            if action_type == "api_call":
                entity_name = str(kwargs.get("entity_name", "") or kwargs.get("name", ""))
                component_name = str(kwargs.get("component_name", ""))
                if entity_name and component_name:
                    components.append(f"{entity_name}.{component_name}")
                elif entity_name:
                    components.append(entity_name)
        if actions:
            details.append(f"Actions: {len(actions)}")
        if components:
            details.append("Touches: " + ", ".join(components[:3]))
        if files:
            details.append("Files: " + ", ".join(files[:2]))
        risk_notes = proposal.get("risk_notes", []) or []
        if risk_notes:
            details.append("Risk: " + str(risk_notes[0]))
        return details

    def _refresh_provider_info(self) -> None:
        if self.api is None:
            self.provider_label = "No provider"
            self.provider_models_text = ""
            return
        diagnostics = self.api.get_ai_provider_diagnostics()
        policy = diagnostics.get("policy", {})
        self.model_name = str(policy.get("model_name", "") or "")
        self.provider_label = str(diagnostics.get("selected_provider", "unknown"))
        models = diagnostics.get("models", [])
        self.available_models = [str(item) for item in models]
        self.models_error = str(diagnostics.get("models_error", "") or "")
        self.provider_models_text = ", ".join(models[:3]) if models else str(diagnostics.get("models_error", ""))
        if not self.model_name and models:
            self.model_name = str(models[0])

    def _draw_model_picker(self, rect: rl.Rectangle) -> None:
        picker = rl.Rectangle(
            rect.x + self.PADDING,
            rect.y + self.HEADER_HEIGHT + self.PADDING,
            rect.width - self.PADDING * 2,
            self.MODEL_PICKER_HEIGHT - self.PADDING * 2,
        )
        rl.draw_rectangle_rec(picker, self.BG_MID)
        rl.draw_rectangle_lines_ex(picker, 1, self.WARNING)
        rl.draw_text("Select Ollama model", int(picker.x + 6), int(picker.y + 6), 10, self.TEXT)

        if self._draw_button(rl.Rectangle(picker.x + picker.width - 70, picker.y + 4, 60, 20), "Refresh"):
            self._refresh_provider_info()

        if not self.available_models:
            text = self.models_error or "No Ollama models found."
            rl.draw_text(text, int(picker.x + 6), int(picker.y + 28), 10, self.WARNING)
            if self._draw_button(rl.Rectangle(picker.x + 6, picker.y + picker.height - 28, 56, 22), "Close"):
                self.show_model_picker = False
            return

        row_y = picker.y + 28
        for model in self.available_models[:4]:
            is_current = model == self.model_name
            label = f"{model} {'(active)' if is_current else ''}"
            if self._draw_button(rl.Rectangle(picker.x + 6, row_y, picker.width - 12, 22), label, active=is_current):
                self._connect_ollama(model)
            row_y += 26

    def _draw_quick_choices(self, input_rect: rl.Rectangle, choices: List[str]) -> None:
        rl.draw_text("Quick options", int(input_rect.x + 6), int(input_rect.y + 38), 10, self.TEXT_DIM)
        row_y = input_rect.y + 54
        button_width = input_rect.width - 12
        for index, choice in enumerate(choices[:3]):
            rect = rl.Rectangle(input_rect.x + 6, row_y + index * 20, button_width, 18)
            if self._draw_button(rect, choice):
                self.input_text = choice
                self._submit_input(mode="auto")

    def _draw_button(self, rect: rl.Rectangle, label: str, active: bool = False) -> bool:
        mouse = rl.get_mouse_position()
        hover = rl.check_collision_point_rec(mouse, rect)
        color = self.WARNING if active else (self.BG_LIGHT if hover else self.BG_MID)
        rl.draw_rectangle_rec(rect, color)
        rl.draw_rectangle_lines_ex(rect, 1, self.BORDER)
        rl.draw_text(label, int(rect.x + 6), int(rect.y + 6), 10, self.TEXT)
        return hover and rl.is_mouse_button_pressed(rl.MOUSE_BUTTON_LEFT)

    def _draw_toggle(self, rect: rl.Rectangle, label: str, value: bool) -> bool:
        mouse = rl.get_mouse_position()
        hover = rl.check_collision_point_rec(mouse, rect)
        color = self.WARNING if value else (self.BG_LIGHT if hover else self.BG_MID)
        rl.draw_rectangle_rec(rect, color)
        rl.draw_rectangle_lines_ex(rect, 1, self.BORDER)
        rl.draw_text(label, int(rect.x + 6), int(rect.y + 5), 10, self.TEXT)
        if hover and rl.is_mouse_button_pressed(rl.MOUSE_BUTTON_LEFT):
            return not value
        return value

    def _wrap_text(self, text: str, max_chars: int) -> List[str]:
        if not text:
            return [""]
        words = text.replace("\r", "").split()
        if not words:
            return [""]
        lines: List[str] = []
        current = words[0]
        for word in words[1:]:
            if len(current) + 1 + len(word) <= max_chars:
                current = f"{current} {word}"
            else:
                lines.append(current)
                current = word
        lines.append(current)
        return lines
