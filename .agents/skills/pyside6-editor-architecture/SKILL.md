---
name: pyside6-editor-architecture
description: Use this skill when changing the PySide6 editor architecture in MotorVideojuegosIA, especially editor_qt, MainWindow, panels, EngineFacade usage, project launcher, menus, toolbar, layout, and integration with EngineAPI.
---

# PySide6 editor architecture skill

## Mission

Keep the Qt editor as a professional authoring UI, not a second engine bolted
onto the first one like a questionable weekend project.

## Hard repository invariants

- `Scene` is the persistent source of truth.
- `World` is an operational runtime projection.
- Qt widgets must not access `World`, `SceneManager`, runtime systems, or raw scene JSON directly.
- Qt panels must not import `EngineAPI`.
- The allowed authoring route is:

```text
Panel -> Qt Signal -> MainWindow slot -> EditorEngineFacade -> EngineAPI -> SceneManager/Scene
```

- `EditorEngineFacade` is the only entry point from Qt panels into the motor.
- UI-only state must stay UI-only:
  - selected tab
  - expanded foldouts
  - hover
  - camera pan/zoom
  - selected item highlight
  - panel splitter sizes
  - search/filter text
- Serializable scene mutations go through `EditorEngineFacade`.

## Read before touching editor code

- `docs/editor_qt.md`
- `docs/agents.md`
- `editor_qt/main_window.py`
- `editor_qt/bridge/engine_facade.py`
- the panel or widget being changed
- related tests

## MainWindow responsibility

`MainWindow` owns composition and routing:

- create panels
- build menus, toolbars, shell, splitters and tabs
- connect panel signals to slots
- call facade methods from slots
- refresh affected panels after successful mutation
- log results to console/status bar
- coordinate cross-panel effects

Keep `MainWindow` as a router/coordinator. If a slot gets large, extract a
private helper or a small service. Do not dump engine logic into the UI because
“it works locally”. That is how software grows mold.

## Panel responsibility

Panels should:

- render data passed into them
- expose user intent through typed Qt signals
- avoid project IO
- avoid direct engine calls
- avoid global state
- avoid long work in event handlers
- be testable with fake data/facades

Preferred panel skeleton:

```python
from __future__ import annotations

from PySide6.QtCore import Signal, Slot
from PySide6.QtWidgets import QVBoxLayout, QWidget

class ExamplePanel(QWidget):
    item_open_requested = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("ExamplePanel")
        self._build_ui()
        self._connect_signals()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

    def _connect_signals(self) -> None:
        ...

    def set_data(self, items: list[dict[str, object]]) -> None:
        ...

    @Slot()
    def _on_button_clicked(self) -> None:
        self.item_open_requested.emit("...")
```

## Signals and slots

Use PySide6 `Signal` declarations at class level and use `@Slot` for methods
connected to signals when practical.

Good:

```python
entity_selected = Signal(str)
property_edit_requested = Signal(str, str, str, str, object)
```

Avoid ambiguous events:

```python
changed = Signal()
clickedThing = Signal(object)
```

Qt signals are a communication boundary. Treat them like API, not confetti.

## Adding engine-facing behavior

When a panel needs a new capability:

1. Check whether `EngineAPI` already exposes the operation.
2. Add a narrow wrapper method to `EditorEngineFacade`.
3. Emit a signal from the panel.
4. Connect it in `MainWindow`.
5. Call the facade from the `MainWindow` slot.
6. Refresh dependent views only after success.
7. Update docs/tests if behavior becomes part of the editor contract.

## Menu/toolbar/action rules

Use `QAction` for actions shared between menu and toolbar.

- Set text.
- Set shortcut where useful.
- Set tooltip/status tip.
- Set enabled/disabled state from actual editor state.
- If disabled, the tooltip should explain why.

Do not create duplicate button logic when one `QAction` can serve both menu and toolbar.

## Refresh policy

Prefer targeted refresh:

- entity mutation -> hierarchy + inspector + viewport + status
- asset mutation -> project panel + viewport cache if needed
- scene mutation -> all scene-aware panels
- UI preference mutation -> style/theme/layout only

Avoid full-refreshing everything after every click unless the project is still
small and the behavior is explicitly transitional.

## Documentation policy

Update `docs/editor_qt.md` when:

- a panel gains a new public behavior
- a signal/facade route becomes part of editor architecture
- workflow changes
- theme files or layout persistence become official

## Review checklist

- No panel imports `EngineAPI`.
- No widget touches scene JSON manually.
- No UI code accesses runtime-only state as authoring state.
- Panel signals are typed and intention-revealing.
- UI-only state is not saved as scene data.
- QSS is centralized.
- Long operations do not block the UI thread.
- Tests/lint claims match commands actually run.
