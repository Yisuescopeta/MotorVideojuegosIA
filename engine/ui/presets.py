"""Pure UI preset definitions for serializable authoring flows."""

from __future__ import annotations

import copy
from typing import Any


def _rect(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "enabled": True,
        "anchor_min_x": 0.5,
        "anchor_min_y": 0.5,
        "anchor_max_x": 0.5,
        "anchor_max_y": 0.5,
        "pivot_x": 0.5,
        "pivot_y": 0.5,
        "anchored_x": 0.0,
        "anchored_y": 0.0,
        "width": 100.0,
        "height": 40.0,
        "rotation": 0.0,
        "scale_x": 1.0,
        "scale_y": 1.0,
        "layout_mode": "free",
        "layout_order": 0,
        "layout_ignore": False,
        "size_mode_x": "fixed",
        "size_mode_y": "fixed",
        "layout_align": "start",
        "padding_left": 0.0,
        "padding_top": 0.0,
        "padding_right": 0.0,
        "padding_bottom": 0.0,
        "spacing": 0.0,
    }
    payload.update(overrides)
    return payload


def _container(name: str, parent: str, rect_transform: dict[str, Any]) -> dict[str, Any]:
    return {
        "kind": "container",
        "name": name,
        "parent": parent,
        "rect_transform": rect_transform,
    }


def _text(
    name: str,
    parent: str,
    text: str,
    rect_transform: dict[str, Any],
    *,
    font_size: int,
    alignment: str = "center",
) -> dict[str, Any]:
    return {
        "kind": "text",
        "name": name,
        "parent": parent,
        "text": text,
        "font_size": font_size,
        "alignment": alignment,
        "rect_transform": rect_transform,
    }


def _button(
    name: str,
    parent: str,
    label: str,
    event_name: str,
    rect_transform: dict[str, Any],
) -> dict[str, Any]:
    return {
        "kind": "button",
        "name": name,
        "parent": parent,
        "label": label,
        "button_event_name": event_name,
        "rect_transform": rect_transform,
    }


