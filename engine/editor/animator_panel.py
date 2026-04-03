"""
engine/editor/animator_panel.py - Workspace dedicado para authoring de Animator.
"""

from __future__ import annotations

import copy
from typing import Any, Dict, List, Optional

import pyray as rl

from engine.assets.asset_service import AssetService
from engine.components.animator import Animator
from engine.editor.render_safety import editor_scissor
from engine.resources.texture_manager import TextureManager

_UNSET = object()


def expand_slice_sequence(slice_names: List[str], start_slice_name: str, sprite_count: int) -> List[str]:
    """Expande una secuencia consecutiva de slices sin wrap-around."""
    if not slice_names or sprite_count <= 0:
        return []
    if start_slice_name not in slice_names:
        return []
    start_index = slice_names.index(start_slice_name)
    end_index = min(len(slice_names), start_index + sprite_count)
    return list(slice_names[start_index:end_index])


class AnimatorPanel:
    BG_COLOR = rl.Color(36, 36, 36, 255)
    CARD_COLOR = rl.Color(46, 46, 46, 255)
    BORDER_COLOR = rl.Color(25, 25, 25, 255)
    TEXT_COLOR = rl.Color(220, 220, 220, 255)
    DIM_COLOR = rl.Color(140, 140, 140, 255)
    ACCENT_COLOR = rl.Color(58, 121, 187, 255)
    MIN_FRAME_MS = 16
    MAX_FRAME_MS = 1000

    def __init__(self) -> None:
        self._scene_manager: Any = None
        self._project_service: Any = None
        self._asset_service: Optional[AssetService] = None
        self._texture_manager = TextureManager()

        self.selected_entity_name: str = ""
        self.selected_state_name: str = ""
        self.selected_frame_index: int = 0
        self.preview_playing: bool = False
        self.preview_frame: int = 0
        self.preview_elapsed: float = 0.0
        self.request_open_sprite_editor_for: Optional[str] = None

    def set_scene_manager(self, manager: Any) -> None:
        self._scene_manager = manager

    def set_project_service(self, project_service: Any) -> None:
        self._project_service = project_service
        self._asset_service = AssetService(project_service) if project_service is not None else None

    def reset(self) -> None:
        self.selected_entity_name = ""
        self.selected_state_name = ""
        self.selected_frame_index = 0
        self.preview_playing = False
        self.preview_frame = 0
        self.preview_elapsed = 0.0
        self.request_open_sprite_editor_for = None

    def _fps_to_frame_ms(self, fps: float) -> int:
        safe_fps = max(0.001, float(fps))
        return int(round(1000.0 / safe_fps))

    def _frame_ms_to_fps(self, frame_ms: int) -> float:
        clamped = max(self.MIN_FRAME_MS, min(self.MAX_FRAME_MS, int(frame_ms)))
        return 1000.0 / float(clamped)

    def update(self, world: Any, dt: float) -> None:
        context = self.get_selection_context(world)
        entity_name = context.get("entity_name", "")
        if entity_name != self.selected_entity_name:
            self.selected_entity_name = entity_name
            self.selected_frame_index = 0
            self.preview_playing = False
            self.preview_frame = 0
            self.preview_elapsed = 0.0

        selected_state = context.get("selected_state_name", "")
        if selected_state != self.selected_state_name:
            self.selected_state_name = selected_state
            self.selected_frame_index = 0
            self.preview_frame = 0
            self.preview_elapsed = 0.0

        state_data = context.get("selected_state_data") or {}
        slice_names = list(state_data.get("slice_names", []))
        fps = float(state_data.get("fps", 8.0))
        if not self.preview_playing or not slice_names or fps <= 0:
            return

        self.preview_elapsed += dt
        frame_duration = 1.0 / fps
        while self.preview_elapsed >= frame_duration:
            self.preview_elapsed -= frame_duration
            self.preview_frame += 1
            if self.preview_frame >= len(slice_names):
                if state_data.get("loop", True):
                    self.preview_frame = 0
                else:
                    self.preview_frame = max(0, len(slice_names) - 1)
                    self.preview_playing = False
                    break

    def get_selection_context(self, world: Any) -> Dict[str, Any]:
        entity_name = getattr(world, "selected_entity_name", "") or ""
        if not entity_name:
            return {"entity_name": "", "status": "no_selection"}

        entity = world.get_entity_by_name(entity_name)
        if entity is None:
            return {"entity_name": "", "status": "missing_entity"}

        animator = entity.get_component(Animator)
        if animator is None:
            return {"entity_name": entity_name, "status": "no_animator"}

        states = animator.to_dict().get("animations", {})
        selected_state = self.selected_state_name
        if selected_state not in states:
            selected_state = animator.default_state if animator.default_state in states else next(iter(states.keys()), "")
        selected_state_data = copy.deepcopy(states.get(selected_state) or {})
        sprite_sheet_locator: Any = animator.get_sprite_sheet_reference() if hasattr(animator, "get_sprite_sheet_reference") else animator.sprite_sheet
        if self._asset_service is not None and animator.sprite_sheet:
            entry = self._asset_service.get_asset_entry(sprite_sheet_locator)
            if entry is not None and hasattr(animator, "sync_sprite_sheet_reference"):
                animator.sync_sprite_sheet_reference(entry.get("reference", {}))
                sprite_sheet_locator = animator.get_sprite_sheet_reference()
        slices = self._asset_service.list_slices(sprite_sheet_locator) if (self._asset_service is not None and animator.sprite_sheet) else []
        slice_names = [str(item.get("name", "")) for item in slices if item.get("name")]

        return {
            "entity_name": entity_name,
            "entity": entity,
            "animator": animator,
            "status": "ready",
            "states": states,
            "selected_state_name": selected_state,
            "selected_state_data": selected_state_data,
            "sprite_sheet": animator.sprite_sheet,
            "sprite_sheet_reference": sprite_sheet_locator,
            "available_slices": slice_names,
            "has_slices": bool(slice_names),
            "sprite_sheet_ready": bool(slice_names),
        }

    def list_sprite_sheet_assets(self) -> List[Dict[str, Any]]:
        if self._project_service is None or self._asset_service is None:
            return []
        assets = self._project_service.list_assets(extensions=[".png"])
        result: List[Dict[str, Any]] = []
        for asset in assets:
            prepared = bool(self._asset_service.list_slices(asset["path"]))
            item = dict(asset)
            item["has_slices"] = prepared
            item["status_label"] = "ready" if prepared else "needs slicing"
            result.append(item)
        return result

    def set_sprite_sheet(self, world: Any, asset_path: str) -> bool:
        context = self.get_selection_context(world)
        entity_name = context.get("entity_name", "")
        if not entity_name:
            return False
        payload = self._get_animator_payload(world, entity_name)
        if payload is None:
            return False
        if self._asset_service is not None:
            payload["sprite_sheet"] = self._asset_service.get_asset_reference(asset_path)
        else:
            payload["sprite_sheet"] = asset_path
        payload["sprite_sheet_path"] = asset_path
        success = self._replace_animator_payload(world, entity_name, payload)
        if success:
            self.preview_playing = False
            self.preview_frame = 0
            self.preview_elapsed = 0.0
        return success

    def create_state(self, world: Any) -> bool:
        context = self.get_selection_context(world)
        entity_name = context.get("entity_name", "")
        if not entity_name:
            return False
        payload = self._get_animator_payload(world, entity_name)
        if payload is None:
            return False
        animations = payload.setdefault("animations", {})
        suffix = 1
        while f"state_{suffix}" in animations:
            suffix += 1
        state_name = f"state_{suffix}"
        available = list(context.get("available_slices", []))
        animations[state_name] = {
            "frames": [0],
            "slice_names": [available[0]] if available else [],
            "fps": 8.0,
            "loop": True,
            "on_complete": None,
        }
        if not payload.get("default_state"):
            payload["default_state"] = state_name
        if not payload.get("current_state"):
            payload["current_state"] = state_name
        success = self._replace_animator_payload(world, entity_name, payload)
        if success:
            self.selected_state_name = state_name
            self.selected_frame_index = 0
        return success

    def remove_state(self, world: Any, state_name: str) -> bool:
        context = self.get_selection_context(world)
        entity_name = context.get("entity_name", "")
        if not entity_name:
            return False
        payload = self._get_animator_payload(world, entity_name)
        if payload is None:
            return False
        animations = payload.setdefault("animations", {})
        if state_name not in animations:
            return False
        del animations[state_name]
        next_default = next(iter(animations.keys()), "")
        if payload.get("default_state") == state_name:
            payload["default_state"] = next_default
        if payload.get("current_state") == state_name:
            payload["current_state"] = payload.get("default_state", next_default)
        for animation in animations.values():
            if animation.get("on_complete") == state_name:
                animation["on_complete"] = None
        success = self._replace_animator_payload(world, entity_name, payload)
        if success:
            self.selected_state_name = payload.get("default_state", next(iter(animations.keys()), ""))
            self.selected_frame_index = 0
        return success

    def add_frame(self, world: Any, state_name: str) -> bool:
        context = self.get_selection_context(world)
        available = list(context.get("available_slices", []))
        if not available:
            return False
        payload = self._get_animator_payload(world, context.get("entity_name", ""))
        if payload is None:
            return False
        state = payload.setdefault("animations", {}).get(state_name)
        if state is None:
            return False
        items = list(state.get("slice_names", []))
        items.append(available[0])
        state["slice_names"] = items
        success = self._replace_animator_payload(world, context["entity_name"], payload)
        if success:
            self.selected_frame_index = len(items) - 1
        return success

    def set_frame_slice(self, world: Any, state_name: str, frame_index: int, slice_name: str) -> bool:
        payload = self._get_animator_payload(world, self.get_selection_context(world).get("entity_name", ""))
        context = self.get_selection_context(world)
        entity_name = context.get("entity_name", "")
        if payload is None or not entity_name:
            return False
        state = payload.setdefault("animations", {}).get(state_name)
        if state is None:
            return False
        items = list(state.get("slice_names", []))
        if frame_index < 0 or frame_index >= len(items):
            return False
        items[frame_index] = slice_name
        state["slice_names"] = items
        return self._replace_animator_payload(world, entity_name, payload)

    def move_frame(self, world: Any, state_name: str, frame_index: int, delta: int) -> bool:
        payload = self._get_animator_payload(world, self.get_selection_context(world).get("entity_name", ""))
        context = self.get_selection_context(world)
        entity_name = context.get("entity_name", "")
        if payload is None or not entity_name:
            return False
        state = payload.setdefault("animations", {}).get(state_name)
        if state is None:
            return False
        items = list(state.get("slice_names", []))
        target_index = frame_index + delta
        if frame_index < 0 or frame_index >= len(items) or target_index < 0 or target_index >= len(items):
            return False
        item = items.pop(frame_index)
        items.insert(target_index, item)
        state["slice_names"] = items
        success = self._replace_animator_payload(world, entity_name, payload)
        if success:
            self.selected_frame_index = target_index
        return success

    def remove_frame(self, world: Any, state_name: str, frame_index: int) -> bool:
        payload = self._get_animator_payload(world, self.get_selection_context(world).get("entity_name", ""))
        context = self.get_selection_context(world)
        entity_name = context.get("entity_name", "")
        if payload is None or not entity_name:
            return False
        state = payload.setdefault("animations", {}).get(state_name)
        if state is None:
            return False
        items = list(state.get("slice_names", []))
        if frame_index < 0 or frame_index >= len(items):
            return False
        del items[frame_index]
        state["slice_names"] = items
        success = self._replace_animator_payload(world, entity_name, payload)
        if success:
            self.selected_frame_index = max(0, min(self.selected_frame_index, max(0, len(items) - 1)))
        return success

    def cycle_frame_slice(self, world: Any, state_name: str, frame_index: int, direction: int) -> bool:
        context = self.get_selection_context(world)
        available = list(context.get("available_slices", []))
        state_data = context.get("states", {}).get(state_name, {})
        items = list(state_data.get("slice_names", []))
        if not available or frame_index < 0 or frame_index >= len(items):
            return False
        current = items[frame_index]
        current_index = available.index(current) if current in available else 0
        new_index = max(0, min(len(available) - 1, current_index + direction))
        return self.set_frame_slice(world, state_name, frame_index, available[new_index])

    def set_state_field(
        self,
        world: Any,
        state_name: str,
        *,
        fps: Optional[float] = None,
        loop: Optional[bool] = None,
        on_complete: Any = _UNSET,
        set_default: bool = False,
    ) -> bool:
        context = self.get_selection_context(world)
        entity_name = context.get("entity_name", "")
        if not entity_name:
            return False
        payload = self._get_animator_payload(world, entity_name)
        if payload is None:
            return False
        animations = payload.setdefault("animations", {})
        state = animations.get(state_name)
        if state is None:
            return False
        if fps is not None:
            state["fps"] = float(fps)
        if loop is not None:
            state["loop"] = bool(loop)
        if on_complete is not _UNSET:
            state["on_complete"] = on_complete if on_complete in animations and on_complete != state_name else None
        if set_default or not payload.get("default_state"):
            payload["default_state"] = state_name
        if payload.get("current_state") not in animations:
            payload["current_state"] = payload.get("default_state", state_name)
        return self._replace_animator_payload(world, entity_name, payload)

    def render(self, world: Any, x: int, y: int, width: int, height: int) -> None:
        view_rect = rl.Rectangle(x, y, width, height)
        with editor_scissor(view_rect):
            rl.draw_rectangle_rec(view_rect, self.BG_COLOR)

            context = self.get_selection_context(world)
            status = context.get("status")
            if status != "ready":
                self._draw_empty_state(status, x, y, width, height)
                return

            left_w = int(width * 0.28)
            center_w = int(width * 0.40)
            right_w = width - left_w - center_w - 16
            left_rect = rl.Rectangle(x + 4, y + 4, left_w, height - 8)
            center_rect = rl.Rectangle(left_rect.x + left_rect.width + 4, y + 4, center_w, height - 8)
            right_rect = rl.Rectangle(center_rect.x + center_rect.width + 4, y + 4, right_w, height - 8)

            self._draw_states_column(world, context, left_rect)
            self._draw_state_editor(world, context, center_rect)
            self._draw_preview_column(context, right_rect)

    def _draw_empty_state(self, status: str, x: int, y: int, width: int, height: int) -> None:
        title = "Animator"
        message = {
            "no_selection": "Select an entity to edit Animator clips.",
            "missing_entity": "Selected entity no longer exists.",
            "no_animator": "Selected entity has no Animator component.",
        }.get(status, "Animator workspace unavailable.")
        rl.draw_text(title, x + 16, y + 16, 18, self.TEXT_COLOR)
        rl.draw_text(message, x + 16, y + 48, 12, self.DIM_COLOR)
        rl.draw_rectangle_lines(x + 12, y + 12, width - 24, height - 24, self.BORDER_COLOR)

    def _draw_card(self, rect: rl.Rectangle, title: str) -> int:
        rl.draw_rectangle_rec(rect, self.CARD_COLOR)
        rl.draw_rectangle_lines_ex(rect, 1, self.BORDER_COLOR)
        rl.draw_text(title, int(rect.x + 10), int(rect.y + 8), 12, self.TEXT_COLOR)
        return int(rect.y + 34)

    def _draw_states_column(self, world: Any, context: Dict[str, Any], rect: rl.Rectangle) -> None:
        current_y = self._draw_card(rect, f"States: {context['entity_name']}")
        add_rect = rl.Rectangle(rect.x + 10, current_y, rect.width - 20, 22)
        if rl.gui_button(add_rect, "Add State"):
            self.create_state(world)
        current_y += 28

        selected_state = context.get("selected_state_name", "")
        for state_name, state_data in context.get("states", {}).items():
            row_rect = rl.Rectangle(rect.x + 10, current_y, rect.width - 20, 30)
            hover = rl.check_collision_point_rec(rl.get_mouse_position(), row_rect)
            active = state_name == selected_state
            color = self.ACCENT_COLOR if active else (rl.Color(60, 60, 60, 255) if hover else rl.Color(52, 52, 52, 255))
            rl.draw_rectangle_rec(row_rect, color)
            rl.draw_text(state_name, int(row_rect.x + 8), int(row_rect.y + 5), 11, self.TEXT_COLOR)
            rl.draw_text(f"{len(state_data.get('slice_names', []))} frames", int(row_rect.x + 8), int(row_rect.y + 17), 9, self.DIM_COLOR)
            if hover and rl.is_mouse_button_pressed(rl.MOUSE_BUTTON_LEFT):
                self.selected_state_name = state_name
                self.selected_frame_index = 0
                self.preview_frame = 0
                self.preview_elapsed = 0.0
            current_y += 36

        current_y += 8
        rl.draw_text("Sprite Sheets", int(rect.x + 10), int(current_y), 11, self.TEXT_COLOR)
        current_y += 18
        for asset in self.list_sprite_sheet_assets()[:7]:
            row_rect = rl.Rectangle(rect.x + 10, current_y, rect.width - 20, 28)
            hover = rl.check_collision_point_rec(rl.get_mouse_position(), row_rect)
            active = asset["path"] == context.get("sprite_sheet", "")
            base_color = self.ACCENT_COLOR if active else (rl.Color(62, 62, 62, 255) if hover else rl.Color(48, 48, 48, 255))
            rl.draw_rectangle_rec(row_rect, base_color)
            rl.draw_text(asset["name"], int(row_rect.x + 6), int(row_rect.y + 4), 10, self.TEXT_COLOR)
            rl.draw_text(asset["status_label"], int(row_rect.x + 6), int(row_rect.y + 15), 9, self.DIM_COLOR)
            if hover and rl.is_mouse_button_pressed(rl.MOUSE_BUTTON_LEFT):
                self.set_sprite_sheet(world, asset["path"])
            current_y += 32

    def _draw_state_editor(self, world: Any, context: Dict[str, Any], rect: rl.Rectangle) -> None:
        current_y = self._draw_card(rect, "Frames")
        state_name = context.get("selected_state_name", "")
        state_data = context.get("selected_state_data")
        if not state_name or state_data is None:
            rl.draw_text("Create or select a state.", int(rect.x + 10), int(current_y), 11, self.DIM_COLOR)
            return

        sprite_sheet = context.get("sprite_sheet", "")
        if not sprite_sheet:
            rl.draw_text("Choose a PNG from the project list.", int(rect.x + 10), int(current_y), 11, self.DIM_COLOR)
            return

        if not context.get("has_slices", False):
            rl.draw_text("This PNG still needs slicing metadata.", int(rect.x + 10), int(current_y), 11, self.DIM_COLOR)
            current_y += 24
            info_rect = rl.Rectangle(rect.x + 10, current_y, rect.width - 20, 22)
            rl.draw_rectangle_rec(info_rect, rl.Color(40, 40, 40, 255))
            rl.draw_text(sprite_sheet, int(info_rect.x + 6), int(info_rect.y + 6), 10, self.DIM_COLOR)
            current_y += 28
            cta_rect = rl.Rectangle(rect.x + 10, current_y, rect.width - 20, 24)
            if rl.gui_button(cta_rect, "Open Sprite Editor"):
                self.request_open_sprite_editor_for = sprite_sheet
            return

        fps = float(state_data.get("fps", 8.0))
        loop = bool(state_data.get("loop", True))
        on_complete = state_data.get("on_complete")

        rl.draw_text(f"State: {state_name}", int(rect.x + 10), int(current_y), 12, self.TEXT_COLOR)
        current_y += 24
        current_y = self._draw_value_stepper(rect, current_y, "FPS", f"{fps:.1f}", lambda: self.set_state_field(world, state_name, fps=max(1.0, fps - 1.0)), lambda: self.set_state_field(world, state_name, fps=fps + 1.0))
        frame_ms = self._fps_to_frame_ms(fps)
        current_y = self._draw_value_stepper(
            rect,
            current_y,
            "Frame ms",
            str(frame_ms),
            lambda: self.set_state_field(world, state_name, fps=self._frame_ms_to_fps(frame_ms - 10)),
            lambda: self.set_state_field(world, state_name, fps=self._frame_ms_to_fps(frame_ms + 10)),
        )

        loop_rect = rl.Rectangle(rect.x + 10, current_y, rect.width - 20, 22)
        if rl.gui_button(loop_rect, f"Loop: {'ON' if loop else 'OFF'}"):
            self.set_state_field(world, state_name, loop=not loop)
        current_y += 28

        default_rect = rl.Rectangle(rect.x + 10, current_y, rect.width - 20, 22)
        if rl.gui_button(default_rect, f"Default State: {'YES' if context['animator'].default_state == state_name else 'SET DEFAULT'}"):
            self.set_state_field(world, state_name, set_default=True)
        current_y += 28

        rl.draw_text("On Complete", int(rect.x + 10), int(current_y), 11, self.TEXT_COLOR)
        current_y += 18
        all_targets = [""] + [name for name in context.get("states", {}).keys() if name != state_name]
        for target in all_targets[:5]:
            label = "None" if not target else target
            row_rect = rl.Rectangle(rect.x + 10, current_y, rect.width - 20, 20)
            active = (on_complete or "") == target
            if rl.gui_button(row_rect, f"{'* ' if active else ''}{label}"):
                self.set_state_field(world, state_name, on_complete=target or None)
            current_y += 24

        add_frame_rect = rl.Rectangle(rect.x + 10, current_y + 4, rect.width - 20, 22)
        if rl.gui_button(add_frame_rect, "Add Frame"):
            self.add_frame(world, state_name)
        current_y += 32

        frame_items = list(state_data.get("slice_names", []))
        if not frame_items:
            rl.draw_text("This state has no frames yet.", int(rect.x + 10), int(current_y), 10, self.DIM_COLOR)
            current_y += 18

        for index, frame_name in enumerate(frame_items[:8]):
            row_rect = rl.Rectangle(rect.x + 10, current_y, rect.width - 20, 24)
            active = index == self.selected_frame_index
            rl.draw_rectangle_rec(row_rect, self.ACCENT_COLOR if active else rl.Color(40, 40, 40, 255))
            rl.draw_text(f"#{index}", int(row_rect.x + 6), int(row_rect.y + 6), 10, self.TEXT_COLOR)
            prev_rect = rl.Rectangle(row_rect.x + 34, row_rect.y, 20, 24)
            next_rect = rl.Rectangle(row_rect.x + 58, row_rect.y, 20, 24)
            move_up_rect = rl.Rectangle(row_rect.x + row_rect.width - 66, row_rect.y, 20, 24)
            move_down_rect = rl.Rectangle(row_rect.x + row_rect.width - 44, row_rect.y, 20, 24)
            delete_rect = rl.Rectangle(row_rect.x + row_rect.width - 22, row_rect.y, 20, 24)
            value_rect = rl.Rectangle(row_rect.x + 82, row_rect.y, row_rect.width - 152, 24)

            if rl.gui_button(prev_rect, "<"):
                self.cycle_frame_slice(world, state_name, index, -1)
            rl.draw_rectangle_rec(value_rect, rl.Color(32, 32, 32, 255))
            rl.draw_text(frame_name or "-", int(value_rect.x + 6), int(value_rect.y + 6), 10, self.TEXT_COLOR)
            if rl.gui_button(next_rect, ">"):
                self.cycle_frame_slice(world, state_name, index, 1)
            if rl.gui_button(move_up_rect, "^"):
                self.move_frame(world, state_name, index, -1)
            if rl.gui_button(move_down_rect, "v"):
                self.move_frame(world, state_name, index, 1)
            if rl.gui_button(delete_rect, "x"):
                self.remove_frame(world, state_name, index)

            if rl.check_collision_point_rec(rl.get_mouse_position(), row_rect) and rl.is_mouse_button_pressed(rl.MOUSE_BUTTON_LEFT):
                self.selected_frame_index = index
                self.preview_frame = index
                self.preview_elapsed = 0.0
            current_y += 28

        remove_rect = rl.Rectangle(rect.x + 10, rect.y + rect.height - 32, rect.width - 20, 22)
        if rl.gui_button(remove_rect, "Remove State"):
            self.remove_state(world, state_name)

    def _draw_value_stepper(self, rect: rl.Rectangle, y: int, label: str, value: str, on_minus: Any, on_plus: Any) -> int:
        rl.draw_text(label, int(rect.x + 10), int(y + 5), 10, self.TEXT_COLOR)
        minus_rect = rl.Rectangle(rect.x + rect.width - 104, y, 22, 22)
        plus_rect = rl.Rectangle(rect.x + rect.width - 24, y, 22, 22)
        value_rect = rl.Rectangle(rect.x + rect.width - 78, y, 50, 22)
        if rl.gui_button(minus_rect, "-"):
            on_minus()
        rl.draw_rectangle_rec(value_rect, rl.Color(40, 40, 40, 255))
        rl.draw_text(value, int(value_rect.x + 4), int(value_rect.y + 6), 10, self.TEXT_COLOR)
        if rl.gui_button(plus_rect, "+"):
            on_plus()
        return y + 28

    def _draw_preview_column(self, context: Dict[str, Any], rect: rl.Rectangle) -> None:
        current_y = self._draw_card(rect, "Preview")
        state_data = context.get("selected_state_data")
        if state_data is None:
            rl.draw_text("No state selected.", int(rect.x + 10), int(current_y), 11, self.DIM_COLOR)
            return
        if not context.get("has_slices", False):
            rl.draw_text("Generate slices to preview this animation.", int(rect.x + 10), int(current_y), 11, self.DIM_COLOR)
            return
        slice_names = list(state_data.get("slice_names", []))
        if not slice_names:
            rl.draw_text("This state has no frames.", int(rect.x + 10), int(current_y), 11, self.DIM_COLOR)
            return

        play_rect = rl.Rectangle(rect.x + 10, current_y, 60, 22)
        stop_rect = rl.Rectangle(rect.x + 76, current_y, 60, 22)
        if rl.gui_button(play_rect, "Play"):
            self.preview_playing = True
            self.preview_frame = min(self.selected_frame_index, len(slice_names) - 1)
        if rl.gui_button(stop_rect, "Stop"):
            self.preview_playing = False
            self.preview_frame = min(self.selected_frame_index, len(slice_names) - 1)
            self.preview_elapsed = 0.0
        current_y += 30

        preview_index = min(self.preview_frame, len(slice_names) - 1)
        preview_name = slice_names[preview_index]
        rl.draw_text(f"Frame {preview_index}: {preview_name}", int(rect.x + 10), int(current_y), 10, self.TEXT_COLOR)
        current_y += 18
        preview_rect = rl.Rectangle(rect.x + 10, current_y, rect.width - 20, min(rect.width - 20, rect.height - 96))
        self._draw_preview_texture(context.get("sprite_sheet", ""), preview_name, preview_rect)
        current_y += int(preview_rect.height + 8)
        rl.draw_text(f"{len(slice_names)} frames", int(rect.x + 10), int(current_y), 10, self.DIM_COLOR)

    def _draw_preview_texture(self, asset_path: str, slice_name: str, rect: rl.Rectangle) -> None:
        rl.draw_rectangle_rec(rect, rl.Color(32, 32, 32, 255))
        rl.draw_rectangle_lines_ex(rect, 1, self.BORDER_COLOR)
        if self._asset_service is None or self._project_service is None or not asset_path or not slice_name:
            return
        slice_rect = self._asset_service.get_slice_rect(asset_path, slice_name)
        if slice_rect is None:
            return
        texture = self._texture_manager.load(self._project_service.resolve_path(asset_path).as_posix())
        if texture.id == 0:
            return
        source = rl.Rectangle(slice_rect["x"], slice_rect["y"], slice_rect["width"], slice_rect["height"])
        scale = min(rect.width / max(1.0, source.width), rect.height / max(1.0, source.height))
        dest_w = source.width * scale
        dest_h = source.height * scale
        dest = rl.Rectangle(rect.x + (rect.width - dest_w) / 2, rect.y + (rect.height - dest_h) / 2, dest_w, dest_h)
        rl.draw_texture_pro(texture, source, dest, rl.Vector2(0, 0), 0.0, rl.WHITE)

    def _get_animator_payload(self, world: Any, entity_name: str) -> Optional[Dict[str, Any]]:
        if self._scene_manager is not None and self._scene_manager.current_scene is not None:
            entity_data = self._scene_manager.current_scene.find_entity(entity_name)
            if entity_data is not None:
                component_data = entity_data.get("components", {}).get("Animator")
                if component_data is not None:
                    return copy.deepcopy(component_data)
        entity = world.get_entity_by_name(entity_name)
        if entity is None:
            return None
        animator = entity.get_component(Animator)
        if animator is None:
            return None
        return copy.deepcopy(animator.to_dict())

    def _replace_animator_payload(self, world: Any, entity_name: str, payload: Dict[str, Any]) -> bool:
        if self._scene_manager is not None:
            return self._scene_manager.replace_component_data(entity_name, "Animator", copy.deepcopy(payload))
        entity = world.get_entity_by_name(entity_name)
        if entity is None:
            return False
        animator = entity.get_component(Animator)
        if animator is None:
            return False
        replacement = Animator.from_dict(payload)
        entity.add_component(replacement)
        return True

    def cleanup(self) -> None:
        self._texture_manager.unload_all()
