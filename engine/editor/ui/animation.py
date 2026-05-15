"""Editor UI animation system — lerp interpolations for smooth transitions."""

from __future__ import annotations

from dataclasses import dataclass, field

from engine.editor.ui_core.colors import lerp_color


@dataclass
class LerpValue:
    """Float lerp for position/size/opacity animations."""
    current: float = 0.0
    target: float = 0.0
    speed: float = 6.0

    def tick(self, dt: float) -> float:
        diff = self.target - self.current
        if abs(diff) < 0.001:
            self.current = self.target
            return self.current
        self.current += diff * min(dt * self.speed, 1.0)
        return self.current

    def set_target(self, value: float) -> None:
        self.target = value

    @property
    def is_done(self) -> bool:
        return abs(self.current - self.target) < 0.001


@dataclass
class ColorLerp:
    """RGBA color lerp for hover/focus transitions."""
    current: tuple[int, int, int, int] = (255, 255, 255, 255)
    target: tuple[int, int, int, int] = (255, 255, 255, 255)
    speed: float = 8.0

    def tick(self, dt: float) -> tuple[int, int, int, int]:
        factor = min(dt * self.speed, 1.0)
        self.current = lerp_color(self.current, self.target, factor)
        return self.current

    def set_target(self, color: tuple[int, int, int, int]) -> None:
        self.target = color

    @property
    def is_done(self) -> bool:
        return self.current == self.target


@dataclass
class PanelAnimation:
    """Combined slide + fade animation for panels."""
    slide: LerpValue = field(default_factory=lambda: LerpValue(current=0.0, target=0.0, speed=8.0))
    fade: LerpValue = field(default_factory=lambda: LerpValue(current=1.0, target=1.0, speed=6.0))

    def tick(self, dt: float) -> tuple[float, float]:
        return (self.slide.tick(dt), self.fade.tick(dt))


@dataclass
class AnimationController:
    """Manages multiple named animations. Lazy-initializes on first access."""
    _lerps: dict[str, LerpValue] = field(default_factory=dict)
    _color_lerps: dict[str, ColorLerp] = field(default_factory=dict)
    _panels: dict[str, PanelAnimation] = field(default_factory=dict)

    def get_lerp(self, key: str, speed: float = 6.0) -> LerpValue:
        if key not in self._lerps:
            self._lerps[key] = LerpValue(speed=speed)
        return self._lerps[key]

    def get_color_lerp(self, key: str, speed: float = 8.0) -> ColorLerp:
        if key not in self._color_lerps:
            self._color_lerps[key] = ColorLerp(speed=speed)
        return self._color_lerps[key]

    def get_panel(self, key: str) -> PanelAnimation:
        if key not in self._panels:
            self._panels[key] = PanelAnimation()
        return self._panels[key]

    def tick_all(self, dt: float) -> None:
        for lerp in self._lerps.values():
            lerp.tick(dt)
        for clr in self._color_lerps.values():
            clr.tick(dt)
        for panel in self._panels.values():
            panel.tick(dt)
