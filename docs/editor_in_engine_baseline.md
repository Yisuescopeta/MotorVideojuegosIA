---
schema_version: 1
doc_type: editor_baseline
status: baseline_snapshot
created: 2026-05-13
updated: 2026-05-13
queen_task_id: queen-20260513-001
phase_scope: 0
documents_existing_capability: true
---

# Baseline: Editor in-engine actual

- **Fecha:** 2026-05-13
- **Scope:** Fase 0 del plan maestro `docs/editor_in_engine_master_plan.md`
- **Regla:** Este documento es una snapshot del estado actual del editor. No
  modifica código, no introduce nuevas capacidades ni cambia contratos
  existentes.

---

## 1. Arquitectura general

La aplicación principal se lanza con `py main.py`. El flujo alto es:

```
main.py -> Game.run() -> bucle ppal (EDIT/PLAY/STOP)
```

| Estado | Descripción |
|--------|-------------|
| EDIT | Mundo editable construido desde `Scene` serializable. El usuario manipula entidades, componentes, jerarquía. |
| PLAY | Se clona `edit_world` a `runtime_world`. Física, gameplay, input activos. Las mutaciones runtime no contaminan el authoring state. |
| STOP | Se restaura el mundo desde `Scene`. La selección puede sobrevivir al cambio de modo. |

Invariantes centrales confirmadas en el editor actual:

- **`Scene`** es la fuente de verdad persistente.
- **`World`** es una proyección operativa (edit_world para authoring, runtime_world para PLAY).
- Las mutaciones runtime **no se guardan** como authoring state accidental.
- Los cambios de authoring pasan por `SceneManager` o `EngineAPI`.
- `EngineAPI` es la fachada pública para agentes, tests, CLI y automatización.

---

## 2. Archivos y responsabilidades

| Archivo | Responsabilidad |
|---------|-----------------|
| `main.py` | Punto de entrada. Crea `Game`, registra sistemas, arranca el bucle. |
| `engine/core/game.py` | Bucle principal del motor. Coordina EDIT/PLAY/STOP, orquesta sistemas, render y editor. |
| `engine/editor/editor_layout.py` | Layout del editor: splitters, tabs SCENE/GAME, cámara editor, transformación mouse->mundo, gestión de solicitudes (play/stop/save/etc). ~2100 líneas. |
| `engine/editor/editor_shell.py` | Composición del shell del editor. Atar (attach) layout, delegar actualización. |
| `engine/editor/editor_shell_state.py` | Estado del shell: panel slots, flags de solicitud, modo activo. |
| `engine/editor/raygui_theme.py` | Tema raygui con colores hardcodeados para botones, paneles, etiquetas. |
| `engine/editor/hierarchy_panel.py` | Panel de jerarquía: lista de entidades, selección, reparent por drag, filtro de búsqueda. |
| `engine/editor/gizmo_system.py` | Gizmos de transformación (mover, escalar, rotar). Pivot modes, snap. |
| `engine/editor/editor_tools.py` | Tool state: herramienta activa, pivot mode, snap settings, transform space. |
| `engine/editor/editor_selection.py` | Estado de selección: entidades seleccionadas, Primary, notificación de cambios. |
| `engine/editor/cursor_manager.py` | Estados visuales del cursor del editor. |
| `engine/editor/console_panel.py` | Consola: logs, filtros, conteo por nivel, input de comandos (help, clear). |
| `engine/editor/project_panel.py` | Panel de proyecto/archivos: navegación de assets. |
| `engine/editor/terminal_panel.py` | Terminal embebida (placeholder funcional). |
| `engine/editor/agent_panel.py` | Panel de agente IA: input de prompt, respuestas streaming. |
| `engine/editor/animator_panel.py` | Panel de animación: timeline, tracks, keyframes. |
| `engine/editor/scene_flow_panel.py` | Panel de flujo de escenas: transiciones, parámetros. |
| `engine/editor/sprite_editor_modal.py` | Modal de editor de sprites: asset picking, preview. |
| `engine/editor/undo_redo.py` | Sistema undo/redo: acciones, stacks, shortcuts Ctrl+Z/Ctrl+Shift+Z. |
| `engine/editor/render_safety.py` | Helpers de render: safe reset de clip state. |
| `engine/inspector/inspector_system.py` | Sistema de inspector: propiedades de entidad seleccionada por tipo de componente. |
| `engine/systems/ui_system.py` | Sistema runtime UI: procesa entidades UI (canvas, botones, texto, imagen). |
| `engine/systems/ui_render_system.py` | Render runtime UI: dibuja componentes UI en el mundo. |
| `engine/components/uibutton.py` | Componente UI Button serializable. |
| `engine/components/uitext.py` | Componente UI Text serializable. |
| `engine/components/uiimage.py` | Componente UI Image serializable. |
| `engine/components/canvas.py` | Componente Canvas (contenedor raíz de UI runtime). |
| `engine/components/recttransform.py` | Componente RectTransform (posición/tamaño relativo para UI). |

