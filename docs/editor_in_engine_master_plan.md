---
schema_version: 1
doc_type: editor_plan
status: active_plan
created: 2026-05-13
updated: 2026-05-14
queen_updated: queen-20260514-001
queen_task_id: queen-20260514-001
phase_scope: all
implemented_capability: false
---

# Plan maestro: Editor profesional in-engine estilo Godot

- **Estado:** plan de ejecución por fases
- **Fuente:** solicitud de usuario del 2026-05-13
- **Regla operativa:** antes de pasar a la fase siguiente, ejecutar code-review y corregir hasta cero `must_fix`.

---

## Reglas del plan

1. **No romper `py main.py`.** Cada fase debe validar que la aplicación principal sigue ejecutándose sin errores.
2. **Play/Pause/Stop siempre funcional.** Los controles de reproducción del editor no deben degradarse en ninguna fase.
3. **No migrar todo a PySide6.** El editor debe mantenerse basado en raygui / rendering propio; no se adopta PySide6 como reemplazo general.
4. **Mantener Scene como verdad persistente y World como proyección operativa.** Las mutaciones runtime no deben convertirse en authoring state accidental.
5. **Ediciones serializables via SceneManager o EngineAPI.** No introducir rutas de edición directa alrededor de los flujos compartidos de authoring.
6. **Runtime UI y Editor UI separados.** Pueden compartir helpers (dibujo, geometría, tokens), nunca persistencia ni estado de authoring.
7. **Usar Godot local como inspiración, no copiar código.** Estudiar la estructura del editor de Godot, adaptar conceptos al modelo serializable y a la arquitectura del motor.
8. **Ciclo de fase:** `RECON -> PLAN -> IMPLEMENTAR -> VALIDAR -> DOCUMENTAR -> CODE REVIEW -> corregir hasta approved/cero must_fix -> avanzar`.

---

## Decisión técnica fundamental

**Primero editor mejor, luego UI interna tipo Godot.**

Esto significa que las fases iniciales (0–9) se enfocan en construir un editor funcional, profesional y utilizable sobre la infraestructura actual. Las fases 10–20 reorganizan esa infraestructura hacia un sistema de UI interna que se parezca más a la arquitectura de Godot (controles retained-mode, theme system, docking), sin romper lo construido antes.

---

## Fases

### Fase 0 — Baseline y reconocimiento

Documentar la línea base del editor actual:
- Crear `docs/editor_in_engine_baseline.md` con el estado actual del editor, archivos principales, limitaciones conocidas.
- Crear `docs/editor_in_engine_godot_reference_notes.md` con notas de referencia del editor de Godot local (estructura de SceneTree, docking, inspector, theme).
- Revisar el código del editor actual e identificar archivos principales.
- Revisar la instalación local de Godot como referencia visual y estructural.
- Validar que `py -m unittest discover -s tests` pase sin errores.
- Validar que `py main.py` ejecute sin errores.

**Entregables:** `docs/editor_in_engine_baseline.md`, `docs/editor_in_engine_godot_reference_notes.md`, reporte de validación de tests y `main.py`.

---

### Fase 1 — Sistema de diseño del editor

Crear la base del sistema de UI del editor en `engine/editor/ui/`:
- Sistema de tokens de diseño: colores, geometría, espaciado, tipografía.
- Motor de dibujo (draw) primitivo para UI del editor (rectángulos, bordes, textos, iconos simples).
- Sistema de temas (theme) mínimos que consuma tokens.
- Hacer que `raygui_theme` use los tokens del sistema de diseño (no colores hardcodeados).
- Validar que se pueda dibujar un canvas UI básico (fondo, rectángulos de ejemplo).
- Validar `py main.py` sin regresión.

**Entregables:** `engine/editor/ui/tokens.py`, `engine/editor/ui/colors.py`, `engine/editor/ui/geometry.py`, `engine/editor/ui/theme.py`, `engine/editor/ui/draw.py`, raygui integrado con tokens.

---

### Fase 2 — Toolkit UI inmediato

