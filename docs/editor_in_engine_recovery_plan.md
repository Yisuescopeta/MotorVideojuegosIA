---
schema_version: 1
doc_type: recovery_plan
status: ready
created: 2026-05-15
source: editor_in_engine_master_plan.md
purpose: Corregir todos los pendientes del master plan usando Queen agent
---

# Plan de recuperación: Editor in-engine

Este plan guía a Queen para completar los 24 items pendientes del
[editor_in_engine_master_plan.md](editor_in_engine_master_plan.md). Se ejecuta
en 6 batches secuenciales autónomos, cada uno como una invocación independiente
de Queen.

---

## Instrucciones para Queen

### Al iniciar

1. Leer `.motor/queen_state/recovery_state.json`.
2. Si `status == "done"` → reportar "Recovery plan ya completado" y detenerse.
3. Si `current_batch` tiene valor → ejecutar ese batch.
4. Si `current_batch` es `null` → ejecutar `BATCH_A`.

### Al completar un batch

1. Actualizar `recovery_state.json`: `status: "completed"` en el batch actual.
2. Avanzar `current_batch` al siguiente.
3. Hacer commit (vía committer) con mensaje descriptivo del batch.
4. Reportar al usuario: batch completado, archivos cambiados, tests.

### Si un batch falla o se bloquea

1. Actualizar `recovery_state.json`: `status: "failed"` en el batch.
2. No avanzar `current_batch`.
3. Reportar al usuario con causas para intervención manual.
4. El usuario puede corregir y re-invocar; Queen retoma el mismo batch.

### Invocaciones

El usuario invoca:
```
/queen ejecutar recovery plan del editor, batch actual segun .motor/queen_state/recovery_state.json
```

Queen lee el state, ejecuta el batch que toca, actualiza el state, y reporta.
El usuario vuelve a invocar para el siguiente batch. Así hasta `status: "done"`.

---

## Estado de tracking

Archivo: `.motor/queen_state/recovery_state.json`

```json
{
  "schema_version": 1,
  "plan": "docs/editor_in_engine_recovery_plan.md",
  "current_batch": "BATCH_A",
  "batches": {
    "BATCH_A": {"status": "pending", "items_total": 4, "items_done": 0},
    "BATCH_B": {"status": "pending", "items_total": 3, "items_done": 0},
    "BATCH_C": {"status": "pending", "items_total": 6, "items_done": 0},
    "BATCH_D": {"status": "pending", "items_total": 3, "items_done": 0},
    "BATCH_E": {"status": "pending", "items_total": 7, "items_done": 0},
    "BATCH_F": {"status": "pending", "items_total": 3, "items_done": 0}
  },
  "status": "in_progress",
  "last_updated": null,
  "queen_task_ids": []
}
```

Queen debe leer este archivo al inicio de cada invocación y escribirlo al
finalizar cada batch (delegando al builder).

---

## BATCH A: Theme System Completion (Fase 14) — 4 items

**Dependencia:** ninguna. Es fundación para polish visual.

### Items

| # | Item | Descripción |
|---|------|-------------|
| A1 | Directorio `engine/editor/theme/` | Crear directorio con `__init__.py`. Mover lógica de tema existente desde `engine/editor/ui_core/theme.py` manteniendo shim de compatibilidad. NO debe romper imports existentes. |
| A2 | Iconos multi-tamaño | Extender `engine/editor/ui/icons.py` para que `ICON_*` soporten `size` param (16, 24, 32, 64). Cada icono debe escalar su geometría proporcionalmente. |
| A3 | Font loading TTF | Crear `engine/editor/theme/fonts.py`. Cargar fuentes TTF desde `assets/fonts/` con sistema de fallback (si falla TTF, usar fuente por defecto de raylib). Exponer `load_font(name, size)` y `get_default_font()`. |
| A4 | Theme editor básico | Panel simple en editor para cambiar colores del tema activo en vivo. Usar `ThemeRegistry` existente. Mostrar grid de colores con nombre, preview y color picker básico (sliders RGB). Guardar cambios en `.motor/editor_state.json`. |

### Archivos involucrados

- `engine/editor/theme/__init__.py` (nuevo)
- `engine/editor/theme/fonts.py` (nuevo)
- `engine/editor/theme/theme_editor.py` (nuevo)
- `engine/editor/ui_core/theme.py` (mover contenido, dejar shim)
- `engine/editor/ui/icons.py` (extender con size param)
- `engine/editor/ui/__init__.py` (actualizar exports)
- `engine/editor/ui_core/__init__.py` (actualizar exports)

