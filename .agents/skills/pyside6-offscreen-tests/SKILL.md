---
name: pyside6-offscreen-tests
description: Use this skill when adding or validating PySide6 editor tests, offscreen Qt tests, signal tests, widget behavior, dirty-state close behavior, gizmos, model/view tests, and UI regression checks in MotorVideojuegosIA.
---

# PySide6 offscreen tests skill

## Mission

Test the Qt editor without requiring a visible desktop.

Because “works on my monitor” is not a CI strategy, despite centuries of
developer folklore.

## Offscreen environment

Windows cmd:

```bat
set QT_QPA_PLATFORM=offscreen
py -m unittest tests.test_editor_qt_gizmo -v
```

PowerShell:

```powershell
$env:QT_QPA_PLATFORM="offscreen"
py -m unittest tests.test_editor_qt_gizmo -v
```

Linux/macOS:

```bash
QT_QPA_PLATFORM=offscreen py -m unittest tests.test_editor_qt_gizmo -v
```

## QApplication rule

Create one app instance:

```python
from PySide6.QtWidgets import QApplication

app = QApplication.instance()
if app is None:
    app = QApplication([])
```

Never create a new `QApplication` per test.

## Use QSignalSpy for signal behavior

For signal-based panels, use `QSignalSpy`:

```python
spy = QSignalSpy(panel.entity_selected)
panel.some_internal_click_or_emit()
assert spy.count() == 1
assert spy.at(0)[0] == "Player"
```

Verify that the signal exists and that payloads are correct.

## What to test

Good UI tests:

- panel emits intended signals
- signal payload values are correct
- commit-on-finish works
- Escape restores value
- invalid input does not commit
- disabled controls have expected state/tooltips
- facade fake receives expected method calls
- dirty close behavior: save/discard/cancel
- viewport coordinate conversion
- gizmo drag start/update/end
- model row counts and display data
- search/filter behavior
- QSS files exist and load

## What not to over-test

Avoid fragile tests for:

- exact pixel colors
- exact screenshot matching
- exact widget coordinates
- implementation-specific private layout nesting

Test behavior and contracts first. Pixel worship is how tests become glassware.

## Fake facades

For panel tests, prefer fake facades:

```python
class FakeFacade:
    def __init__(self) -> None:
        self.calls = []

    def create_entity(self, name: str) -> dict[str, object]:
        self.calls.append(("create_entity", name))
        return {"success": True, "message": "Created"}
```

Use real `EngineAPI` only for integration tests.

## Theme tests

Useful tests:

- `frost_dark.qss` exists
- `frost_light.qss` exists
- app can load each stylesheet
- required object-name selectors exist
- no obvious placeholder tokens remain
- theme switch does not alter scene data

## Commands to report honestly

Focused:

```bash
py -m unittest tests.test_editor_qt_gizmo -v
```

Broader:

```bash
py -m unittest discover -s tests
py -m ruff check engine cli tools main.py editor_qt
py -m mypy engine cli tools main.py editor_qt
```

Never claim success unless the command was actually run.