Construir el toolkit base para la UI del editor en `engine/editor/ui/`:
- `input.py`: helpers de entrada (mouse, teclado, foco).
- `widgets.py`: widgets básicos (label, button, checkbox, slider, text input simple).
- `widget_state.py`: máquina de estado para widgets (idle, hover, active, disabled, focus).
- `icons.py`: sistema de iconos (cargar desde archivos o dibujar primitivos).
- `WidgetResult`: tipo de retorno unificado para widgets (redraw, consume_input, action).
- Tests de geometría y widget_state.
- Validar `py main.py`.

**Entregables:** `engine/editor/ui/input.py`, `engine/editor/ui/widgets.py`, `engine/editor/ui/widget_state.py`, `engine/editor/ui/icons.py`, tests unitarios.

---

### Fase 3 — Top bar, menús y toolbar

Rediseñar la barra superior del editor:
- Mantener flags `EditorShellState` (modo edición/reproducción).
- Mantener botones Play/Pause/Stop siempre funcionales.
- Agregar menús desplegables (File, Edit, View, Help).
- Toolbar con acciones comunes.
- Separar lógica de menús de la lógica del editor principal.

**Entregables:** Top bar rediseñada, menús funcionales, toolbar, validación de Play/Pause/Stop.

---

### Fase 4 — Panel framework v1

Crear sistema de paneles acoplables:
- `panels.py`: contenedor base para paneles del editor.
- `scroll.py`: soporte de scroll para paneles con contenido extenso.
- Headers de panel con título e icono.
- Área de contenido por panel.
- Splitters para redimensionar paneles.
- Diseño flexible (no docking completo aún, solo paneles fijos con splitter).

**Entregables:** `engine/editor/ui/panels.py`, `engine/editor/ui/scroll.py`, paneles básicos funcionales.

---

### Fase 5 — Hierarchy profesional

Construir el panel de jerarquía (árbol de escena):
- `tree_view.py`: control de árbol profesional.
- Soporte de selección simple y múltiple.
- Crear, borrar, duplicar entradas desde el árbol.
- Búsqueda/filtro en la jerarquía.
- Scroll en lista larga.
- Expandir/colapsar nodos padre.
- Iconos por tipo de nodo.
- **No mutar el árbol directo:** toda creación/borrado/duplicado debe pasar por SceneManager o EngineAPI.

**Entregables:** `engine/editor/ui/tree_view.py`, panel Hierarchy funcional.

---

### Fase 6 — Inspector profesional v1

Construir el panel de inspector de propiedades:
- Widgets de propiedades: bool, int, float, str, color, vector2, vector3, dict, list, asset picker.
- `inspector.py` y `property_widgets.py`.
- Commit seguro de cambios (solo guardar cuando el usuario confirma o al perder foco).
- Edición vía rutas existentes de authoring (SceneManager / EngineAPI).
- Soporte para propiedades anidadas y arrays.

**Estado real (2026-05-14, foundation + panel v1 opcional):**
- ✅ `engine/editor/ui/property_widgets.py` — creado: PropertyKind, PropertyDescriptor, EditTransaction, CommitContract, PropertyEditResult. Pure data model, sin render.
- ✅ `engine/editor/ui/inspector.py` — creado: InspectorGroup, InspectorModel, build_inspector_model_from_dict, infer_property_kind. Pure data model/builders, sin render.
- ✅ `engine/editor/ui/inspector_render.py` — creado: `InspectorPanel` editor-only con pyray. Renderiza grupos/propiedades del inspector. Soporta edición inline: bool toggle, text edit para INT/FLOAT/STR con commit/cancel. Display read-only para COLOR, VECTOR2, VECTOR3, DICT, LIST.
- ✅ Commit via SceneManager/EngineAPI: `commit_property()` delega en `SceneManager.update_entity_property` o `apply_edit_to_world`. Sin SceneManager → no-op con `last_error`.
- ✅ Text editing: `begin_text_edit()`, `set_text_buffer()`, `commit_text_edit()` con parseo de tipo, `handle_key()` (ENTER commit, ESC cancel).
- ✅ Wiring opcional en `Game.set_inspector_panel()`: cuando se inyecta un `InspectorPanel`, toma prioridad sobre `InspectorSystem` legacy en el render loop. `None` restaura fallback legacy.
- ✅ Export público via `engine/editor/ui/__init__.py`: `InspectorPanel`, `InspectorWidgetRect`.
- ✅ Tests: `tests/test_inspector_render.py` — 8 tests: build_model con world object y dict, no_selection no-op, bool_commit invoca SceneManager, text_edit_commit invoca SceneManager e invalid numeric no commit, escape cancels, no_SceneManager_no_mutate, render_layout_bounds, game_setter.
- ❌ Legacy `InspectorSystem` sigue siendo el render por defecto/fallback. `InspectorPanel` es opt-in vía `Game.set_inspector_panel()`.
- ❌ Edición inline para COLOR, VECTOR2, VECTOR3, DICT, LIST — solo display read-only, sin widget interactivo.
- ❌ Soporte para propiedades anidadas y arrays — no implementado.
- ❌ Sin wiring automático en EditorLayout — el panel debe inyectarse explícitamente desde fuera.