---

## 3. Qué funciona hoy

- `py main.py` lanza la aplicación interactiva sin errores.
- Layout principal con splitters: Hierarchy (izquierda), Scene/Game tabs (centro), Inspector (derecha), bottom tabs (abajo).
- Menú superior con acciones: Play, Pause, Stop, Reload, New Scene, Save Scene, Load Scene, Undo/Redo.
- Toolbar con herramientas: Select, Move, Rotate, Scale, Rect, Tile, Pencil, Animator, UI, Paint.
- Play/Pause/Stop funcionales: transición EDIT->PLAY->STOP sin pérdida de datos.
- Hierarchy: lista de entidades, selección, reparent por drag, filtro de búsqueda.
- Inspector: edición de propiedades por componente de la entidad seleccionada.
- Bottom tabs: Project, Console, Terminal, Agent, Animator, Flow.
- Project panel: navegación de archivos del proyecto.
- Console: logs con filtros por nivel, input de comandos.
- Terminal: terminal embebida funcional.
- Agent panel: chat con agente IA.
- Animator panel: timeline con tracks y keyframes.
- Scene Flow panel: configuración de transiciones entre escenas.
- Splitters funcionales para redimensionar paneles.
- Scene camera: pan (click medio) y zoom (rueda).
- Gizmos de transformación: mover, escalar, rotar.
- Sprite editor modal: asset picker.
- Undo/Redo: Ctrl+Z / Ctrl+Shift+Z.
- About modal.
- Runtime UI: botones, texto, imagen en canvas durante PLAY.

---

## 4. Deuda técnica y limitaciones conocidas

| Área | Problema |
|------|----------|
| Colores | Hardcodeados en `raygui_theme.py`. No hay sistema de tokens de diseño. |
| Render UI editor | Mezcla raygui con dibujo manual (`rl.draw_*`). Sin abstracción unificada. |
| Temas | No existe theme system. Solo `raygui_theme` con colores fijos. |
| Hierarchy | Sin virtualización. Escenas con muchas entidades degradan rendimiento. |
| Inspector | Acoplado a tipos de componente actuales. Sin widget framework reutilizable. |
| Paneles | Cada panel implementa su propio render. Sin framework común de paneles. |
| Text input | Limitado a entrada básica. Sin cursor, selección, clipboard multi-línea. |
| Popups | Sin sistema de popups/menús contextuales. Solo modales puntuales (about, sprite editor). |
| Editor UI vs Runtime UI | No hay separación formal de capas. Comparten helpers implícitamente. |
| Framework UI | No existe retained-mode control tree. Todo es immediate-mode con raygui. |
| Docking | Los paneles tienen posición fija con splitters. No hay docking arrastrable. |
| Asset browser | Funcionalidad básica. Sin vista grid, cards, breadcrumbs, filtros. |
| Performance | Sin dirty flags, sin render parcial, sin caché de widgets. Se redibuja todo cada frame. |
| Tests | Cobertura mínima de tests para el editor. Sin tests de regresión visual. |