### Tests

- `tests/test_editor_theme_fonts.py` — carga TTF, fallback, cache
- `tests/test_editor_icons_multisize.py` — escalado de iconos en 4 tamaños
- `tests/test_editor_theme_editor.py` — cambio de colores en vivo, persistencia

### Definition of Done

- [ ] Directorio `engine/editor/theme/` existe con código funcional
- [ ] Shim en `ui_core/theme.py` no rompe imports existentes
- [ ] Iconos se dibujan correctamente en 16/24/32/64px (tests de geometría)
- [ ] `load_font()` carga TTF real si existe, fallback si no
- [ ] Theme editor permite cambiar colores y persiste en `editor_state.json`
- [ ] Tests pasan: `py -m unittest discover -s tests -p "test_editor_theme*" -p "test_editor_icons*"`
- [ ] `py main.py` sin errores de import
- [ ] Review approved, 0 must_fix

---

## BATCH B: Inspector Inline Editing (Fase 6) — 3 items

**Dependencia:** BATCH_A completado (usa sistema de temas e iconos).

### Items

| # | Item | Descripción |
|---|------|-------------|
| B1 | Edición inline COLOR | Widget color picker inline en `inspector_render.py`. Al hacer click en propiedad COLOR, mostrar popup con sliders R/G/B/A + preview. Commit via `commit_property()`. |
| B2 | Edición inline VECTOR2/VECTOR3 | Widget de edición inline para vectores. Mostrar campos X/Y (y Z para VECTOR3) editables con text input. Parseo y validación. Commit via `commit_property()`. |
| B3 | Propiedades anidadas y arrays | Soporte para DICT y LIST en el inspector. Mostrar keys/indices expandibles. Edición inline de valores hoja. No requiere edición de estructura (add/remove keys). |

### Archivos involucrados

- `engine/editor/ui/inspector_render.py` (añadir widgets inline)
- `engine/editor/ui/property_widgets.py` (extender con nested property descriptors)
- `engine/editor/ui/inspector.py` (extender `build_inspector_model_from_dict` para nested)

### Tests

- `tests/test_inspector_inline_editing.py` — color picker, vector editing, nested properties

### Definition of Done

- [ ] COLOR properties muestran preview + editor RGB(A)
- [ ] VECTOR2/VECTOR3 properties editables inline con validación
- [ ] DICT/LIST properties expandibles con valores hoja editables
- [ ] Wiring automático en EditorLayout (sin inyección manual de InspectorPanel)
- [ ] Tests pasan
- [ ] `py main.py` sin errores
- [ ] Review approved, 0 must_fix

---

## BATCH C: Controls Integration into Panels (Fase 13 + 15) — 6 items

**Dependencia:** BATCH_B completado (inspector ya usa controles inline).

### Items

| # | Item | Descripción |
|---|------|-------------|
| C1 | Integrar TextInput en Console | Reemplazar input de comandos del ConsolePanel por `TextInput` de `ui_core/controls/text_input.py` usando `process_text_input()` y `render_text_input()`. |
| C2 | Integrar Dropdown en filtros | Reemplazar dropdowns de filtro en Console y AssetBrowser por `DropdownModel`/`ComboBoxModel` + render shell. |
| C3 | Integrar ContextMenu | Añadir click derecho en Hierarchy (crear/borrar/duplicar), Inspector (reset property), AssetBrowser (delete/rename). Usar `ContextMenuModel` + render shell. |
| C4 | Integrar Popup en confirmaciones | Usar `PopupModel` para confirmaciones de delete, overwrite, etc. Reemplazar diálogos ad-hoc. |
| C5 | Migrar Console a retained-mode | Activar `console_panel` feature flag (`MOTOR_EDITOR_CONTROL_CONSOLE=1`) y verificar que `ConsolePanelEditorControlAdapter` funciona correctamente con el modelo `ConsoleControlModel`. |
| C6 | Selector de archivo | Implementar `FilePickerModel` en `ui_core/controls/` + render shell. Usarlo en "Open Scene", "Import Asset", "Export Theme". |

### Archivos involucrados

- `engine/editor/console_panel.py` (integrar TextInput, Dropdown)
- `engine/editor/asset_browser.py` (integrar Dropdown, ContextMenu)
- `engine/editor/editor_layout.py` (wiring de ContextMenu global)
- `engine/editor/ui_core/controls/file_picker.py` (nuevo)
- `engine/editor/ui/file_picker_render.py` (nuevo shell)
- `engine/editor/ui/context_menu_render.py` (extender para wiring)
- `engine/editor/editor_control_flags.py` (extender flags)

