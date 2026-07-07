from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from engine.api import EngineAPI

from .cards import SUITS, asset_path_for, build_spanish_deck, card_entity_name
from .layout import CARD_HEIGHT, CARD_WIDTH, REFERENCE_HEIGHT, REFERENCE_WIDTH, foundation_rect, stock_rect, tableau_slot_rect, waste_rect

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKGROUND_ASSET_PATH = "assets/BackgroudWood/Backgroud1.png"
UI_PACK_ROOT = "assets/Complete_UI_Essential_Pack_Free/01_Flat_Theme/Sprites"
UI_TITLE_BANNER_ASSET = f"{UI_PACK_ROOT}/UI_Flat_Banner01a.png"
UI_TITLE_BANNER_HOVER_ASSET = f"{UI_PACK_ROOT}/UI_Flat_Banner02a.png"
UI_TITLE_BANNER_PRESSED_ASSET = f"{UI_PACK_ROOT}/UI_Flat_Banner03a.png"
UI_TITLE_BANNER_DISABLED_ASSET = f"{UI_PACK_ROOT}/UI_Flat_Banner04a.png"
UI_PANEL_ASSET = f"{UI_PACK_ROOT}/UI_Flat_Frame02a.png"
UI_VICTORY_PANEL_ASSET = f"{UI_PACK_ROOT}/UI_Flat_Frame03a.png"
UI_BAR_ASSET = f"{UI_PACK_ROOT}/UI_Flat_Bar01a.png"
UI_SLOT_BADGE_ASSET = f"{UI_PACK_ROOT}/UI_Flat_FrameSlot01a.png"

UI_ASSET_PATHS = (
    UI_TITLE_BANNER_ASSET,
    UI_TITLE_BANNER_HOVER_ASSET,
    UI_TITLE_BANNER_PRESSED_ASSET,
    UI_TITLE_BANNER_DISABLED_ASSET,
    UI_PANEL_ASSET,
    UI_VICTORY_PANEL_ASSET,
    UI_BAR_ASSET,
    UI_SLOT_BADGE_ASSET,
)


def build_scene(project_root: str | Path | None = None) -> Path:
    root = Path(project_root or PROJECT_ROOT).resolve()
    levels_dir = root / "levels"
    levels_dir.mkdir(parents=True, exist_ok=True)
    scene_path = levels_dir / "main_scene.json"
    scene_path.write_text(json.dumps(_empty_scene(), indent=4, ensure_ascii=True), encoding="utf-8")

    api = EngineAPI(project_root=root.as_posix())
    api.load_level(scene_path.as_posix())
    api.set_sorting_layers(["Board", "Cards", "UI"])
    _create_background(api)
    _create_slots(api)
    _create_cards(api)
    _create_director(api)
    _create_ui(api)
    api.save_scene(path=scene_path.as_posix())

    _write_runtime_config(root)
    _write_manifest(root)
    return scene_path


def _empty_scene() -> dict[str, Any]:
    return {
        "schema_version": 2,
        "name": "Solitario Espanol",
        "entities": [],
        "rules": [],
        "feature_metadata": {},
    }


def _rect_points() -> list[list[float]]:
    half_w = CARD_WIDTH / 2.0
    half_h = CARD_HEIGHT / 2.0
    return [[-half_w, -half_h], [half_w, -half_h], [half_w, half_h], [-half_w, half_h]]


def _create_background(api: EngineAPI) -> None:
    api.create_entity(
        "BoardBackground",
        {
            "Transform": {
                "enabled": True,
                "x": REFERENCE_WIDTH / 2.0,
                "y": REFERENCE_HEIGHT / 2.0,
                "rotation": 0.0,
                "scale_x": 1.0,
                "scale_y": 1.0,
            },
            "Sprite": {
                "enabled": True,
                "texture": {"guid": "", "path": BACKGROUND_ASSET_PATH},
                "texture_path": BACKGROUND_ASSET_PATH,
                "width": int(REFERENCE_WIDTH),
                "height": int(REFERENCE_HEIGHT),
                "origin_x": 0.5,
                "origin_y": 0.5,
                "flip_x": False,
                "flip_y": False,
                "tint": [255, 255, 255, 255],
                "source_slice": "",
            },
            "RenderOrder2D": {
                "enabled": True,
                "sorting_layer": "Default",
                "order_in_layer": -1000,
                "render_pass": "World",
            },
        },
        tag="Background",
        layer="Default",
    )


def _transform_from_rect(rect: Any) -> dict[str, Any]:
    x, y = rect.center
    return {"enabled": True, "x": x, "y": y, "rotation": 0.0, "scale_x": 1.0, "scale_y": 1.0}


def _slot_components(rect: Any, color: list[int], order: int) -> dict[str, Any]:
    return {
        "Transform": _transform_from_rect(rect),
        "Polygon2D": {
            "enabled": True,
            "points": _rect_points(),
            "color": color,
            "texture": {"guid": "", "path": ""},
            "texture_path": "",
            "offset_x": 0.0,
            "offset_y": 0.0,
        },
        "RenderOrder2D": {
            "enabled": True,
            "sorting_layer": "Board",
            "order_in_layer": order,
            "render_pass": "World",
        },
    }


