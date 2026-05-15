"""Theme editor panel — allows live editing of theme colors."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from engine.editor.theme import (
    THEME_REGISTRY,
    EditorTheme,
    ThemeRegistry,
    get_active_theme,
)


def _rl():
    import pyray as rl
    return rl


def _clamp(v: int, lo: int = 0, hi: int = 255) -> int:
    return max(lo, min(hi, v))


@dataclass
class ThemeEditorState:
    selected_color: str | None = None
    r: int = 0
    g: int = 0
    b: int = 0
    dirty: bool = False


class ThemeEditorPanel:
    """Panel interactivo que muestra y edita colores del tema activo."""

    def __init__(self, registry: ThemeRegistry | None = None) -> None:
        self._registry = registry or THEME_REGISTRY
        self._state = ThemeEditorState()
        self._color_names = list(get_active_theme().colors.keys())

    @property
    def state(self) -> ThemeEditorState:
        return self._state

    def _select_color(self, name: str) -> None:
        theme = get_active_theme()
        rgba = theme.colors.get(name)
        if rgba is None:
            return
        self._state.selected_color = name
        self._state.r, self._state.g, self._state.b = rgba[0], rgba[1], rgba[2]

    def _apply_color(self) -> None:
        name = self._state.selected_color
        if not name:
            return
        r, g, b = _clamp(self._state.r), _clamp(self._state.g), _clamp(self._state.b)
        theme = get_active_theme()
        current = theme.colors.get(name, (128, 128, 128, 255))
        a = current[3]
        data = theme.to_dict()
        data["colors"][name] = [r, g, b, a]
        new_theme = EditorTheme.from_dict(data)
        self._registry.register(new_theme)
        self._registry.set_active(new_theme.name)
        self._state.dirty = True

    def _render_slider(
        self,
        label: str,
        value: int,
        x: int,
        y: int,
        w: int,
        mouse_pos: tuple[int, int],
        clicked: bool,
    ) -> int:
        rl = _rl()
        rl.draw_text(f"{label}: {value}", x, y, 10, rl.Color(180, 180, 180, 255))
        track_y = y + 13
        rl.draw_rectangle(x, track_y, w, 8, rl.Color(50, 50, 50, 255))
        fill_w = int(w * _clamp(value) / 255)
        rl.draw_rectangle(x, track_y, fill_w, 8, rl.Color(80, 160, 240, 255))
        rl.draw_rectangle_lines(x, track_y, w, 8, rl.Color(90, 90, 90, 255))
        if clicked and w > 0:
            mx, my = mouse_pos
            if x <= mx <= x + w and track_y <= my <= track_y + 8:
                return _clamp(int((mx - x) / w * 255))
        return value

    def render(
        self,
        rect: tuple[int, int, int, int],
        mouse_pos: tuple[int, int] = (0, 0),
        clicked: bool = False,
        right_clicked: bool = False,
    ) -> dict[str, tuple[int, int, int]]:
        rl = _rl()
        x, y, w, h = rect
        theme = get_active_theme()
        mx, my = mouse_pos
        changes: dict[str, tuple[int, int, int]] = {}

        yo = y + 4
        rl.draw_text("Theme Editor", x + 6, yo, 13, rl.Color(220, 220, 220, 255))
        yo += 20

        for color_name in self._color_names:
            if yo + 22 > y + h:
                break

            rgba = theme.colors.get(color_name, (128, 128, 128, 255))
            selected = color_name == self._state.selected_color

            if clicked and x + 4 <= mx <= x + w - 4 and yo <= my <= yo + 20:
                self._select_color(color_name)

            px = x + 8
            py = yo + 2
            pw = 16
            rl.draw_rectangle(px, py, pw, pw, rl.Color(rgba[0], rgba[1], rgba[2], 255))
            rl.draw_rectangle_lines(px, py, pw, pw, rl.Color(80, 80, 80, 255))

            txt_color = rl.Color(255, 200, 100, 255) if selected else rl.Color(200, 200, 200, 255)
            rl.draw_text(color_name, px + pw + 6, py, 12, txt_color)

            yo += 22

            if selected:
                sl_x = x + 32
                sl_w = w - 44
                if sl_w < 40:
                    sl_w = 40

                for attr, label in (("r", "R"), ("g", "G"), ("b", "B")):
                    if yo + 24 > y + h:
                        break
                    old_val = getattr(self._state, attr)
                    new_val = self._render_slider(label, old_val, sl_x, yo, sl_w, mouse_pos, clicked)
                    new_val = _clamp(new_val)
                    setattr(self._state, attr, new_val)
                    if new_val != old_val:
                        self._apply_color()
                        changes[color_name] = (
                            _clamp(self._state.r),
                            _clamp(self._state.g),
                            _clamp(self._state.b),
                        )
                    yo += 24

        return changes

    def save_state(self, path: str = ".motor/editor_state.json") -> None:
        p = Path(path)
        data: dict = {}
        if p.exists():
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                data = {}
        preferences = data.get("preferences", {})
        if not isinstance(preferences, dict):
            preferences = {}
        theme = get_active_theme()
        preferences["editor_theme"] = theme.name
        preferences["custom_theme_colors"] = theme.to_dict()
        data["preferences"] = preferences
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def load_state(self, path: str = ".motor/editor_state.json") -> None:
        p = Path(path)
        if not p.exists():
            return
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return
        preferences = data.get("preferences", {})
        if not isinstance(preferences, dict):
            return
        custom = preferences.get("custom_theme_colors")
        if not isinstance(custom, dict):
            return
        try:
            theme = EditorTheme.from_dict(custom)
            self._registry.register(theme)
            self._registry.set_active(theme.name)
        except (ValueError, TypeError):
            pass
