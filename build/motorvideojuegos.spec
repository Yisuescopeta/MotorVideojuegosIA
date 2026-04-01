# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec para MotorVideojuegosIA.

Uso:
    pyinstaller build/motorvideojuegos.spec --noconfirm

Genera: dist/MotorVideojuegosIA/ (carpeta con ejecutable y dependencias)
"""

import os
import sys
from PyInstaller.utils.hooks import collect_dynamic_libs

block_cipher = None

# Raíz del proyecto (un nivel arriba de build/)
PROJECT_ROOT = os.path.abspath(os.path.join(SPECPATH, ".."))

# DLLs nativos de raylib
raylib_binaries = collect_dynamic_libs("raylib")

a = Analysis(
    [os.path.join(PROJECT_ROOT, "main.py")],
    pathex=[PROJECT_ROOT],
    binaries=raylib_binaries,
    datas=[
        (os.path.join(PROJECT_ROOT, "assets"), "assets"),
        (os.path.join(PROJECT_ROOT, "levels"), "levels"),
        (os.path.join(PROJECT_ROOT, "prefabs"), "prefabs"),
        (os.path.join(PROJECT_ROOT, "scripts"), "scripts"),
        (os.path.join(PROJECT_ROOT, "settings"), "settings"),
        (os.path.join(PROJECT_ROOT, "project.json"), "."),
    ],
    hiddenimports=[
        # Módulos del motor que se cargan dinámicamente
        "engine",
        "engine.config",
        "engine.core.game",
        "engine.core.engine_state",
        "engine.core.time_manager",
        "engine.core.hot_reload",
        "engine.ecs.entity",
        "engine.ecs.component",
        "engine.ecs.world",
        "engine.components.transform",
        "engine.components.sprite",
        "engine.components.collider",
        "engine.components.charactercontroller2d",
        "engine.components.joint2d",
        "engine.components.rigidbody",
        "engine.components.animator",
        "engine.components.camera2d",
        "engine.components.audiosource",
        "engine.components.inputmap",
        "engine.components.playercontroller2d",
        "engine.components.scriptbehaviour",
        "engine.components.tilemap",
        "engine.components.canvas",
        "engine.systems.render_system",
        "engine.systems.physics_system",
        "engine.systems.collision_system",
        "engine.systems.animation_system",
        "engine.systems.audio_system",
        "engine.systems.input_system",
        "engine.systems.player_controller_system",
        "engine.systems.character_controller_system",
        "engine.systems.script_behaviour_system",
        "engine.systems.selection_system",
        "engine.systems.ui_system",
        "engine.systems.ui_render_system",
        "engine.inspector.inspector_system",
        "engine.levels.level_loader",
        "engine.levels.component_registry",
        "engine.events.event_bus",
        "engine.events.rule_system",
        "engine.scenes.scene",
        "engine.scenes.scene_manager",
        "engine.resources.texture_manager",
        "engine.editor.editor_layout",
        "engine.editor.hierarchy_panel",
        "engine.editor.animator_panel",
        "engine.editor.sprite_editor_modal",
        "engine.editor.terminal_panel",
        "engine.editor.gizmo_system",
        "engine.editor.raygui_theme",
        "engine.editor.project_panel",
        "engine.editor.console_panel",
        "engine.editor.cursor_manager",
        "engine.editor.editor_tools",
        "engine.editor.undo_redo",
        "engine.project.project_service",
        "engine.physics.box2d_backend",
        "engine.update_checker",
        "engine.debug.profiler",
        "engine.debug.timeline",
        "cli.runner",
        "cli.headless_game",
        "cli.script_executor",
        "tools.engine_cli",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Dev-only: no incluir en la distribución
        "bandit",
        "mypy",
        "ruff",
        "pip_audit",
        "pytest",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="MotorVideojuegosIA",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # Sin ventana de consola
    disable_windowed_traceback=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="MotorVideojuegosIA",
)