### Tests

- `tests/test_controls_integration.py` — TextInput en consola, Dropdown en filtros, ContextMenu wiring
- `tests/test_file_picker.py` — modelo + render + integración

### Definition of Done

- [ ] Console usa TextInput retained-mode para command input
- [ ] Filtros usan DropdownModel en Console y AssetBrowser
- [ ] Click derecho funcional en Hierarchy (crear/borrar/duplicar)
- [ ] Click derecho funcional en Inspector (reset property)
- [ ] Click derecho funcional en AssetBrowser (delete/rename)
- [ ] Confirmaciones usan PopupModel
- [ ] Console feature flag activado funciona sin regresiones
- [ ] FilePicker funcional para Open/Import/Export
- [ ] Tests pasan
- [ ] `py main.py` sin errores
- [ ] Review approved, 0 must_fix

---

## BATCH D: Docking Visual Completion (Fase 12) — 3 items

**Dependencia:** BATCH_C completado (paneles ya usan controles nuevos).

### Items

| # | Item | Descripción |
|---|------|-------------|
| D1 | Visual shell ventanas flotantes | Implementar render y hit-testing para `FloatingDockWindow`. El modelo ya existe en `ui_core/docking.py`. Añadir title bar con botones (close, dock), borde, sombra. Soporte para drag de ventana completa. |
| D2 | Auto-hide visual | Implementar colapso animado de paneles con `auto_hide=True`. El panel se reduce a un strip lateral con icono. Hover expande temporalmente. Click en pin fija expansión. |
| D3 | Drag GUI preview | Implementar preview visual durante drag de tabs. Mostrar rectángulo semitransparente + indicador de drop zone (highlight en área destino). Usar `begin_dock_tab_drag()` y `complete_dock_tab_drag()` del modelo. |

### Archivos involucrados

- `engine/editor/ui/dock_render.py` (nuevo — shells visuales para docking)
- `engine/editor/editor_layout.py` (wiring de floating + auto-hide + drag preview)
- `engine/editor/ui_core/docking.py` (sin cambios, modelo ya existe)
- `engine/editor/ui_core/dock_rects.py` (extender para floating window rects)

### Tests

- `tests/test_docking_visual.py` — floating render bounds, auto-hide state transitions, drag preview rects

### Definition of Done

- [ ] Floating windows se renderizan con title bar, borde, sombra
- [ ] Floating windows responden a drag, close, dock
- [ ] Auto-hide colapsa/expande paneles con animación
- [ ] Pin fija/libera panel en auto-hide
- [ ] Drag de tabs muestra preview semitransparente + drop zone highlight
- [ ] Tests pasan
- [ ] `py main.py` sin errores
- [ ] Review approved, 0 must_fix

---

## BATCH E: Visual Polish + Performance (Fase 17 + 18) — 7 items

**Dependencia:** BATCH_D completado (docking visual ya implementado).

### Items

| # | Item | Descripción |
|---|------|-------------|
| E1 | Animaciones suaves | Sistema de interpolación frame-a-frame para hover, focus, transiciones de panel. Usar `TimeManager._delta_time`. Aplicar a botones (color transition), paneles (expand/ collapse), tabs (switch). |
| E2 | Modo claro verificado | Activar `UNITY_LIGHT` y verificar visualmente + tests que todos los widgets responden al tema claro. Corregir hardcodeos de color que asuman tema oscuro. |
| E3 | Fuente monoespaciada | Cargar fuente monoespaciada (TTF o fallback) para Console panel y code inputs. Usar sistema de BATCH_A3. |
| E4 | Virtual scroll | Implementar virtualización de filas en Hierarchy y AssetBrowser. Solo renderizar filas visibles en viewport. Reciclar pool de widgets. Umbral de activación: > 100 entradas. |
| E5 | Widget cache | Sistema de caché para widgets retained-mode. No recrear `measure()`/`arrange()` si no hubo cambios (`dirty` flag). Invalidar caché en `set_text()`, `add_child()`, `remove_child()`. |
| E6 | Dirty flags | Añadir `_dirty` flag a paneles. Solo re-renderizar panel si hubo cambio de estado, input, o el layout cambió. Reducir draw calls innecesarios. |
| E7 | Panel profiling | Instrumentar `draw_layout()` con `time.perf_counter()` alrededor de cada `panel.render()`. Exponer métricas via `EngineAPI.get_debug_profile()` con breakdown por panel. |