**Entregables plan original:** `engine/editor/ui/inspector.py`, `engine/editor/ui/property_widgets.py`, panel Inspector funcional.
**Entregables entregados:** `engine/editor/ui/inspector.py` (foundation), `engine/editor/ui/property_widgets.py` (foundation), `engine/editor/ui/inspector_render.py` (panel v1 opcional con SceneManager/EngineAPI wiring). Legacy `InspectorSystem` preservado como fallback.

---

### Fase 7 — Project / Asset browser

Construir el navegador de proyectos y assets:
- Vista grid y lista.
- Tarjetas (cards) con icono, nombre, tipo.
- Breadcrumbs de navegación.
- Filtros por tipo de asset.
- Integración con `AssetService` existente.
- Doble-click para abrir asset en inspector o editor correspondiente.

**Estado real (2026-05-13, Fase 7 risk corrected):**
- ✅ Vista grid — existente, refactorizada a `_render_content_grid()`.
- ✅ Vista lista — NUEVA: `_render_content_list()`, toggle grid/list en toolbar.
- ✅ Breadcrumbs de navegación — existentes.
- ✅ Filtros por tipo de asset — existentes.
- ✅ Integración con `AssetService` — existente.
- ✅ Doble-click en imagen → abre sprite editor (`request_open_sprite_editor_for`).
- ✅ Doble-click en escena (`levels/`) → abre escena (`request_open_scene_for`).
- ✅ Doble-click en otros tipos (scripts, prefabs, audio, material, unknown) → `_reveal_asset_in_panel()`: navega a directorio padre, resetea filtro si oculta el asset, selecciona el archivo. Sin ejecución de script, sin shell, sin `game.py`.
- ✅ Inferencia de `asset_kind` desde extensión cuando metadata catalogo es `"unknown"` — scripts, audio, material, prefab, scene_data se categorizan automáticamente.
- ✅ `ThumbnailProvider`: iconos tipados por tipo (folder, image, scene, prefab, script, audio, material, unknown) con colores y decoraciones distintivas (círculos, barras, bordes). Cuando `rl.is_window_ready()` es true y `rl.load_texture` funciona, carga la imagen real escalada al icono. Sin ventana Raylib o si falla carga, fallback automático al icono tipado.
- ✅ Limpieza de caché de thumbnails al cambiar de proyecto (`set_project_service`).
- ❌ Drag & drop desde asset browser a viewport/inspector — no implementado.
- ❌ Vista de tarjetas (cards) con preview grande — no implementado.

**Entregables plan original:** Panel AssetBrowser funcional con vista grid/lista.
**Entregables entregados:** Vista grid/lista funcional, doble-click para image/scene + reveal seguro para otros tipos, toggle view mode, ThumbnailProvider con thumbnails reales (contexto ventana) + fallback iconos tipados, inferencia de asset_kind desde extensión. Pendiente: drag & drop, vista de tarjetas.

---

### Fase 8 — Console / Logs / Terminal feedback

Construir el panel de consola y feedback:
- Salida de logs con niveles (info, warn, error, debug).
- Filtros por nivel y búsqueda.
- Badges de conteo por nivel.
- Command input para ejecutar comandos de consola (ej. `help`, `clear`, scripts).
- Notificaciones del sistema (toast, notificaciones de error breve).
- Seguridad: sanitizar input de comandos, no exponer APIs internas peligrosas.

