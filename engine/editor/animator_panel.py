"""
engine/editor/animator_panel.py - Workspace dedicado para authoring de Animator.
"""

from __future__ import annotations

import copy
import re
from typing import Any, Dict, List, Optional

import pyray as rl
from engine.assets.asset_service import AssetService
from engine.components.animator import Animator
from engine.editor.render_safety import editor_scissor
from engine.resources.texture_manager import TextureManager

_UNSET = object()
_SLICE_SEQUENCE_PATTERN = re.compile(r"^(.*?)(\d+)$")
_TRAILING_STATE_NUMBER_PATTERN = re.compile(r"_(\d+)$")


def expand_slice_sequence(slice_names: List[str], start_slice_name: str, sprite_count: int) -> List[str]:
    """Expande una secuencia consecutiva de slices sin wrap-around."""
    if not slice_names or sprite_count <= 0:
        return []
    if start_slice_name not in slice_names:
        return []
    start_index = slice_names.index(start_slice_name)
    end_index = min(len(slice_names), start_index + sprite_count)
    return list(slice_names[start_index:end_index])


def detect_slice_sequences(slice_names: List[str]) -> List[List[str]]:
    grouped: Dict[str, List[tuple[int, int, str]]] = {}
    for position, name in enumerate(slice_names):
        match = _SLICE_SEQUENCE_PATTERN.match(str(name))
        if match is None:
            continue
        prefix = match.group(1)
        grouped.setdefault(prefix, []).append((int(match.group(2)), position, str(name)))

    sequences: List[tuple[int, int, List[str]]] = []
    for items in grouped.values():
        ordered = sorted(items, key=lambda item: (item[0], item[1]))
        current: List[tuple[int, int, str]] = []
        previous_number: Optional[int] = None
        for number, position, name in ordered:
            if current and previous_number is not None and number != previous_number + 1:
                if len(current) > 1:
                    sequences.append((len(current), min(entry[1] for entry in current), [entry[2] for entry in current]))
                current = []
            current.append((number, position, name))
            previous_number = number
        if len(current) > 1:
            sequences.append((len(current), min(entry[1] for entry in current), [entry[2] for entry in current]))

    sequences.sort(key=lambda item: (-item[0], item[1], item[2][0]))
    return [list(names) for _, _, names in sequences]


def detect_slice_groups(slice_names: List[str]) -> List[Dict[str, Any]]:
    grouped: Dict[str, List[tuple[int, int, str]]] = {}
    for position, name in enumerate(slice_names):
        match = _SLICE_SEQUENCE_PATTERN.match(str(name))
        if match is None:
            continue
        group_name = match.group(1).rstrip("_").strip()
        if not group_name:
            continue
        grouped.setdefault(group_name, []).append((int(match.group(2)), position, str(name)))

    groups: List[Dict[str, Any]] = []
    for group_name, items in grouped.items():
        ordered = sorted(items, key=lambda item: (item[0], item[1]))
        if len(ordered) < 2:
            continue
        slice_group = [item[2] for item in ordered]
        groups.append(
            {
                "group_name": group_name,
                "slice_names": slice_group,
                "count": len(slice_group),
            }
        )

    groups.sort(key=lambda item: (-int(item["count"]), str(item["group_name"])))
    return groups


def choose_default_slice_sequence(slice_names: List[str]) -> List[str]:
    sequences = detect_slice_sequences(slice_names)
    if sequences:
        return list(sequences[0])
    return [slice_names[0]] if slice_names else []


def get_default_state_name_for_group(group_name: str) -> str:
    clean_name = str(group_name or "").strip()
    return clean_name or "state"