### Archivos involucrados

- `engine/editor/ui/animation.py` (nuevo — sistema de interpolación)
- `engine/editor/ui/theme.py` (verificar/corregir modo claro)
- `engine/editor/theme/fonts.py` (extender con mono font)
- `engine/editor/ui/virtual_scroll.py` (nuevo)
- `engine/editor/ui_core/controls/control.py` (añadir dirty/cache)
- `engine/editor/editor_layout.py` (dirty flags, profiling)
- `engine/editor/console_panel.py` (mono font)
- `engine/editor/hierarchy_panel.py` (virtual scroll)
- `engine/editor/asset_browser.py` (virtual scroll)

### Tests

- `tests/test_editor_animations.py` — interpolación, transiciones
- `tests/test_editor_light_theme.py` — modo claro en todos los widgets
- `tests/test_editor_mono_font.py` — carga y uso en consola
- `tests/test_editor_virtual_scroll.py` — virtualización, reciclaje
- `tests/test_editor_widget_cache.py` — dirty flags, caché
- `tests/test_editor_panel_profiling.py` — métricas por panel

### Definition of Done

- [ ] Hover/focus/transiciones usan interpolación suave
- [ ] `UNITY_LIGHT` se ve correcto en todos los widgets (test automatizado)
- [ ] Console usa fuente monoespaciada
- [ ] Hierarchy con > 100 entradas solo renderiza filas visibles
- [ ] AssetBrowser con > 100 assets solo renderiza filas visibles
- [ ] Widgets no se re-miden si no hay cambios
- [ ] Paneles no se re-renderizan si dirty flag es false
- [ ] `EngineAPI.get_debug_profile()` incluye breakdown por panel
- [ ] Tests pasan
- [ ] `py main.py` sin errores
- [ ] Review approved, 0 must_fix

---

## BATCH F: Plan Structure Fixes — 3 items

**Dependencia:** BATCH_E completado (todos los features implementados).

### Items

| # | Item | Descripción |
|---|------|-------------|
| F1 | Milestones 2 y 3 | Añadir al master plan: Milestone 2 (fases 10-16, UI interna Godot) y Milestone 3 (fases 17-20, polish + cutover). |
| F2 | Deuda técnica consolidada | Añadir sección "Deuda técnica" al master plan agrupando todos los items que quedaron diferidos + su estado actual (completado por recovery plan). |
| F3 | Corregir frontmatter | Cambiar `status: completed` → `status: completed` (ya es correcto tras recovery). Actualizar `updated`, `completed`, `queen_updated`. Añadir referencia al recovery plan. |

### Archivos involucrados

- `docs/editor_in_engine_master_plan.md` (actualizar frontmatter, milestones, deuda)
- `docs/editor_in_engine_recovery_plan.md` (marcar como completado)

### Definition of Done

- [ ] Milestone 2 documentado con fases 10-16 y entregables
- [ ] Milestone 3 documentado con fases 17-20 y entregables
- [ ] Sección "Deuda técnica" existe con items diferidos y su resolución
- [ ] Frontmatter del master plan actualizado y consistente
- [ ] `recovery_state.json` → `status: "done"`
- [ ] Review approved, 0 must_fix
- [ ] Commit final del recovery plan

---

## Checks globales (ejecutar tras cada batch)

```bash
py -m unittest discover -s tests -v
py -m ruff check engine cli tools main.py
py -m motor doctor --project . --json
```

Si `ruff` o `mypy` reportan issues nuevos (no preexistentes), el builder debe
corregirlos antes de declarar el batch completado.

---

## Verificación final (tras BATCH_F)

1. `py -m unittest discover -s tests` — todos los tests pasan (salvo 4 tilemap isolation ya documentados)
2. `py -m ruff check engine cli tools main.py` — sin issues nuevos
3. `py -m motor doctor --project . --json` — healthy
4. `py main.py` — sin errores de sintaxis/import
5. `docs/editor_in_engine_master_plan.md` — frontmatter, milestones y deuda actualizados
6. `.motor/queen_state/recovery_state.json` — `status: "done"`, todos los batches `completed`

---

## Archivos relacionados

- `docs/editor_in_engine_master_plan.md` — plan original, fuente de verdad de los pendientes
- `docs/editor_ui_architecture.md` — separación Editor UI vs Runtime UI
- `.opencode/agents/queen.md` — configuración de Queen (sin límite de ciclos)
- `.motor/queen_state/recovery_state.json` — tracking de progreso