**Estado real (2026-05-13, completado):**
- ✅ Nivel DEBUG — `log_debug()`, toggle button en toolbar, icono `(#)` y color SKYBLUE.
- ✅ Filtros por nivel — checkboxes INFO/WARN/ERROR/DEBUG. Search text input con filtro case-insensitive sobre mensaje y nivel.
- ✅ Badges de conteo — barra de herramientas muestra `I:N W:N E:N D:N` en tiempo real.
- ✅ Command input — campo de texto en parte inferior. Comandos allowlist: `help`, `clear`, `echo <text>`, `toggle_debug`, `version`, `time`. Rechaza comandos desconocidos con "Unknown command:". **Sin shell, sin scripts.**
- ✅ Toast notifications — `engine/editor/toast_notifications.py`: `ToastManager` con niveles INFO/WARN/ERR/DEBUG, auto-dismiss por duration, render en esquina inferior-derecha, singleton `TOAST_MANAGER`.
- ✅ EditorLayout integrado — `TOAST_MANAGER.render()` llamado al final de `EditorLayout.render()`.
- ✅ Tests unitarios — cobertura de `log_debug`, `_count_by_level`, `_get_filtered_logs` con filtros combinados, `_execute_command` con todos los comandos allowlist + unknown, `clear` y `toggle_debug`.

**Entregables:** Panel Console con search, badges, debug level, command allowlist. Sistema de toasts integrado en EditorLayout.

---

### Fase 9 — Viewport chrome

Mejorar el viewport del editor:
- Grid de fondo configurable.
- Gestión básica de cámara (pan, zoom, reset).
- Gizmos parciales (mover, rotar, escalar) — al menos mover funcional.
- Overlay de información (FPS, coordenadas, nodo seleccionado).
- Profesionalizar el viewport: bordes, sombra exterior, esquinas.

**Estado real (2026-05-14, entregado sin gizmo):**
- ✅ Grid configurable — `grid_enabled`, `grid_step_size` (5–500), `grid_opacity` (0–255), `grid_show_center_lines`. Método `set_grid_config()` con clamping.
- ✅ Reset de cámara — `reset_camera()` lleva zoom y target al origen. Tecla **Home** en tab SCENE (no en TERMINAL).
- ✅ Viewport chrome — sombra exterior (2px offset, alpha 80), borde UNITY_BORDER, 8 corner accent lines (16px, color UNITY_BLUE_HOVER alpha 150).
- ✅ Viewport overlay — semitransparente (α=105) en esquina superior-izquierda del viewport. Muestra: FPS, Mouse (solo tab SCENE, screen-to-world), Zoom, Target. Si `viewport_overlay_context["selected_entity"]` está definido, muestra `Selected <nombre>`. No hace world lookup ni frame-selected.
- ✅ Tests unitarios — `test_editor_layout_fase9.py`: grid defaults, grid config clamping, reset_camera + offset sync, Home shortcut con/sin terminal, overlay context, smoke draw_layout con chrome+overlay, scene_mouse_pos con coordenadas locales del viewport.
- ❌ Gizmo (mover/rotar/escalar) — NO implementado. No se tocaron `game.py`, gizmo files ni archivos críticos.
- ❌ Botón Home en toolbar — NO implementado. Solo atajo de teclado Home.

**Entregables plan original:** Viewport con grid, cámara, gizmo de movimiento, overlay de info.
**Entregables entregados:** Grid configurable, reset cámara (Home), viewport chrome (sombra + esquinas), overlay informativo con FPS/mouse/cámara/selected-if-provided. Gizmo de movimiento y botón Home pendientes.

---

### Fase 10 — Separación oficial Editor UI vs Runtime UI ✅

Separación arquitectónica completada.

**Realizado (2026-05-13):**
- ✅ `engine/editor/ui_core/` creado con 9 módulos puros: `tokens`, `colors`, `geometry`, `widget_state`, `theme`, `property_widgets`, `inspector`, `tree_view`, `__init__`. Ninguno importa pyray ni `engine.editor.ui`.
- ✅ Legacy `engine/editor/ui/*` (8 módulos) convertidos a shims que re-exportan de `ui_core` via `import *`. La función `to_ray_color()` se queda en el shim `colors.py` por su dependencia de `pyray`.
- ✅ `tests/test_ui_core_purity.py` — 4 tests que verifican: import sin pyray, análisis AST de imports prohibidos, accesibilidad de símbolos, identidad de objetos entre shim y core.
- ✅ `docs/editor_ui_architecture.md` — documento canónico que define el límite Pure Core vs Impure Shell, mapa de módulos, patrón de shim, pruebas de pureza, reglas para contribuidores y relación con Runtime UI.

