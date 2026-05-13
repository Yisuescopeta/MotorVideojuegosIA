---
schema_version: 1
doc_type: editor_plan
status: active_plan
created: 2026-05-13
updated: 2026-05-13
queen_updated: queen-20260513-003
queen_task_id: queen-20260513-001
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

**Estado real (2026-05-13, foundation v1):**
- ✅ `engine/editor/ui/property_widgets.py` — creado: PropertyKind, PropertyDescriptor, EditTransaction, CommitContract, PropertyEditResult. Pure data model, sin render.
- ✅ `engine/editor/ui/inspector.py` — creado: InspectorGroup, InspectorModel, build_inspector_model_from_dict, infer_property_kind. Pure data model/builders, sin render.
- ❌ Panel Inspector funcional — NO implementado. Los módulos existen como foundation de datos, pero el inspector production existente (`engine/inspector/inspector_system.py`) NO está reemplazado ni el nuevo panel está wired en el layout del editor. Testing via nuevos tests unitarios.

**Entregables plan original:** `engine/editor/ui/inspector.py`, `engine/editor/ui/property_widgets.py`, panel Inspector funcional.
**Entregables entregados:** `engine/editor/ui/inspector.py` (foundation), `engine/editor/ui/property_widgets.py` (foundation). Panel Inspector pendiente.

---

### Fase 7 — Project / Asset browser

Construir el navegador de proyectos y assets:
- Vista grid y lista.
- Tarjetas (cards) con icono, nombre, tipo.
- Breadcrumbs de navegación.
- Filtros por tipo de asset.
- Integración con `AssetService` existente.
- Doble-click para abrir asset en inspector o editor correspondiente.

**Estado real (2026-05-13, Fase 7 minimal done):**
- ✅ Vista grid — existente, refactorizada a `_render_content_grid()`.
- ✅ Vista lista — NUEVA: `_render_content_list()`, toggle grid/list en toolbar.
- ✅ Breadcrumbs de navegación — existentes.
- ✅ Filtros por tipo de asset — existentes.
- ✅ Integración con `AssetService` — existente.
- ✅ Doble-click en imagen → abre sprite editor (`request_open_sprite_editor_for`).
- ✅ Doble-click en escena (`levels/`) → abre escena (`request_open_scene_for`).
- ❌ Doble-click en otros tipos (scripts, prefabs, etc.) — no-op, futuro.
- ❌ Thumbnails reales — NO implementados. Iconos placeholder de color sólido.
- ❌ Drag & drop desde asset browser a viewport/inspector — no implementado.
- ❌ Vista de tarjetas (cards) con preview grande — no implementado.

**Entregables plan original:** Panel AssetBrowser funcional con vista grid/lista.
**Entregables entregados:** Vista grid/lista funcional, doble-click para image/scene, toggle view mode. Pendiente: thumbnails reales, drag & drop, doble-click para otros tipos, vista de tarjetas.

---

### Fase 8 — Console / Logs / Terminal feedback

Construir el panel de consola y feedback:
- Salida de logs con niveles (info, warn, error, debug).
- Filtros por nivel y búsqueda.
- Badges de conteo por nivel.
- Command input para ejecutar comandos de consola (ej. `help`, `clear`, scripts).
- Notificaciones del sistema (toast, notificaciones de error breve).
- Seguridad: sanitizar input de comandos, no exponer APIs internas peligrosas.

**Entregables:** Panel Console funcional, sistema de notificaciones.

---

### Fase 9 — Viewport chrome

Mejorar el viewport del editor:
- Grid de fondo configurable.
- Gestión básica de cámara (pan, zoom, reset).
- Gizmos parciales (mover, rotar, escalar) — al menos mover funcional.
- Overlay de información (FPS, coordenadas, nodo seleccionado).
- Profesionalizar el viewport: bordes, sombra exterior, esquinas.

**Entregables:** Viewport con grid, cámara, gizmo de movimiento, overlay de info.

---

### Fase 10 — Separación oficial Editor UI vs Runtime UI

Crear separación arquitectónica clara:
- Documentar la separación en `docs/editor_ui_architecture.md`.
- Crear `engine/editor/ui_core/` mínimo con controles compartibles.
- Los helpers de UI que el runtime pueda usar van en `ui_core`.
- La UI del editor (paneles, menús, inspector) se queda en `engine/editor/ui/`.
- Runtime UI no importa de `engine/editor/ui/` directamente.

**Entregables:** `docs/editor_ui_architecture.md`, `engine/editor/ui_core/` con controles base reubicados.

---

### Fase 11 — Control tree retained-mode v1

Implementar sistema de controles retained-mode tipo Godot:
- `measure()` y `arrange()` para layout.
- Sistema de eventos (mouse_enter, mouse_exit, click, drag, focus, blur).
- Focus management con tab-order.
- Controles base: Control, Container, Button, Label, Panel.
- Demo de controles retained-mode funcionando en el editor.

**Entregables:** `engine/editor/ui/controls/` con controles retained-mode, demo funcional.

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