_PRESET_DEFINITIONS: tuple[dict[str, Any], ...] = (
    {
        "id": "hud-platformer",
        "name": "HUD Platformer",
        "description": "HUD con score, lives, timer y boton de pausa.",
        "root_entity": "HUDPlatformerCanvas",
        "reference_width": 1280,
        "reference_height": 720,
        "sort_order": 30,
        "initial_active": True,
        "nodes": [
            _container(
                "HUDPlatformerTopBar",
                "HUDPlatformerCanvas",
                _rect(
                    anchor_min_x=0.0,
                    anchor_min_y=0.0,
                    anchor_max_x=1.0,
                    anchor_max_y=0.0,
                    pivot_x=0.0,
                    pivot_y=0.0,
                    anchored_x=0.0,
                    anchored_y=24.0,
                    width=0.0,
                    height=72.0,
                    layout_mode="horizontal_stack",
                    padding_left=24.0,
                    padding_top=12.0,
                    padding_right=24.0,
                    padding_bottom=12.0,
                    spacing=16.0,
                    layout_align="center",
                ),
            ),
            _text(
                "HUDPlatformerScoreText",
                "HUDPlatformerTopBar",
                "Score: 0000",
                _rect(width=220.0, height=48.0, layout_order=0),
                font_size=28,
                alignment="left",
            ),
            _text(
                "HUDPlatformerLivesText",
                "HUDPlatformerTopBar",
                "Lives: 3",
                _rect(width=180.0, height=48.0, layout_order=1),
                font_size=28,
                alignment="left",
            ),
            _text(
                "HUDPlatformerTimerText",
                "HUDPlatformerTopBar",
                "Time: 00:00",
                _rect(width=220.0, height=48.0, layout_order=2),
                font_size=28,
                alignment="left",
            ),
            _button(
                "HUDPlatformerPauseButton",
                "HUDPlatformerTopBar",
                "Pause",
                "ui.hud_platformer.pause",
                _rect(width=160.0, height=48.0, layout_order=3),
            ),
        ],
    },
    {
        "id": "main-menu",
        "name": "Main Menu",
        "description": "Menu principal con titulo y acciones Play, Options y Quit.",
        "root_entity": "MainMenuCanvas",
        "reference_width": 1280,
        "reference_height": 720,
        "sort_order": 40,
        "initial_active": True,
        "nodes": [
            _container(
                "MainMenuPanel",
                "MainMenuCanvas",
                _rect(
                    width=420.0,
                    height=360.0,
                    layout_mode="vertical_stack",
                    padding_left=32.0,
                    padding_top=32.0,
                    padding_right=32.0,
                    padding_bottom=32.0,
                    spacing=16.0,
                    layout_align="center",
                ),
            ),
            _text(
                "MainMenuTitle",
                "MainMenuPanel",
                "OpenGame",
                _rect(width=356.0, height=80.0, layout_order=0),
                font_size=56,
            ),
            _button(
                "MainMenuPlayButton",
                "MainMenuPanel",
                "Play",
                "ui.main_menu.play",
                _rect(width=356.0, height=56.0, layout_order=1),
            ),
            _button(
                "MainMenuOptionsButton",
                "MainMenuPanel",
                "Options",
                "ui.main_menu.options",
                _rect(width=356.0, height=56.0, layout_order=2),
            ),
            _button(
                "MainMenuQuitButton",
                "MainMenuPanel",
                "Quit",
                "ui.main_menu.quit",
                _rect(width=356.0, height=56.0, layout_order=3),
            ),
        ],
    },
    {
        "id": "pause-menu",
        "name": "Pause Menu",
        "description": "Overlay de pausa con acciones Resume, Restart y QuitToMenu.",
        "root_entity": "PauseMenuCanvas",
        "reference_width": 1280,
        "reference_height": 720,
        "sort_order": 60,
        "initial_active": False,
        "nodes": [
            _container(
                "PauseMenuPanel",
                "PauseMenuCanvas",
                _rect(
                    width=420.0,
                    height=340.0,
                    layout_mode="vertical_stack",
                    padding_left=32.0,
                    padding_top=32.0,
                    padding_right=32.0,
                    padding_bottom=32.0,
                    spacing=16.0,
                    layout_align="center",
                ),
            ),
            _text(
                "PauseMenuTitle",
                "PauseMenuPanel",
                "Paused",
                _rect(width=356.0, height=72.0, layout_order=0),
                font_size=52,
            ),
            _button(
                "PauseMenuResumeButton",
                "PauseMenuPanel",
                "Resume",
                "ui.pause_menu.resume",
                _rect(width=356.0, height=56.0, layout_order=1),
            ),
            _button(
                "PauseMenuRestartButton",
                "PauseMenuPanel",
                "Restart",
                "ui.pause_menu.restart",
                _rect(width=356.0, height=56.0, layout_order=2),
            ),
            _button(
                "PauseMenuQuitToMenuButton",
                "PauseMenuPanel",
                "Quit To Menu",
                "ui.pause_menu.quit_to_menu",
                _rect(width=356.0, height=56.0, layout_order=3),
            ),
        ],
    },
    {
        "id": "game-over",
        "name": "Game Over",
        "description": "Overlay de game over con Retry y QuitToMenu.",
        "root_entity": "GameOverCanvas",
        "reference_width": 1280,
        "reference_height": 720,
        "sort_order": 70,
        "initial_active": False,
        "nodes": [
            _container(
                "GameOverPanel",
                "GameOverCanvas",
                _rect(
                    width=420.0,
                    height=260.0,
                    layout_mode="vertical_stack",
                    padding_left=32.0,
                    padding_top=32.0,
                    padding_right=32.0,
                    padding_bottom=32.0,
                    spacing=16.0,
                    layout_align="center",
                ),
            ),
            _text(
                "GameOverTitle",
                "GameOverPanel",
                "Game Over",
                _rect(width=356.0, height=72.0, layout_order=0),
                font_size=52,
            ),
            _button(
                "GameOverRetryButton",
                "GameOverPanel",
                "Retry",
                "ui.game_over.retry",
                _rect(width=356.0, height=56.0, layout_order=1),
            ),
            _button(
                "GameOverQuitToMenuButton",
                "GameOverPanel",
                "Quit To Menu",
                "ui.game_over.quit_to_menu",
                _rect(width=356.0, height=56.0, layout_order=2),
            ),
        ],
    },
    {
        "id": "dialog-box",
        "name": "Dialog Box",
        "description": "Caja de dialogo inferior con speaker, body y continue.",
        "root_entity": "DialogBoxCanvas",
        "reference_width": 1280,
        "reference_height": 720,
        "sort_order": 50,
        "initial_active": False,
        "nodes": [
            _container(
                "DialogBoxPanel",
                "DialogBoxCanvas",
                _rect(
                    anchor_min_x=0.5,
                    anchor_min_y=1.0,
                    anchor_max_x=0.5,
                    anchor_max_y=1.0,
                    pivot_x=0.5,
                    pivot_y=1.0,
                    anchored_x=0.0,
                    anchored_y=-32.0,
                    width=1120.0,
                    height=220.0,
                    layout_mode="vertical_stack",
                    padding_left=32.0,
                    padding_top=24.0,
                    padding_right=32.0,
                    padding_bottom=24.0,
                    spacing=12.0,
                    layout_align="start",
                ),
            ),
            _text(
                "DialogBoxSpeakerText",
                "DialogBoxPanel",
                "Speaker",
                _rect(width=1056.0, height=36.0, layout_order=0),
                font_size=26,
                alignment="left",
            ),
            _text(
                "DialogBoxBodyText",
                "DialogBoxPanel",
                "Dialog body goes here.",
                _rect(width=1056.0, height=88.0, layout_order=1),
                font_size=24,
                alignment="left",
            ),
            _button(
                "DialogBoxContinueButton",
                "DialogBoxPanel",
                "Continue",
                "ui.dialog_box.continue",
                _rect(width=180.0, height=48.0, layout_order=2),
            ),
        ],
    },
)


def list_ui_preset_definitions() -> list[dict[str, Any]]:
    """Return deep-copied deterministic UI preset definitions."""
    return copy.deepcopy(list(_PRESET_DEFINITIONS))


def get_ui_preset_definition(preset_id: str) -> dict[str, Any] | None:
    """Return a deep-copied UI preset definition by id."""
    normalized = str(preset_id or "").strip().lower()
    for definition in _PRESET_DEFINITIONS:
        if definition["id"] == normalized:
            return copy.deepcopy(definition)
    return None
