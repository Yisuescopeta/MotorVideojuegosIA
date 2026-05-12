---
name: pyside6-frostline-qss-design-system
description: Use this skill when improving the PySide6 editor visual design to match the supplied Frostline Engine references: glacial light/dark palette, QSS, theme tokens, panels, rounded cards, tabs, sidebars, toolbars, inspectors, asset browser, console, and viewport chrome.
---

# Frostline PySide6 QSS design system skill

## Mission

Make `MotorVideojuegosIA` look like the supplied Frostline-style editor mockups:
glacial, crisp, professional, blue-cyan accented, soft in light mode and deep
navy in dark mode. Not “random dark theme number 7”, humanity has suffered enough.

## Visual target from references

The mockups show:

- a top app bar with logo, project selector, scene selector and editor controls
- a left vertical rail with section icons
- a hierarchy panel with search and tree rows
- a central scene viewport with floating viewport controls
- a right inspector with segmented Entity/Component tabs
- bottom project browser with card thumbnails
- bottom console with pill filters
- large rounded panels
- subtle translucent/glass surfaces
- cyan/ice-blue active states
- mode parity: light and dark share the same layout, accents and hierarchy

## Theme architecture

Recommended files:

```text
editor_qt/theme/
  frost_tokens.py        # optional Python token map for runtime switching
  frost_light.qss
  frost_dark.qss
```

The app may load one QSS at startup, but the design should support both.

Use object names for semantic zones:

```text
#AppRoot
#TopBar
#SideRail
#HierarchyPanel
#ProjectPanel
#InspectorPanel
#ConsolePanel
#ViewportPanel
#ViewportOverlay
#PanelHeader
#PanelTitle
#PanelToolbar
#SearchField
#PrimaryAction
#DangerAction
#AssetCard
#AddCard
#SegmentedTabs
```

## Frostline light palette

Use this as the base palette for the light mode.

```css
/*
Frostline Light
bg_app:          #d8ecfb
bg_shell:        #eaf6ff
panel:           #f3faff
panel_alt:       #e6f3fd
panel_glass:     rgba(244, 251, 255, 0.78)
panel_raised:    #ffffff
border_soft:     #c8e0f2
border_strong:   #9dc8e9
text:            #17314d
text_soft:       #486581
text_muted:      #7a97ae
accent:          #35bdf6
accent_2:        #2f8cff
accent_deep:     #176fb7
accent_soft:     #d8f2ff
selection:       #bce8ff
warning:         #f7a928
danger:          #ef5b73
success:         #3dbf8f
shadow:          rgba(38, 94, 145, 0.18)
viewport_chrome: rgba(67, 137, 194, 0.42)
*/
```

## Frostline dark palette

Use this as the base palette for dark mode.

```css
/*
Frostline Dark
bg_app:          #04111c
bg_shell:        #071827
panel:           #0b2032
panel_alt:       #102b42
panel_glass:     rgba(9, 30, 48, 0.82)
panel_raised:    #112c44
border_soft:     #1d405d
border_strong:   #2c6b96
text:            #d9ecff
text_soft:       #a8c1d8
text_muted:      #6f8fa8
accent:          #32c7ff
accent_2:        #2f8cff
accent_deep:     #0c6cb3
accent_soft:     rgba(50, 199, 255, 0.16)
selection:       #0e4f7c
warning:         #ffb84d
danger:          #ff667d
success:         #4ed6a3
shadow:          rgba(0, 0, 0, 0.45)
viewport_chrome: rgba(5, 20, 34, 0.78)
*/
```

## Contrast rules

- Normal text should target at least 4.5:1 contrast against its background.
- Large text can target at least 3:1.
- Icons, focus rings, input borders and active UI components should be visibly distinguishable.
- Muted text is allowed, but not for critical labels or values.
- Disabled text may be lower contrast, but the control must still be recognizable.

Do not make ice-blue text on ice-blue panels and call it “subtle”. That is not subtle;
that is invisible with branding.

## QSS structure

Organize QSS by sections:

```css
/* 01. App + typography */
/* 02. Main bars */
/* 03. Panels */
/* 04. Buttons and tool buttons */
/* 05. Inputs */
/* 06. Trees and tables */
/* 07. Tabs */
/* 08. Splitters */
/* 09. Asset cards */
/* 10. Console */
/* 11. Scrollbars */
/* 12. State helpers */
```

## Global application styling

Prefer `QApplication.setStyleSheet(...)` for the loaded theme.

Base rule:

```css
QWidget {
    font-family: "Segoe UI", "Inter", "Arial", sans-serif;
    font-size: 12px;
    color: #d9ecff;
}
```

