"""Pure popup model and placement helpers."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

Rect = tuple[float, float, float, float]


@dataclass
class PopupModel:
    """Serializable popup/dialog state with pure placement helpers."""

    name: str = ""
    visible: bool = False
    rect: Rect = (0.0, 0.0, 0.0, 0.0)
    modal: bool = False
    close_on_outside: bool = True
    anchor: Rect | None = None
    z_index: int = 1000
    title: str = ""
    message: str = ""
    buttons: list[str] = field(default_factory=list)
    dialog_type: str = ""
    schema_version: int = 1

    def open(self, rect: Rect | None = None, anchor: Rect | None = None) -> None:
        """Show popup and optionally update rect/anchor."""

        if rect is not None:
            self.rect = _normalize_rect(rect)
        if anchor is not None:
            self.anchor = _normalize_rect(anchor)
        self.visible = True

    def close(self) -> None:
        self.visible = False

    def toggle(self, rect: Rect | None = None) -> None:
        if self.visible:
            self.close()
        else:
            self.open(rect=rect)

    def contains_point(self, x: float, y: float) -> bool:
        rx, ry, rw, rh = self.rect
        return self.visible and rx <= x <= rx + rw and ry <= y <= ry + rh

    def handle_pointer_down(self, x: float, y: float) -> str:
        """Handle outside-click close policy without rendering dependencies."""

        if not self.visible:
            return "ignored"
        if self.contains_point(x, y):
            return "inside"
        if self.close_on_outside:
            self.close()
            return "closed"
        return "outside"

    def place_below(self, anchor: Rect, size: tuple[float, float], viewport: tuple[float, float]) -> Rect:
        """Place popup near anchor, flipping above when needed."""

        ax, ay, aw, ah = _normalize_rect(anchor)
        width, height = max(0.0, size[0]), max(0.0, size[1])
        vw, vh = max(0.0, viewport[0]), max(0.0, viewport[1])
        x = min(max(0.0, ax), max(0.0, vw - width))
        y = ay + ah
        if y + height > vh and ay - height >= 0:
            y = ay - height
        else:
            y = min(max(0.0, y), max(0.0, vh - height))
        self.anchor = (ax, ay, aw, ah)
        self.rect = (x, y, width, height)
        return self.rect

    def to_dict(self) -> dict[str, object]:
        """Serialize popup state to JSON-compatible primitives."""

        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> "PopupModel":
        """Build popup state from a `to_dict()` payload."""

        payload: dict[str, Any] = dict(data)
        payload["rect"] = _normalize_rect(_rect_from_payload(payload.get("rect")))
        anchor = payload.get("anchor")
        payload["anchor"] = None if anchor is None else _normalize_rect(_rect_from_payload(anchor))
        payload["buttons"] = [str(button) for button in payload.get("buttons", [])]
        return cls(**payload)


@dataclass
class PopupManager:
    """LIFO manager for active popup stack."""

    stack: list[PopupModel] = field(default_factory=list)

    @property
    def top(self) -> PopupModel | None:
        return self.stack[-1] if self.stack else None

    def push(self, popup: PopupModel) -> PopupModel:
        popup.z_index = 1000 + len(self.stack)
        popup.visible = True
        self.stack.append(popup)
        return popup

    def pop(self) -> PopupModel | None:
        if not self.stack:
            return None
        popup = self.stack.pop()
        popup.close()
        return popup

    def handle_pointer_down(self, x: float, y: float) -> str:
        popup = self.top
        if popup is None:
            return "ignored"
        result = popup.handle_pointer_down(x, y)
        if result == "closed":
            self.stack.pop()
        return result


def alert_popup(title: str, message: str, rect: Rect = (0.0, 0.0, 320.0, 140.0)) -> PopupModel:
    """Create visible modal alert popup data."""

    return PopupModel(
        name="alert",
        visible=True,
        rect=_normalize_rect(rect),
        modal=True,
        title=title,
        message=message,
        buttons=["ok"],
        dialog_type="alert",
    )


def confirm_popup(title: str, message: str, rect: Rect = (0.0, 0.0, 360.0, 160.0)) -> PopupModel:
    """Create visible modal confirm popup data."""

    return PopupModel(
        name="confirm",
        visible=True,
        rect=_normalize_rect(rect),
        modal=True,
        title=title,
        message=message,
        buttons=["cancel", "ok"],
        dialog_type="confirm",
    )


def yes_no_popup(title: str, message: str, rect: Rect = (0.0, 0.0, 360.0, 160.0)) -> PopupModel:
    """Create visible modal yes/no popup data."""

    return PopupModel(
        name="yes_no",
        visible=True,
        rect=_normalize_rect(rect),
        modal=True,
        title=title,
        message=message,
        buttons=["no", "yes"],
        dialog_type="yes_no",
    )


def _normalize_rect(rect: Rect) -> Rect:
    x, y, w, h = rect
    return (float(x), float(y), max(0.0, float(w)), max(0.0, float(h)))


def _rect_from_payload(value: object) -> Rect:
    if isinstance(value, (list, tuple)) and len(value) == 4:
        return (float(value[0]), float(value[1]), float(value[2]), float(value[3]))
    return (0.0, 0.0, 0.0, 0.0)
