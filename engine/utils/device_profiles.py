"""Shared device profiles for editor preview and export window config."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

FIT_PANEL_PROFILE_ID = "fit_panel"
DEFAULT_EXPORT_WIDTH = 1280
DEFAULT_EXPORT_HEIGHT = 720


@dataclass(frozen=True, slots=True)
class DeviceProfile:
    id: str
    label: str
    width: int | None
    height: int | None

    @property
    def fixed_size(self) -> tuple[int, int] | None:
        if self.width is None or self.height is None:
            return None
        return (self.width, self.height)


DEVICE_PROFILES: tuple[DeviceProfile, ...] = (
    DeviceProfile(FIT_PANEL_PROFILE_ID, "Fit Panel", None, None),
    DeviceProfile("mobile_portrait", "Mobile Portrait", 390, 844),
    DeviceProfile("mobile_landscape", "Mobile Landscape", 844, 390),
    DeviceProfile("tablet_landscape", "Tablet Landscape", 1180, 820),
    DeviceProfile("desktop_16_9", "Desktop 16:9", 1280, 720),
    DeviceProfile("desktop_16_10", "Desktop 16:10", 1440, 900),
    DeviceProfile("desktop_ultrawide", "Desktop Ultrawide", 2560, 1080),
)

_DEVICE_PROFILE_BY_ID = {profile.id: profile for profile in DEVICE_PROFILES}


def list_device_profiles() -> tuple[DeviceProfile, ...]:
    return DEVICE_PROFILES


def get_device_profile(profile_id: object) -> DeviceProfile:
    return _DEVICE_PROFILE_BY_ID.get(str(profile_id or ""), _DEVICE_PROFILE_BY_ID[FIT_PANEL_PROFILE_ID])


def is_known_device_profile(profile_id: object) -> bool:
    return str(profile_id or "") in _DEVICE_PROFILE_BY_ID


def next_device_profile_id(profile_id: object) -> str:
    profiles = list_device_profiles()
    current = get_device_profile(profile_id).id
    for index, profile in enumerate(profiles):
        if profile.id == current:
            return profiles[(index + 1) % len(profiles)].id
    return profiles[0].id


def resolve_preview_size(profile_id: object, panel_width: int, panel_height: int) -> tuple[int, int]:
    profile = get_device_profile(profile_id)
    fixed_size = profile.fixed_size
    if fixed_size is not None:
        return fixed_size
    return (max(1, int(panel_width)), max(1, int(panel_height)))


def resolve_window_config(window: dict[str, Any] | None) -> dict[str, Any]:
    result: dict[str, Any] = dict(window or {})
    profile = get_device_profile(result.get("device_profile"))
    fixed_size = profile.fixed_size
    default_width = fixed_size[0] if fixed_size is not None else DEFAULT_EXPORT_WIDTH
    default_height = fixed_size[1] if fixed_size is not None else DEFAULT_EXPORT_HEIGHT

    result["width"] = _resolve_positive_int(result.get("width"), default_width)
    result["height"] = _resolve_positive_int(result.get("height"), default_height)
    result.setdefault("resizable", True)
    result.setdefault("fullscreen", False)
    if "device_profile" in result:
        result["device_profile"] = profile.id
    return result


def _resolve_positive_int(value: object, fallback: int) -> int:
    if not isinstance(value, (str, bytes, bytearray, int, float)):
        return int(fallback)
    try:
        resolved = int(value)
    except (TypeError, ValueError):
        return int(fallback)
    return resolved if resolved > 0 else int(fallback)