**Entregables:** `docs/editor_ui_architecture.md`, `engine/editor/ui_core/` con controles base reubicados, shims legacy, tests de pureza.

---

### Fase 11 — Control tree retained-mode v1 ✅

Sistema de controles retained-mode tipo Godot completado.

**Realizado (2026-05-14):**
- ✅ `engine/editor/ui_core/controls/` creado con 5 módulos puros: `events` (ControlEvent, ControlEventKind, Size, Anchor, Margin), `control` (Control, Label, Button, Panel, TextureRect), `container` (Container, VBoxContainer, HBoxContainer, ScrollContainer), `focus` (FocusManager con tab-order), `__init__`. Ninguno importa pyray.
- ✅ `measure()` y `arrange()` para layout. Soporta expand_h/expand_v, spacing, alignment (start/center/end) en containers horizontales y verticales.
- ✅ Sistema de eventos: MOUSE_ENTER, MOUSE_EXIT, MOUSE_DOWN, MOUSE_UP, CLICK, DOUBLE_CLICK, DRAG_START, DRAG, DRAG_END, FOCUS_GAIN, FOCUS_LOST, KEY_DOWN, KEY_UP, RESIZED, SCROLL.
- ✅ FocusManager con tab-order: `build_tab_order()`, `focus_next()`, `focus_prev()`, `pick_at()` para picking descendente, `grab()`/`ungrab()` para modal grab.
- ✅ Controles base: Control, Label (texto con font_size), Button (con on_click callback), Panel (contenedor simple), TextureRect (placeholder).
- ✅ `engine/editor/ui/controls.py` — impure shell: `render_control()` con pyray, `process_input()` para input de ratón/teclado, `demo_control_tree()` para demo funcional.
- ✅ `engine/editor/ui_core/__init__.py` — exporta todos los símbolos de controls.
- ✅ Tests: `tests/test_ui_core_controls.py` — 45 tests cubriendo Size, eventos, Control base (add_child, global_rect, contains_point, dispatch, focus), Label, Button, Panel, TextureRect, Container (VBox/HBox con expand, spacing, alignment, margin), ScrollContainer, FocusManager (tab-order, pick_at, grab), pureza de imports.
- ✅ Pureza verificada: purity test extendido con 5 nuevos módulos.

**Entregables:** `engine/editor/ui_core/controls/` con controles retained-mode puros, `engine/editor/ui/controls.py` con render impuro, demo funcional, tests completos.

---

### Fase 12 — Docking y layout persistente

Crear sistema de docking completo:
- `engine/editor/docking/`: dock, tab, split, floating windows.
- Layout persistente (guardar/restaurar posición de paneles entre sesiones).
- Drag de pestañas para reordenar/acoplar.
- Auto-hide y pin de paneles laterales.

**Entregables:** Sistema de docking completo con persistencia de layout.

---

### Fase 13 — Text input serio, popups, menús contextuales

Profesionalizar la entrada de texto y los menús:
- Text input con cursor, selección, clipboard (cortar/copiar/pegar), undo/redo.
- Popups modales (confirmar acción, selector de archivo, diálogo de opciones).
- Menús contextuales (click derecho en jerarquía, inspector, viewport).
- Dropdowns y comboboxes.

**Entregables:** TextInput profesional, sistema de popups, menús contextuales.

---

### Fase 14 — Theme system tipo Godot

Implementar sistema de temas completo:
- `engine/editor/theme/`: theme manager, theme resources.
- Iconos en múltiples tamaños (16px, 24px, 32px, 64px).
- Fuentes (cargar TTF, sistema de fallback).
- Themes intercambiables (light, dark, custom).
- Theme editor básico (cambiar colores en vivo).

**Entregables:** `engine/editor/theme/` completo, themes light/dark, theme editor básico.