def _create_slots(api: EngineAPI) -> None:
    api.create_entity("Slot_Stock", _slot_components(stock_rect(), [42, 98, 76, 180], 10), tag="Board", layer="Board")
    api.create_entity("Slot_Waste", _slot_components(waste_rect(), [42, 98, 76, 180], 11), tag="Board", layer="Board")
    for order, suit in enumerate(SUITS, start=20):
        api.create_entity(
            f"Slot_Foundation_{suit.value}",
            _slot_components(foundation_rect(suit), [56, 118, 88, 190], order),
            tag="Board",
            layer="Board",
        )
    for index in range(7):
        api.create_entity(
            f"Slot_Tableau_{index + 1}",
            _slot_components(tableau_slot_rect(index), [35, 68, 86, 160], 40 + index),
            tag="Board",
            layer="Board",
        )


def _create_cards(api: EngineAPI) -> None:
    for order, card in enumerate(build_spanish_deck()):
        texture = asset_path_for(card)
        api.create_entity(
            card_entity_name(card),
            {
                "Transform": {"enabled": True, "x": -400.0, "y": -400.0, "rotation": 0.0, "scale_x": 1.0, "scale_y": 1.0},
                "Sprite": {
                    "enabled": True,
                    "texture": {"guid": "", "path": texture},
                    "texture_path": texture,
                    "width": int(CARD_WIDTH),
                    "height": int(CARD_HEIGHT),
                    "origin_x": 0.5,
                    "origin_y": 0.5,
                    "flip_x": False,
                    "flip_y": False,
                    "tint": [255, 255, 255, 255],
                    "source_slice": "",
                },
                "Collider": {
                    "enabled": True,
                    "width": CARD_WIDTH,
                    "height": CARD_HEIGHT,
                    "offset_x": 0.0,
                    "offset_y": 0.0,
                    "is_trigger": True,
                    "shape_type": "box",
                    "radius": CARD_WIDTH / 2.0,
                    "points": [],
                    "friction": 0.2,
                    "restitution": 0.0,
                    "density": 1.0,
                },
                "RenderOrder2D": {
                    "enabled": True,
                    "sorting_layer": "Cards",
                    "order_in_layer": 1000 + order,
                    "render_pass": "World",
                },
            },
            tag="Card",
            layer="Cards",
        )


def _create_director(api: EngineAPI) -> None:
    api.create_entity(
        "SolitaireDirector",
        {
            "Transform": {"enabled": True, "x": 0.0, "y": 0.0, "rotation": 0.0, "scale_x": 1.0, "scale_y": 1.0},
            "ScriptBehaviour": {
                "enabled": True,
                "script": {"guid": "", "path": "scripts/solitario_espanol/controller.py"},
                "module_path": "solitario_espanol.controller",
                "run_in_edit_mode": False,
                "public_data": {"seed": ""},
            },
        },
        tag="Game",
        layer="Default",
    )


def _rect_transform(x: float, y: float, width: float, height: float) -> dict[str, Any]:
    return {
        "enabled": True,
        "anchor_min_x": 0.0,
        "anchor_min_y": 0.0,
        "anchor_max_x": 0.0,
        "anchor_max_y": 0.0,
        "pivot_x": 0.0,
        "pivot_y": 0.0,
        "anchored_x": x,
        "anchored_y": y,
        "width": width,
        "height": height,
        "rotation": 0.0,
        "scale_x": 1.0,
        "scale_y": 1.0,
    }


def _ui_text(text: str, size: int, color: list[int], alignment: str = "left", wrap: bool = False) -> dict[str, Any]:
    return {"enabled": True, "text": text, "font_size": size, "color": color, "alignment": alignment, "wrap": wrap}


def _ui_image(
    asset_path: str,
    x: float,
    y: float,
    width: float,
    height: float,
    *,
    tint: list[int] | None = None,
    enabled: bool = True,
) -> dict[str, Any]:
    return {
        "RectTransform": _rect_transform(x, y, width, height),
        "UIImage": {
            "enabled": enabled,
            "sprite": {"guid": "", "path": asset_path},
            "slice_name": "",
            "tint": tint or [255, 255, 255, 255],
            "preserve_aspect": True,
        },
    }