Avoid setting aggressive global backgrounds on every `QWidget` if child widgets
need transparency/glass effects. Use object names for main containers.

## Panels

Panel look:

```css
#HierarchyPanel,
#ProjectPanel,
#InspectorPanel,
#ConsolePanel {
    background: rgba(...);
    border: 1px solid ...;
    border-radius: 16px;
}
```

Panel headers:

- title left
- overflow menu right
- optional toolbar/search below
- 10-12 px padding

## Top bar

The top bar should feel like Frostline:

- logo + engine name left
- rounded combo boxes for project/scene
- central grouped tools
- play/pause/stop group
- build/launch group
- undo/redo/theme/account right

Use `QToolButton` or `QAction` groups and style checked state with cyan.

## Left rail

Left rail design:

- narrow vertical panel
- icon + label
- active item has cyan glow/left accent
- hover state uses translucent accent fill
- keep labels short: Hierarchy, Scenes, World, Lighting, Scripting, Audio, Settings

## Inputs

Search fields and combos:

```css
QLineEdit#SearchField,
QComboBox {
    border-radius: 8px;
    padding: 6px 10px;
}
```

Use placeholder text color for search.

## Trees

Hierarchy style:

- row height 24-28 px
- selected row gets cyan/blue fill
- hover row is subtle
- disclosure arrows should remain readable
- eye/visibility buttons should be muted until hover

Use tree indentation cleanly. The hierarchy is already mentally expensive.

## Tabs and segmented controls

The mockups use segmented tabs for `Entity / Component` and subtle top tabs for
`Scene / Game`.

For `QTabWidget`:

```css
QTabWidget::pane {
    border: 0;
}

QTabBar::tab {
    border-radius: 9px;
    padding: 6px 14px;
}

QTabBar::tab:selected {
    background: ...;
    color: ...;
}
```

## Buttons

Interactive states required:

- normal
- hover
- pressed
- checked
- disabled
- focus

For primary buttons:

- accent background
- white or near-white text
- visible focus outline
- not too saturated in light mode

For destructive buttons:

- danger border/text by default
- danger fill only on hover/pressed or confirmation action

## Asset cards

For the project browser:

- thumbnail with rounded top corners
- title footer overlay
- selected: cyan border and small glow
- hover: raise border contrast
- favorite/star badge optional
- add-card: dashed border with large plus

QSS cannot do everything card-like elegantly. If needed, use a custom delegate
or small card widget, but keep layout/data separate.

## Console

Console should be compact and scannable:

- pill filters: All, Log, Warning, Error
- warning icon/text amber
- error icon/text red
- timestamps muted
- right-side source labels muted
- input row at bottom with command placeholder

Avoid using the same color for every log type. Logs are already a swamp.

## Viewport chrome

The viewport itself is image/canvas-heavy. Keep QSS for the container and draw
viewport overlay controls with widgets or QPainter.

Viewport overlay controls should use `viewport_chrome`:

- semi-transparent dark/light pill backgrounds
- cyan active icons
- rounded controls
- small spacing
- avoid blocking the scene

## Shadows and translucency

Qt Style Sheets do not provide real CSS `box-shadow`.

Options:

- use subtle borders instead of fake shadows
- use `QGraphicsDropShadowEffect` sparingly on top-level panels/cards
- avoid applying shadow effects to hundreds of row widgets
- use translucent backgrounds where compositing is acceptable

## Theme switching

Recommended approach:

```python
def load_theme(app: QApplication, theme_name: str) -> None:
    theme_path = Path(__file__).resolve().parent / "theme" / f"{theme_name}.qss"
    app.setStyleSheet(theme_path.read_text(encoding="utf-8"))
```

Persist user theme preference outside scene data.

## QSS pitfalls

- QSS is not full CSS.
- Some CSS properties are unsupported.
- Subcontrols like `QComboBox::drop-down` and `QScrollBar::handle` need explicit styling.
- `QWidget { background: ... }` can accidentally paint every child.
- Widget-level `setStyleSheet` can override app style unexpectedly.
- If using style sheets and code-level font/background settings conflict, stylesheet wins.

## Professional acceptance checklist

- Light and dark modes use the same semantic tokens.
- Active state is always cyan/blue.
- Panel boundaries are visible but soft.
- Text contrast is readable.
- QSS has sections and comments.
- Object names are stable.
- Disabled controls explain why via tooltip.
- Hover/pressed/checked/focus states exist.
- There are no random inline styles in panel constructors.
- The viewport remains fast and readable.