---

### Fase 15 — Migración gradual paneles a EditorControl

Migrar paneles existentes a la nueva arquitectura de controles retained-mode:
- Feature flags para activar/desactivar migración por panel.
- Cada panel se migra uno por uno (Hierarchy, Inspector, Console, AssetBrowser, Viewport).
- Los paneles migrados conviven con los no migrados.
- Rollback rápido si un panel migrado falla.

**Entregables:** Paneles migrados progresivamente, feature flags operativos.

---

### Fase 16 — Compartir helpers con Runtime UI

Compartir helpers de UI entre Editor UI y Runtime UI:
- Identificar controles y utilidades que el runtime puede usar (label, button, layout básico).
- Moverlos a `engine/editor/ui_core/` o `engine/ui/`.
- Runtime UI consume desde ahí sin arrastrar dependencias de editor.
- No compartir: persistencia, estado de authoring, paneles del editor.

**Entregables:** Helpers compartidos documentados, runtime importa desde `ui_core` sin dependencias de editor.

---

### Fase 17 — Polish visual completo

Pulir la apariencia visual del editor:
- Sombras, bordes redondeados, gradientes sutiles.
- Animaciones suaves (hover, focus, transiciones de panel).
- Iconografía consistente en todo el editor.
- Espaciado y alineación sistemáticos.
- Modo oscuro y modo claro completos.
- Fuente monoespaciada para consola y code inputs.

**Entregables:** Editor visualmente pulido, modo oscuro/claro completos.

---

### Fase 18 — Performance y escalabilidad

Optimizar el editor para escenas grandes:
- Virtualización de listas (hierarchy, assets, console logs).
- Caché de widgets (no recrear en cada frame).
- Dirty flags y render parcial.
- Métricas de rendimiento (FPS del editor, tiempo de render de UI).
- Profiling de paneles costosos.

**Entregables:** Editor optimizado para escenas grandes, panel de métricas.

---

### Fase 19 — Tests, screenshots y regresión visual

Asegurar calidad del editor:
- Tests unitarios para todos los controles y paneles.
- Tests de integración para flujos del editor.
- Screenshots automáticos de cada panel y estado.
- Tests de regresión visual (comparar screenshots contra baseline).
- Tests de estrés con escenas grandes.

**Entregables:** Suite completa de tests, screenshots automatizados, regresión visual.

---

### Fase 20 — Cutover oficial

Corte final cuando se cumplan todas las condiciones:
- Todos los tests pasan (unitarios, integración, regresión visual).
- `py main.py` funciona sin errores.
- Play/Pause/Stop funcionales.
- Hierarchy, Inspector, Console, AssetBrowser, Viewport estables.
- Docking y layout persistente funcional.
- Themes light/dark completos.
- No hay regresiones conocidas respecto a la línea base.
- Code review de cada fase completado con cero `must_fix`.
- Documentación canónica actualizada.

**Entregables:** Editor profesional in-engine completado, documentación final actualizada.

---

## Milestone 1

**Alcance:** Fases 0, 1, 2, 3, 4, 5, 6, 8, 9 (parcial).

Este milestone cubre la construcción del editor funcional mínimo profesional:
- Baseline y reconocimiento (F0).
- Sistema de diseño y toolkit UI (F1, F2).
- Top bar, menús y toolbar (F3).
- Panel framework (F4).
- Hierarchy profesional (F5).
- Inspector profesional (F6).
- Console y feedback (F8).
- Viewport chrome parcial (F9).

Al completar el Milestone 1, el editor debe tener un Hierarchy funcional, Inspector funcional, Console operativa, y Viewport mejorado con grid y cámara.

---

## Archivos canónicos relacionados

- `docs/editor_in_engine_baseline.md` — línea base del editor actual (Fase 0)
- `docs/editor_in_engine_godot_reference_notes.md` — notas de referencia Godot (Fase 0)
- `docs/editor_ui_architecture.md` — separación Editor UI vs Runtime UI (Fase 10)
- `docs/architecture.md` — arquitectura general del motor
- `docs/TECHNICAL.md` — detalles técnicos del motor
- `docs/api.md` — API pública del motor
- `docs/module_taxonomy.md` — taxonomía de subsistemas