def _create_ui(api: EngineAPI) -> None:
    api.create_entity(
        "SolitaireCanvas",
        {
            "Canvas": {
                "enabled": True,
                "render_mode": "screen_space_overlay",
                "reference_width": REFERENCE_WIDTH,
                "reference_height": REFERENCE_HEIGHT,
                "match_mode": "stretch",
                "sort_order": 100,
            }
        },
        tag="UI",
        layer="UI",
    )
    ui_entities = [
        ("TitleBanner", _ui_image(UI_TITLE_BANNER_ASSET, 68, 14, 320, 100)),
        ("TitleText", {"RectTransform": _rect_transform(84, 36, 288, 34), "UIText": _ui_text("Solitario Espanol", 26, [35, 37, 41, 255], "center")}),
        ("TitleAccentBar", _ui_image(UI_BAR_ASSET, 86, 118, 160, 40, tint=[45, 58, 68, 255])),
        ("StockBadge", _ui_image(UI_SLOT_BADGE_ASSET, 72, 142, 36, 36)),
        ("StockBadgeText", {"RectTransform": _rect_transform(114, 142, 120, 24), "UIText": _ui_text("Mazo", 18, [244, 244, 236, 255], "left")}),
        ("WasteBadge", _ui_image(UI_SLOT_BADGE_ASSET, 184, 142, 36, 36)),
        ("WasteBadgeText", {"RectTransform": _rect_transform(226, 142, 140, 24), "UIText": _ui_text("Descarte", 18, [244, 244, 236, 255], "left")}),
        ("FoundationsBadge", _ui_image(UI_SLOT_BADGE_ASSET, 702, 142, 36, 36)),
        ("FoundationsBadgeText", {"RectTransform": _rect_transform(744, 142, 150, 24), "UIText": _ui_text("Bases", 18, [244, 244, 236, 255], "left")}),
        ("MovesPanel", _ui_image(UI_PANEL_ASSET, 922, 14, 240, 160, tint=[236, 238, 242, 255])),
        ("MovesText", {"RectTransform": _rect_transform(950, 44, 184, 54), "UIText": _ui_text("Movimientos: 0", 22, [34, 37, 43, 255], "center")}),
        (
            "RestartButton",
            {
                "RectTransform": _rect_transform(916, 188, 240, 75),
                "UIButton": {
                    "enabled": True,
                    "interactable": True,
                    "label": "Reiniciar",
                    "normal_color": [72, 86, 98, 255],
                    "hover_color": [84, 100, 112, 255],
                    "pressed_color": [56, 70, 80, 255],
                    "disabled_color": [48, 48, 48, 200],
                    "transition_scale_pressed": 0.96,
                    "on_click": {"type": "load_scene", "path": "levels/main_scene.json"},
                    "normal_sprite": {"guid": "", "path": UI_TITLE_BANNER_ASSET},
                    "hover_sprite": {"guid": "", "path": UI_TITLE_BANNER_HOVER_ASSET},
                    "pressed_sprite": {"guid": "", "path": UI_TITLE_BANNER_PRESSED_ASSET},
                    "disabled_sprite": {"guid": "", "path": UI_TITLE_BANNER_DISABLED_ASSET},
                    "normal_slice": "",
                    "hover_slice": "",
                    "pressed_slice": "",
                    "disabled_slice": "",
                    "image_tint": [255, 255, 255, 255],
                    "preserve_aspect": True,
                },
            },
        ),
        ("StatusPanel", _ui_image(UI_PANEL_ASSET, 922, 310, 324, 216, tint=[238, 233, 220, 255])),
        ("StatusText", {"RectTransform": _rect_transform(944, 336, 280, 168), "UIText": _ui_text("Seleccion: ninguna. R o Reiniciar.", 19, [34, 37, 43, 255], "left", True)}),
        ("VictoryPanel", _ui_image(UI_VICTORY_PANEL_ASSET, 400, 200, 480, 320, tint=[255, 248, 210, 245], enabled=False)),
        ("VictoryText", {"RectTransform": _rect_transform(438, 282, 404, 120), "UIText": _ui_text("", 34, [35, 37, 41, 255], "center")}),
    ]
    for name, payload in ui_entities:
        api.create_entity(name, payload, tag="UI", layer="UI")
        api.set_entity_parent(name, "SolitaireCanvas")


def _write_runtime_config(root: Path) -> None:
    payload = {
        "schema_version": 1,
        "entry_scene": "levels/main_scene.json",
        "project_name": "Solitario Espanol",
        "version": "0.1.0",
        "window": {"width": REFERENCE_WIDTH, "height": REFERENCE_HEIGHT},
    }
    (root / "runtime_config.json").write_text(json.dumps(payload, indent=4, ensure_ascii=True), encoding="utf-8")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _manifest_entry(root: Path, path: Path) -> dict[str, str]:
    return {"path": path.relative_to(root).as_posix(), "sha256": _sha256(path)}


def _write_manifest(root: Path) -> None:
    assets = sorted(
        list((root / "assets" / "spanish_deck").glob("*.PNG"))
        + [root / "assets" / "BackgroudWood" / "Backgroud1.png"]
        + [root / Path(path) for path in UI_ASSET_PATHS],
        key=lambda p: p.as_posix().lower(),
    )
    scripts = sorted((root / "scripts" / "solitario_espanol").glob("*.py"), key=lambda p: p.name.lower())
    scenes = [root / "levels" / "main_scene.json"]
    payload = {
        "schema_version": 1,
        "entry_scene": "levels/main_scene.json",
        "assets": [_manifest_entry(root, path) for path in assets],
        "scripts": [_manifest_entry(root, path) for path in scripts],
        "scenes": [_manifest_entry(root, path) for path in scenes],
    }
    (root / "game.manifest.json").write_text(json.dumps(payload, indent=4, ensure_ascii=True), encoding="utf-8")


if __name__ == "__main__":
    print(build_scene())
