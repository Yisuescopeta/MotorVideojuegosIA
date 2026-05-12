---
name: pyside6-panel-patterns
description: Use this skill when creating or redesigning PySide6 panels, tabs, inspectors, project browsers, hierarchy trees, console panels, agent panels, forms, and property editors in MotorVideojuegosIA.
---

# PySide6 panel patterns skill

## Mission

Build panels that feel like a real editor: consistent, testable, keyboard-aware,
and not held together by mystical `setGeometry()` rituals.

## Panel anatomy

Use a predictable structure:

```python
class InspectorPanel(QWidget):
    property_edit_requested = Signal(str, str, str, str, object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("InspectorPanel")
        self._entity_name = ""
        self._build_ui()
        self._connect_signals()

    def _build_ui(self) -> None:
        ...

    def _connect_signals(self) -> None:
        ...

    def set_entity(self, entity: dict[str, object] | None) -> None:
        ...
```

Keep constructors boring. Boring constructors are civilization.

## Layout rules

Recommended spacing:

- outer panel margin: 10 px
- dense inner group margin: 8 px
- row spacing: 6 px
- toolbar spacing: 4 px
- card radius in QSS: 10-16 px, depending on region
- tree row height: 24-28 px

Use:

- `QVBoxLayout` for panels
- `QHBoxLayout` for compact rows
- `QFormLayout` for property fields
- `QSplitter` for resizable editor regions
- `QTabWidget` for workspace modes
- `QToolButton` for compact icon actions
- `QAction` for actions reused between menu/toolbar

Avoid:

- absolute positioning
- hardcoded giant sizes outside viewport code
- random margins per widget
- inline styles
- mixing rendering, IO and engine calls in one widget

## Object names

Give semantic object names to styleable widgets:

```python
self.setObjectName("ProjectPanel")
header.setObjectName("PanelHeader")
title.setObjectName("PanelTitle")
toolbar.setObjectName("PanelToolbar")
search.setObjectName("SearchField")
```

Then use QSS selectors:

```css
#ProjectPanel #PanelTitle { ... }
QLineEdit#SearchField { ... }
```

## Signals

Signals should express user intent, not implementation detail.

Good:

```python
scene_open_requested = Signal(str)
asset_preview_requested = Signal(str)
component_add_requested = Signal(str, str)
```

Bad:

```python
buttonClicked = Signal()
thingHappened = Signal(object)
```

Use `@Slot` on connected methods where useful:

```python
@Slot()
def _on_add_clicked(self) -> None:
    ...
```

## Data input methods

Panels should have clear setter methods:

- `set_project_data(...)`
- `set_entity(...)`
- `set_assets(...)`
- `set_console_entries(...)`
- `set_agent_data(...)`

Do not make panels pull data from the engine. Panels are views, not raccoons
digging through the project dumpster.

## Inspector/property editors

Map values by type:

- `bool` -> `QCheckBox`
- `int` -> `QSpinBox`
- `float` -> `QDoubleSpinBox`
- enum-like string -> `QComboBox`
- plain string -> `QLineEdit`
- `dict`/`list` -> JSON editor or read-only summary with edit dialog

Commit policy:

- commit on Enter, focus-out, finished editing or explicit Apply
- do not commit on every `valueChanged`
- Escape restores the original value
- invalid input restores last valid value and logs an error
- after a successful commit, refresh from facade data

## Search/filter UX

For hierarchy, project and asset panels:

- add search field with placeholder
- filter case-insensitively
- preserve current selection when possible
- show empty state when no result matches
- do not destroy the underlying data just to filter the view

For larger lists, use model/view with `QSortFilterProxyModel`.

## Cards and asset grids

For the Frostline-style asset browser:

- use card-like cells with thumbnail, title and small type badge
- selected card gets cyan border/glow
- hover raises contrast subtly
- “Add Scene” card should use dashed border
- preserve grid/list toggle as UI state
- use lazy thumbnail loading if assets grow

## Context menus

Context menus should be grouped:

```text
Open
Rename
Duplicate
---
Create Child
Save as Prefab
---
Delete
```

Destructive actions should be visually separated and confirmed when irreversible.

## Keyboard support

Add common shortcuts where applicable:

- Delete: delete selected entity/asset only after confirmation if destructive
- F2: rename
- Ctrl+S: save
- Ctrl+Z / Ctrl+Y: undo/redo
- Ctrl+F: focus search
- F: frame selected in viewport
- Esc: cancel edit/drag/dialog

## Empty/loading/error states

Every panel should have intentional states:

- no project
- no scene
- no selection
- loading
- empty result
- error

Empty state text should tell the user what to do next, not just emotionally abandon them.

## Accessibility basics

- icon-only buttons need tooltips
- text contrast should meet WCAG AA where possible
- focus states should be visible
- disabled controls need a reason
- avoid state indicated only by color
- clickable target size should not be microscopic
