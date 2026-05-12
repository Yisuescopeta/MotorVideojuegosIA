# UI redesign checklist for MotorVideojuegosIA Qt editor

## Phase 1: Frostline theme foundation

- Add `frost_dark.qss`.
- Add `frost_light.qss`.
- Add theme loader that can choose one file.
- Add object names to major editor regions.
- Replace generic dark theme colors with Frostline tokens.
- Ensure active state is cyan/blue in both modes.
- Add focus states to inputs/buttons.
- Add hover/pressed/checked/disabled states.
- Make splitter handles discoverable.
- Use monospace font for console/terminal.
- Keep text contrast readable.

## Phase 2: Layout polish

- Create top bar groups matching mockup:
  - project selector
  - scene selector
  - transform tools
  - play controls
  - build/launch
- Add left rail navigation.
- Normalize all panel margins.
- Normalize panel header style.
- Add panel overflow menu area.
- Persist splitter sizes and active tabs as editor preference.

## Phase 3: Hierarchy and inspector

- Add hierarchy search.
- Add selected row cyan highlight.
- Add visibility icon column/state.
- Preserve tree expansion state after refresh.
- Use inspector sections with clean headers:
  - Transform
  - Sprite/Mesh
  - Materials
  - Light
  - Scripts
- Improve Add Component UX with searchable component picker.

## Phase 4: Project browser

- Add asset card grid.
- Add thumbnails for image/scene assets.
- Add selected asset border/glow.
- Add `Add Scene` dashed card.
- Add grid/list toggle.
- Add path breadcrumbs.

## Phase 5: Console

- Add pill filters: All, Log, Warning, Error.
- Color warnings amber and errors red.
- Show timestamps muted.
- Add command input row.
- Add clear action.

## Phase 6: Viewport

- Add floating viewport controls.
- Add zoom dropdown.
- Add reset camera.
- Add frame selected.
- Add selected entity outline.
- Add hover outline.
- Add asset drop ghost preview.
- Improve grid visibility in light/dark mode.

## Phase 7: Professionalization

- Move large lists to model/view if needed.
- Add QSignalSpy tests for panels.
- Add offscreen tests for theme loading.
- Add fake-facade tests for panel signal contracts.
- Keep no direct EngineAPI imports in panels.
