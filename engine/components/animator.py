"""
engine/components/animator.py - Componente de animaciones por sprite sheet.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from engine.assets.asset_reference import build_asset_reference, clone_asset_reference, normalize_asset_reference
from engine.ecs.component import Component


@dataclass
class AnimationData:
    """Datos de una animacion individual."""

    frames: List[int] = field(default_factory=lambda: [0])
    slice_names: List[str] = field(default_factory=list)
    fps: float = 8.0
    loop: bool = True
    on_complete: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "frames": self.frames,
            "slice_names": self.slice_names,
            "fps": self.fps,
            "loop": self.loop,
        }
        if self.on_complete is not None:
            result["on_complete"] = self.on_complete
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AnimationData":
        return cls(
            frames=data.get("frames", [0]),
            slice_names=data.get("slice_names", []),
            fps=data.get("fps", 8.0),
            loop=data.get("loop", True),
            on_complete=data.get("on_complete"),
        )

    def get_frame_count(self) -> int:
        if self.slice_names:
            return len(self.slice_names)
        return len(self.frames)


class Animator(Component):
    """Gestiona animaciones basadas en sprite sheets."""

    def __init__(
        self,
        sprite_sheet: str = "",
        sprite_sheet_ref: Any = None,
        frame_width: int = 32,
        frame_height: int = 32,
        animations: Optional[Dict[str, AnimationData]] = None,
        default_state: str = "idle",
        flip_x: bool = False,
        flip_y: bool = False,
        speed: float = 1.0,
    ) -> None:
        self.enabled: bool = True
        self.sprite_sheet_ref = normalize_asset_reference(sprite_sheet_ref if sprite_sheet_ref is not None else sprite_sheet)
        self.sprite_sheet: str = self.sprite_sheet_ref.get("path", "")
        self.frame_width: int = frame_width
        self.frame_height: int = frame_height
        self.animations: Dict[str, AnimationData] = animations or {}
        self.default_state: str = default_state
        self.flip_x: bool = flip_x
        self.flip_y: bool = flip_y
        self.speed: float = max(0.01, float(speed))

        self.current_state: str = default_state
        self.current_frame: int = 0
        self.elapsed_time: float = 0.0
        self.is_finished: bool = False

    def get_sprite_sheet_reference(self) -> dict[str, str]:
        return clone_asset_reference(self.sprite_sheet_ref)

    def sync_sprite_sheet_reference(self, reference: Any) -> None:
        self.sprite_sheet_ref = normalize_asset_reference(reference)
        self.sprite_sheet = self.sprite_sheet_ref.get("path", "")

    def play(self, state: str, force_restart: bool = False) -> str:
        if state not in self.animations:
            print(f"[WARNING] Animator: estado '{state}' no existe")
            return self.current_state
        previous_state = self.current_state
        if state == self.current_state and not force_restart:
            return previous_state
        self.current_state = state
        self.current_frame = 0
        self.elapsed_time = 0.0
        self.is_finished = False
        return previous_state

    def stop(self) -> None:
        self.is_finished = True

    def resume(self) -> None:
        if self.is_finished and self.current_state in self.animations:
            anim = self.animations[self.current_state]
            if not anim.loop:
                self.is_finished = False

    @property
    def is_playing(self) -> bool:
        if self.current_state not in self.animations:
            return False
        if self.is_finished:
            return False
        anim = self.animations[self.current_state]
        if not anim.loop:
            return False
        return True

    @property
    def normalized_time(self) -> float:
        anim = self.get_current_animation()
        if anim is None or anim.get_frame_count() <= 0:
            return 0.0
        return self.current_frame / max(1, anim.get_frame_count() - 1)

    def get_current_animation(self) -> Optional[AnimationData]:
        return self.animations.get(self.current_state)

    def get_current_sprite_frame(self) -> int:
        anim = self.get_current_animation()
        if anim is None or not anim.frames:
            return 0
        frame_index = min(self.current_frame, len(anim.frames) - 1)
        return anim.frames[frame_index]

    def get_current_slice_name(self) -> Optional[str]:
        anim = self.get_current_animation()
        if anim is None or not anim.slice_names:
            return None
        frame_index = min(self.current_frame, len(anim.slice_names) - 1)
        return anim.slice_names[frame_index]

    def get_source_rect(self, sheet_columns: int) -> tuple[int, int, int, int]:
        frame_index = self.get_current_sprite_frame()
        col = frame_index % sheet_columns
        row = frame_index // sheet_columns
        return (
            col * self.frame_width,
            row * self.frame_height,
            self.frame_width,
            self.frame_height,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "sprite_sheet": self.get_sprite_sheet_reference(),
            "sprite_sheet_path": self.sprite_sheet,
            "frame_width": self.frame_width,
            "frame_height": self.frame_height,
            "flip_x": self.flip_x,
            "flip_y": self.flip_y,
            "speed": self.speed,
            "animations": {name: anim.to_dict() for name, anim in self.animations.items()},
            "default_state": self.default_state,
            "current_state": self.current_state,
            "current_frame": self.current_frame,
            "is_finished": self.is_finished,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Animator":
        animations = {
            name: AnimationData.from_dict(anim_data)
            for name, anim_data in data.get("animations", {}).items()
        }
        sprite_sheet_ref = normalize_asset_reference(data.get("sprite_sheet"))
        sprite_sheet_path = data.get("sprite_sheet_path", data.get("sprite_sheet", ""))
        if isinstance(sprite_sheet_path, str) and sprite_sheet_path and sprite_sheet_ref.get("path") != sprite_sheet_path:
            sprite_sheet_ref = build_asset_reference(sprite_sheet_path, sprite_sheet_ref.get("guid", ""))

        animator = cls(
            sprite_sheet=sprite_sheet_path,
            sprite_sheet_ref=sprite_sheet_ref,
            frame_width=data.get("frame_width", 32),
            frame_height=data.get("frame_height", 32),
            animations=animations,
            default_state=data.get("default_state", data.get("current_state", "idle")),
            flip_x=data.get("flip_x", False),
            flip_y=data.get("flip_y", False),
            speed=data.get("speed", 1.0),
        )
        animator.enabled = data.get("enabled", True)
        animator.current_state = data.get("current_state", animator.default_state)
        animator.current_frame = data.get("current_frame", 0)
        animator.is_finished = data.get("is_finished", False)
        return animator