---

## 5. Partes que NO deben romperse

| Componente | Por qué es crítico |
|------------|--------------------|
| `py main.py` | Punto de entrada único. Cualquier fase debe validar que sigue ejecutándose. |
| Play/Pause/Stop | Ciclo EDIT/PLAY/STOP es el corazón del motor. No debe degradarse. |
| Scene como verdad persistente | Ninguna mutación runtime debe contaminar el authoring state. |
| Authoring via SceneManager/EngineAPI | No introducir rutas de edición directa alternativas. |
| Hierarchy selección/reparent | Flujo principal de organización de escenas. |
| Inspector edits | Edición de propiedades vía inspector debe seguir funcionando. |
| Gizmos (move/rotate/scale) | Interacción directa en el viewport. |
| Tilemap tools | Herramientas de pintado de tilemap sobre celdas. |
| Splitters | Redimensionamiento de paneles del editor. |
| Runtime UI serializable | Componentes UI (button, text, image) en canvas deben persistir y renderizar en PLAY. |
| Cámara editor (pan/zoom) | Navegación del viewport. |

---

## 6. Capturas de pantalla

No se generaron capturas automáticas en esta fase. Las capturas manuales
pueden almacenarse en:

```
artifacts/editor_screenshots/phase0/
```

Capturas recomendadas para documentación visual futura:
- `editor_full_layout.png` — layout completo con hierarchy, scene view, inspector, bottom tabs.
- `editor_play_mode.png` — editor durante PLAY con runtime UI visible.
- `editor_hierarchy.png` — panel hierarchy con entidades expandidas.
- `editor_inspector.png` — inspector mostrando componentes de una entidad.
- `editor_console.png` — consola con logs de varios niveles.
- `editor_animator.png` — animator panel con timeline.

---

## 7. Validación

Los siguientes comandos forman parte de la validación de Fase 0 según el plan
maestro. La validación se ejecutó post-review como corrección menor.

| Comando | Estado |
|---------|--------|
| `py -m unittest tests.test_repository_governance tests.test_editor_shell tests.test_editor_tools tests.test_editor_interaction_controller -v` | **✅ 63 tests OK** — pass sin errores |
| `py main.py --headless --frames 1` | **✅ Correcto** — finaliza sin errores |
| `py -m motor doctor --project . --json` | **✅ Healthy** — success:true, issues:[], warnings:[] |
| `py -m motor ai start --project . --json` | **✅ Success** — success:true, message:"AI start contract loaded", engine.version 2026.03, warnings:[], issues:[] |
| `py -m motor ai compliance --project . --json` | **✅ Success** — native_score:100, strict_pass:true, external_runtime_detected:false, problems:[], warnings:[] |

---

## 8. Riesgos

| Riesgo | Impacto | Mitigación |
|--------|---------|------------|
| Refactor de colores/tokens rompe raygui theme actual | F1 no avanzable | Mantener `raygui_theme.py` como compatible hacia atrás hasta F14 |
| Mezcla Editor UI y Runtime UI sin separación formal | Deuda crece en fases 1-9 | Documentar límites en F10 y migrar progresivamente |
| Hierarchy sin virtualización causa lentitud en escenas grandes | Mala UX, reportes de rendimiento | Aplazar a F18 (performance), mientras tanto mantener filtro de búsqueda |
| Paneles sin framework común duplican lógica | Costo de cambio alto en fases 4-7 | Panel framework v1 en F4, migración progresiva después |
| Sin tests actuales para el editor | Regresiones no detectadas | Tests manuales de humo en cada fase; F19 automatiza |
| Sin capturas baseline | Difícil detectar regresión visual | Capturar screenshots manuales pronto (F0 o F1) |