def build_state_payload_from_slice_group(
    slice_names: List[str],
    *,
    preserve_fields: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    preserved = dict(preserve_fields or {})
    return {
        "frames": list(range(len(slice_names))),
        "slice_names": list(slice_names),
        "fps": float(preserved.get("fps", 8.0)),
        "loop": bool(preserved.get("loop", True)),
        "on_complete": preserved.get("on_complete"),
    }


def normalize_group_match_name(name: str) -> str:
    normalized = str(name or "").strip().lower()
    if not normalized:
        return ""
    return _TRAILING_STATE_NUMBER_PATTERN.sub("", normalized)


def get_recommended_slice_group(selected_state_name: str, groups: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    target = normalize_group_match_name(selected_state_name)
    if not target:
        return None
    for group in groups:
        if normalize_group_match_name(str(group.get("group_name", ""))) == target:
            return dict(group)
    return None


def can_refresh_from_recommended_group(context: Dict[str, Any], recommended_group: Optional[Dict[str, Any]]) -> bool:
    if not str(context.get("selected_state_name", "") or "").strip():
        return False
    if recommended_group is None:
        return False
    slice_names = list(recommended_group.get("slice_names", []))
    return bool(slice_names)


class AnimatorPanel:
    BG_COLOR = rl.Color(36, 36, 36, 255)
    CARD_COLOR = rl.Color(46, 46, 46, 255)
    BORDER_COLOR = rl.Color(25, 25, 25, 255)
    TEXT_COLOR = rl.Color(220, 220, 220, 255)
    DIM_COLOR = rl.Color(140, 140, 140, 255)
    ACCENT_COLOR = rl.Color(58, 121, 187, 255)
    MIN_FRAME_MS = 16
    MAX_FRAME_MS = 1000
    IMAGE_EXTENSIONS: tuple[str, ...] = (".png", ".jpg", ".jpeg", ".bmp")

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
        sprite_summary: Dict[str, Any] = {}
        if self._asset_service is not None and animator.sprite_sheet:
            entry = self._asset_service.get_asset_entry(sprite_sheet_locator)
            if entry is not None and hasattr(animator, "sync_sprite_sheet_reference"):
                animator.sync_sprite_sheet_reference(entry.get("reference", {}))
                sprite_sheet_locator = animator.get_sprite_sheet_reference()
            sprite_summary = self._asset_service.get_sprite_asset_summary(sprite_sheet_locator)
        slices = list(sprite_summary.get("slices", [])) if sprite_summary else []
        slice_names = [str(item.get("name", "")) for item in slices if item.get("name")]
        image_width, image_height = tuple(sprite_summary.get("image_size", (0, 0))) if sprite_summary else (0, 0)

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
            "sprite_sheet_summary": dict(sprite_summary),
            "sprite_sheet_pipeline_status": str(sprite_summary.get("pipeline_status", "") or ""),
            "sprite_sheet_pipeline_label": str(sprite_summary.get("pipeline_label", "") or ""),
            "sprite_sheet_has_metadata": bool(sprite_summary.get("has_metadata", False)),
            "sprite_sheet_slice_count": int(sprite_summary.get("slice_count", 0) or 0),
            "sprite_sheet_image_width": int(image_width),
            "sprite_sheet_image_height": int(image_height),
            "available_slices": slice_names,
            "has_slices": bool(slice_names),
            "sprite_sheet_ready": str(sprite_summary.get("pipeline_status", "") or "") == "ready",
        }

    def list_sprite_sheet_assets(self) -> List[Dict[str, Any]]:
        if self._asset_service is None:
            return []
        self._asset_service.refresh_catalog()
        assets = self._asset_service.list_assets(asset_kind="texture")
        if not assets:
            assets = self._asset_service.list_assets(extensions=list(self.IMAGE_EXTENSIONS))
        result: List[Dict[str, Any]] = []
        for asset in assets:
            summary = self._asset_service.get_sprite_asset_summary(asset["path"])
            image_width, image_height = tuple(summary.get("image_size", (0, 0)))
            item = dict(asset)
            item["has_slices"] = bool(summary.get("slice_count", 0))
            item["pipeline_status"] = str(summary.get("pipeline_status", "") or "")
            item["pipeline_label"] = str(summary.get("pipeline_label", "") or "")
            item["status_label"] = item["pipeline_label"] or item["pipeline_status"]
            item["slice_count"] = int(summary.get("slice_count", 0) or 0)
            item["image_size"] = (int(image_width), int(image_height))
            item["guid_short"] = str(summary.get("guid_short", asset.get("guid_short", "")) or "")
            item["has_metadata"] = bool(summary.get("has_metadata", False))
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
        default_sequence = choose_default_slice_sequence(available)
        animations[state_name] = {
            "frames": list(range(len(default_sequence))) if default_sequence else [0],
            "slice_names": default_sequence,
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

    def list_detected_slice_groups(self, world: Any) -> List[Dict[str, Any]]:
        context = self.get_selection_context(world)
        return self._detect_groups_from_context(context)

    def create_state_from_slice_group(self, world: Any, group_name: str) -> bool:
        context = self.get_selection_context(world)
        entity_name = context.get("entity_name", "")
        if not entity_name:
            return False
        payload = self._get_animator_payload(world, entity_name)
        if payload is None:
            return False
        group = self._find_slice_group(context, group_name)
        if group is None:
            return False

        animations = payload.setdefault("animations", {})
        base_name = get_default_state_name_for_group(str(group.get("group_name", "")))
        state_name = base_name
        suffix = 1
        while state_name in animations:
            state_name = f"{base_name}_{suffix}"
            suffix += 1

        animations[state_name] = build_state_payload_from_slice_group(list(group.get("slice_names", [])))
        if not payload.get("default_state"):
            payload["default_state"] = state_name
        if not payload.get("current_state"):
            payload["current_state"] = state_name
        success = self._replace_animator_payload(world, entity_name, payload)
        if success:
            self.selected_state_name = state_name
            self.selected_frame_index = 0
            self.preview_frame = 0
            self.preview_elapsed = 0.0
        return success

    def create_state_from_recommended_group(self, world: Any) -> bool:
        context = self.get_selection_context(world)
        recommended = self._get_recommended_group_from_context(context)
        if recommended is None:
            return False
        return self.create_state_from_slice_group(world, str(recommended.get("group_name", "")))

    def refresh_state_from_recommended_group(self, world: Any) -> bool:
        context = self.get_selection_context(world)
        recommended = self._get_recommended_group_from_context(context)
        if not can_refresh_from_recommended_group(context, recommended):
            return False
        return self.apply_slice_group_to_state(
            world,
            str(context.get("selected_state_name", "")),
            str(recommended.get("group_name", "")),
        )

    def apply_slice_group_to_state(self, world: Any, state_name: str, group_name: str) -> bool:
        context = self.get_selection_context(world)
        entity_name = context.get("entity_name", "")
        if not entity_name or not state_name:
            return False
        payload = self._get_animator_payload(world, entity_name)
        if payload is None:
            return False
        animations = payload.setdefault("animations", {})
        state = animations.get(state_name)
        if state is None:
            return False
        group = self._find_slice_group(context, group_name)
        if group is None:
            return False

        animations[state_name] = build_state_payload_from_slice_group(
            list(group.get("slice_names", [])),
            preserve_fields=state,
        )
        success = self._replace_animator_payload(world, entity_name, payload)
        if success:
            self.selected_state_name = state_name
            self.selected_frame_index = 0
            self.preview_frame = 0
            self.preview_elapsed = 0.0
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

    def duplicate_state(self, world: Any, state_name: str, new_name: Optional[str] = None) -> bool:
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

        base_name = new_name.strip() if new_name else f"{state_name}_copy"
        final_name = base_name
        suffix = 1
        while final_name in animations:
            final_name = f"{base_name}_{suffix}"
            suffix += 1

        animations[final_name] = copy.deepcopy(animations[state_name])
        success = self._replace_animator_payload(world, entity_name, payload)
        if success:
            self.selected_state_name = final_name
            self.selected_frame_index = 0
        return success

    def rename_state(self, world: Any, old_name: str, new_name: str) -> bool:
        context = self.get_selection_context(world)
        entity_name = context.get("entity_name", "")
        if not entity_name:
            return False
        if not old_name.strip() or not new_name.strip():
            return False
        if old_name == new_name:
            return True
        payload = self._get_animator_payload(world, entity_name)
        if payload is None:
            return False
        animations = payload.setdefault("animations", {})
        if old_name not in animations:
            return False
        if new_name in animations:
            return False

        animations[new_name] = animations.pop(old_name)
        if payload.get("default_state") == old_name:
            payload["default_state"] = new_name
        if payload.get("current_state") == old_name:
            payload["current_state"] = new_name
        for animation in animations.values():
            if animation.get("on_complete") == old_name:
                animation["on_complete"] = new_name

        success = self._replace_animator_payload(world, entity_name, payload)
        if success:
            self.selected_state_name = new_name
            self.selected_frame_index = 0
        return success

    def set_animator_flip(self, world: Any, flip_x: Optional[bool] = None, flip_y: Optional[bool] = None) -> bool:
        context = self.get_selection_context(world)
        entity_name = context.get("entity_name", "")
        if not entity_name:
            return False
        payload = self._get_animator_payload(world, entity_name)
        if payload is None:
            return False
        if flip_x is not None:
            payload["flip_x"] = bool(flip_x)
        if flip_y is not None:
            payload["flip_y"] = bool(flip_y)
        return self._replace_animator_payload(world, entity_name, payload)

    def set_animator_speed(self, world: Any, speed: float) -> bool:
        context = self.get_selection_context(world)
        entity_name = context.get("entity_name", "")
        if not entity_name:
            return False
        payload = self._get_animator_payload(world, entity_name)
        if payload is None:
            return False
        payload["speed"] = max(0.01, float(speed))
        return self._replace_animator_payload(world, entity_name, payload)

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
            status = context.get("status") or "unknown"
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
            summary = f"{asset['status_label']} | {asset.get('slice_count', 0)} slices"
            rl.draw_text(summary[:32], int(row_rect.x + 6), int(row_rect.y + 15), 9, self.DIM_COLOR)
            if hover and rl.is_mouse_button_pressed(rl.MOUSE_BUTTON_LEFT):
                self.set_sprite_sheet(world, asset["path"])
            current_y += 32

    def _draw_state_editor(self, world: Any, context: Dict[str, Any], rect: rl.Rectangle) -> None:
        current_y = self._draw_card(rect, "Frames")
        state_name = context.get("selected_state_name", "")
        state_data = context.get("selected_state_data")
        sprite_sheet = context.get("sprite_sheet", "")
        if not sprite_sheet:
            rl.draw_text("Choose an image from the project list.", int(rect.x + 10), int(current_y), 11, self.DIM_COLOR)
            return

        pipeline_label = str(context.get("sprite_sheet_pipeline_label", "") or "plain image")
        slice_count = int(context.get("sprite_sheet_slice_count", 0) or 0)
        image_width = int(context.get("sprite_sheet_image_width", 0) or 0)
        image_height = int(context.get("sprite_sheet_image_height", 0) or 0)
        rl.draw_text(f"Sheet: {sprite_sheet}", int(rect.x + 10), int(current_y), 10, self.DIM_COLOR)
        current_y += 18
        rl.draw_text(
            f"Pipeline: {pipeline_label} | Image: {image_width}x{image_height} | slices: {slice_count}",
            int(rect.x + 10),
            int(current_y),
            10,
            self.TEXT_COLOR,
        )
        current_y += 24

        if not context.get("has_slices", False):
            rl.draw_text("This sprite sheet is not ready for animation yet.", int(rect.x + 10), int(current_y), 11, self.DIM_COLOR)
            current_y += 24
            info_rect = rl.Rectangle(rect.x + 10, current_y, rect.width - 20, 22)
            rl.draw_rectangle_rec(info_rect, rl.Color(40, 40, 40, 255))
            rl.draw_text(pipeline_label, int(info_rect.x + 6), int(info_rect.y + 6), 10, self.DIM_COLOR)
            current_y += 28
            cta_rect = rl.Rectangle(rect.x + 10, current_y, rect.width - 20, 24)
            if rl.gui_button(cta_rect, "Open Sprite Editor"):
                self.request_open_sprite_editor_for = sprite_sheet
            return

        slice_groups = self._detect_groups_from_context(context)
        recommended_group = self._get_recommended_group_from_context(context)
        if slice_groups:
            rl.draw_text("Slice Groups", int(rect.x + 10), int(current_y), 11, self.TEXT_COLOR)
            current_y += 18
            if recommended_group is not None:
                recommended_rect = rl.Rectangle(rect.x + 10, current_y, rect.width - 20, 22)
                rl.draw_rectangle_rec(recommended_rect, rl.Color(44, 63, 88, 255))
                rl.draw_text(
                    f"Recommended: {recommended_group['group_name']}",
                    int(recommended_rect.x + 6),
                    int(recommended_rect.y + 6),
                    10,
                    self.TEXT_COLOR,
                )
                quick_rect = rl.Rectangle(recommended_rect.x + recommended_rect.width - 312, recommended_rect.y, 150, 22)
                if rl.gui_button(quick_rect, "New From Recommended"):
                    self.create_state_from_recommended_group(world)
                if can_refresh_from_recommended_group(context, recommended_group):
                    refresh_rect = rl.Rectangle(recommended_rect.x + recommended_rect.width - 156, recommended_rect.y, 150, 22)
                    if rl.gui_button(refresh_rect, "Refresh From Recommended"):
                        self.refresh_state_from_recommended_group(world)
                current_y += 26
            for group in slice_groups[:4]:
                group_name = str(group.get("group_name", ""))
                row_rect = rl.Rectangle(rect.x + 10, current_y, rect.width - 20, 22)
                is_recommended = recommended_group is not None and str(recommended_group.get("group_name", "")) == group_name
                row_color = rl.Color(52, 70, 96, 255) if is_recommended else rl.Color(40, 40, 40, 255)
                rl.draw_rectangle_rec(row_rect, row_color)
                rl.draw_text(
                    f"{group_name} ({int(group.get('count', 0))})",
                    int(row_rect.x + 6),
                    int(row_rect.y + 6),
                    10,
                    self.TEXT_COLOR,
                )
                if is_recommended:
                    rl.draw_text("Recommended", int(row_rect.x + 108), int(row_rect.y + 6), 9, self.TEXT_COLOR)
                new_rect = rl.Rectangle(row_rect.x + row_rect.width - 96, row_rect.y, 42, 22)
                apply_rect = rl.Rectangle(row_rect.x + row_rect.width - 48, row_rect.y, 42, 22)
                if rl.gui_button(new_rect, "New"):
                    self.create_state_from_slice_group(world, group_name)
                if state_name:
                    if rl.gui_button(apply_rect, "Apply"):
                        self.apply_slice_group_to_state(world, state_name, group_name)
                else:
                    rl.draw_rectangle_rec(apply_rect, rl.Color(32, 32, 32, 255))
                    rl.draw_text("Apply", int(apply_rect.x + 6), int(apply_rect.y + 6), 9, self.DIM_COLOR)
                current_y += 26
            current_y += 6

        if not state_name or state_data is None:
            rl.draw_text("Create or select a state.", int(rect.x + 10), int(current_y), 11, self.DIM_COLOR)
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

    def _detect_groups_from_context(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        return detect_slice_groups(list(context.get("available_slices", [])))

    def _find_slice_group(self, context: Dict[str, Any], group_name: str) -> Optional[Dict[str, Any]]:
        target = str(group_name or "").strip()
        if not target:
            return None
        for group in self._detect_groups_from_context(context):
            if str(group.get("group_name", "")) == target:
                return dict(group)
        return None

    def _get_recommended_group_from_context(self, context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        return get_recommended_slice_group(
            str(context.get("selected_state_name", "")),
            self._detect_groups_from_context(context),
        )

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
