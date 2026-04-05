# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec para MotorVideojuegosIA.

Uso:
    pyinstaller build/motorvideojuegos.spec --noconfirm

Genera: dist/MotorVideojuegosIA/ (carpeta con ejecutable y dependencias)

Para build de depuración (consola visible — útil cuando la ventana no aparece):
    SET MOTOR_DEBUG_CONSOLE=1 && pyinstaller build/motorvideojuegos.spec --noconfirm
    (o cambiar console=False → console=True en la sección EXE de abajo)
"""

import os
import sys
import site as _site_module
from PyInstaller.utils.hooks import collect_dynamic_libs, collect_all

block_cipher = None

# Raíz del proyecto (un nivel arriba de build/)
PROJECT_ROOT = os.path.abspath(os.path.join(SPECPATH, ".."))


def _find_real_pyray_site_packages():
    """Return the site-packages directory containing the REAL pyray (raylib-py).

    The project ships a local pyray/ stub shim at PROJECT_ROOT/pyray/__init__.py.
    If that shim ends up in pathex before the real site-packages directory,
    PyInstaller bundles the stub instead of the actual CFFI extension — raylib
    functions (init_window, begin_drawing, …) become no-ops and the window never
    opens.  This function locates the real package so we can insert it FIRST in
    pathex, shadowing the local shim during analysis.

    Detection heuristic: the real pyray does NOT import sitecustomize; our shim does.
    """
    local_shim = os.path.normcase(os.path.join(PROJECT_ROOT, "pyray"))
    candidates = []
    try:
        candidates += _site_module.getsitepackages()
    except Exception:
        pass
    try:
        candidates.append(_site_module.getusersitepackages())
    except Exception:
        pass
    for sp in candidates:
        pyray_dir = os.path.join(sp, "pyray")
        if not os.path.isdir(pyray_dir):
            continue
        if os.path.normcase(pyray_dir) == local_shim:
            continue
        init_py = os.path.join(pyray_dir, "__init__.py")
        if not os.path.isfile(init_py):
            continue
        try:
            with open(init_py, encoding="utf-8", errors="replace") as f:
                content = f.read()
            if "sitecustomize" not in content:
                return sp  # found real raylib-py, not our shim
        except Exception:
            continue
    return None


_real_pyray_sp = _find_real_pyray_site_packages()
if _real_pyray_sp is None:
    print(
        "\n"
        "WARNING: Real pyray (raylib-py) not found in site-packages.\n"
        "         The local stub shim will be bundled — the game window will NOT open.\n"
        "         Install: pip install raylib\n",
        file=sys.stderr,
    )

# Put real site-packages BEFORE project root so PyInstaller resolves pyray to the
# real raylib-py package, NOT our local PROJECT_ROOT/pyray/ stub shim.
_pathex = ([_real_pyray_sp] if _real_pyray_sp else []) + [PROJECT_ROOT]

# Temporarily expose real site-packages to collect_* hooks so they find real pyray.
if _real_pyray_sp and _real_pyray_sp not in sys.path:
    sys.path.insert(0, _real_pyray_sp)

# DLLs nativos de raylib
raylib_binaries = collect_dynamic_libs("raylib")

# Collect all Python modules and native binaries from the real pyray package.
try:
    _pyray_datas, _pyray_binaries, _pyray_hiddenimports = collect_all("pyray")
except Exception:
    _pyray_datas, _pyray_binaries, _pyray_hiddenimports = [], [], []

# Habilitar consola de depuración: SET MOTOR_DEBUG_CONSOLE=1 antes de invocar pyinstaller
_console = os.environ.get("MOTOR_DEBUG_CONSOLE", "").lower() in {"1", "true", "yes"}

a = Analysis(
    [os.path.join(PROJECT_ROOT, "main.py")],
    pathex=_pathex,
    binaries=raylib_binaries + _pyray_binaries,
    datas=[
        (os.path.join(PROJECT_ROOT, "assets"), "assets"),
        (os.path.join(PROJECT_ROOT, "levels"), "levels"),
        (os.path.join(PROJECT_ROOT, "prefabs"), "prefabs"),
        (os.path.join(PROJECT_ROOT, "scripts"), "scripts"),
        (os.path.join(PROJECT_ROOT, "settings"), "settings"),
        (os.path.join(PROJECT_ROOT, "project.json"), "."),
    ] + _pyray_datas,
    hiddenimports=[
        # raylib / pyray backend (explicit, in case static analysis misses them)
        "raylib",
        "pyray",
    ] + _pyray_hiddenimports + [
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
        # Local pyray stub shim — not needed when real pyray is bundled.
        # Including it would override the real backend and silently break rendering.
        "sitecustomize",
        # Dev-only tools: no incluir en la distribución
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
    # Release build: console=False (no terminal window).
    # Debug build:   SET MOTOR_DEBUG_CONSOLE=1 before running pyinstaller,
    #                or flip this to True to see startup errors.
    console=_console,
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
