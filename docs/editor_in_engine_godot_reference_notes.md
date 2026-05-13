---
schema_version: 1
doc_type: godot_reference
status: reference_notes
created: 2026-05-13
updated: 2026-05-13
queen_task_id: queen-20260513-001
phase_scope: 0
implemented_capability: false
---

# Notas de referencia: Editor Godot (estructura y conceptos)

- **Fecha:** 2026-05-13
- **Propósito:** Referencia comparativa para informar el diseño del editor
  in-engine. **No es un plan de implementación.** No promociona capacidades
  como presentes solo porque Godot las tiene.
- **Regla:** Inspirarse en la arquitectura, no copiar código. Adaptar conceptos
  al modelo serializable y a la arquitectura del motor.

---

## Disclaimer

Este documento describe conceptos del editor de Godot observados en su
funcionamiento y código fuente público. Su propósito es servir como referencia
para tomar decisiones de diseño informadas, no como especificación vinculante.

Cuando este dice "Godot hace X", eso no significa que el motor deba hacer X.
Cada concepto debe evaluarse contra:

1. El modelo `Scene` como fuente de verdad persistente.
2. La separación `Editor UI` vs `Runtime UI`.
3. La arquitectura inmediata (raygui + immediate-mode) del editor actual.
4. La viabilidad de implementación por fases.

---

## Tabla comparativa de conceptos Godot

| Concepto Godot | Ruta/rol en Godot | Rol en Godot | Equivalente Motor actual | Brecha / Fase prevista |
|----------------|-------------------|--------------|--------------------------|------------------------|
| **Control** | `scene/gui/control.cpp` | Clase base de todos los nodos UI. Tiene `rect_position`, `rect_size`, `_draw()`, signals de entrada. | No existe clase base UI unificada. Cada componente UI (uibutton, uitext) tiene su propio render. | F11 — Control retained-mode |
| **Container** | `scene/gui/container.cpp` | Control que organiza hijos automáticamente (HBox, VBox, Grid, etc.). | No existe layout automático. El posicionamiento es manual vía RectTransform. | F11 — Container layout |
| **Button** | `scene/gui/button.cpp` | Botón textual/con icono. Estilos vía theme. | `engine/components/uibutton.py` (runtime) y botones raygui en editor. Sin theme. | F2 — Widgets editor / F11 — Control Button |
| **Label** | `scene/gui/label.cpp` | Texto estático con autowrap, alineación, font. | `engine/components/uitext.py` (runtime). Labels del editor son raygui directo. | F2 — Widgets editor / F11 — Control Label |
| **LineEdit** | `scene/gui/line_edit.cpp` | Entrada de texto mono-línea con cursor, selección, clipboard. | No existe equivalente completo. Terminal panel tiene input básico. | F13 — Text input serio |
| **TextEdit** | `scene/gui/text_edit.cpp` | Editor de texto multi-línea con syntax highlighting, gutter, minimap. | No existe. Agent panel tiene input multi-línea básico. | F13 — Text input serio |
| **Tree** | `scene/gui/tree.cpp` | Árbol/lista jerárquica con columnas, iconos, selección, drag & drop. | Hierarchy panel es lista plana dibujada con raygui, sin virtualización, sin columnas. | F5 — TreeView profesional |
| **ItemList** | `scene/gui/item_list.cpp` | Lista de items con iconos, selección simple/múltiple. | No existe. Project panel es lista básica. | F7 — Asset browser grid/list |
| **TabContainer** | `scene/gui/tab_container.cpp` | Contenedor con pestañas. Cada tab es un Control hijo. | Bottom tabs existen pero son manuales (check `active_bottom_tab`). | F4 — Panel framework |
| **PopupMenu** | `scene/gui/popup_menu.cpp` | Menú contextual/desplegable con items, submenús, checkboxes. | No existe. Menú superior es raygui básico. Sin menús contextuales. | F13 — Popups, menús contextuales |
| **EditorInspector** | `editor/editor_inspector.cpp` | Inspector de propiedades por categorías, subcategorías, widgets por tipo. | `engine/inspector/inspector_system.py` — propiedades planas, acoplado a componentes. | F6 — Inspector profesional |
| **SceneTreeEditor** | `editor/scene_tree_editor.cpp` | Árbol de escena con iconos, drag, búsqueda, filtro. | `engine/editor/hierarchy_panel.py` — selección, reparent, filtro. Sin iconos por tipo, sin drag a viewport. | F5 — Hierarchy profesional |
| **Docking** | `editor/dock_system.cpp` | Sistema de docking: tabs arrastrables, split, floating, layout persistente. | Splitters fijos. No hay docking arrastrable ni layouts intercambiables. | F12 — Docking completo |
| **Theme** | `scene/resources/theme.cpp` | Recurso de tema: estilos por tipo de Control, colores, fonts, icons, constants. | Colores hardcodeados en `raygui_theme.py`. No hay recurso de theme. | F14 — Theme system |
| **Theme cache** | `servers/display_server.cpp` | Caché de estilos resueltos para render rápido. | No existe. | F14 — Theme system |
| **BottomPanel** | `editor/bottom_panel.cpp` | Panel inferior con tabs (Output, Debug, Audio, Animation). | Bottom tabs ya existen (Console, Terminal, Agent, Animator, Flow). Sin framework. | F4 / F8 — Panel framework + Console |
| **EditorNode** | `editor/editor_node.cpp` | Nodo raíz del editor. Orquesta todos los paneles, menús, atajos, modo editor/play. | `editor_layout.py` y `editor_shell.py` cumplen rol similar pero sin separación de concerns. | F0-F9 — Mejora progresiva |

---

## Patrones a adaptar

### 1. Control tree retained-mode (F11)

Godot usa un árbol de controles (`Control` nodos) con ciclo `_draw()` explícito.
Cada control conoce su rect, estado, y padres/hijos. El sistema de eventos
(entrada, mouse, focus) recorre el árbol.

**Por qué adaptarlo:**
- Permite focus management, tab-order, tooltips, cursor hover por control.
- Base para widgets reutilizables (button, label, slider, tree).
- Compatible con el modelo de componentes del motor si se adapta como árbol de UI del editor, no como nodos de escena.

### 2. Theme resource (F14)

Godot separa estilo de implementación via `Theme` resource. Cada Control puede
tener estilos por estado (normal, hover, pressed, disabled, focus).

**Por qué adaptarlo:**
- Elimina colores hardcodeados.
- Permite temas intercambiables (light/dark/custom).
- Consistencia visual en todo el editor.

### 3. Docking system (F12)

El sistema de docking de Godot permite arrastrar, acoplar, flotar y reorganizar
paneles. El layout se persiste entre sesiones.

**Por qué adaptarlo:**
- Experiencia profesional: el usuario organiza su espacio de trabajo.
- Separación de layout de la lógica de cada panel.
- Los splitters actuales son step intermedio válido.

### 4. Inspector por categorías (F6)

El inspector de Godot agrupa propiedades por categorías ("Transform",
"Collision", "Physics Material"), con subcategorías expandibles.

**Por qué adaptarlo:**
- Escalable a medida que aumentan los componentes.
- Mejor experiencia que lista plana de propiedades.
- Cada componente declara sus categorías.

### 5. Scene tree con iconos y search (F5)

Godot SceneTreeEditor muestra iconos por tipo de nodo, búsqueda/filtro en
tiempo real, drag para reparent, selección múltiple.

**Por qué adaptarlo:**
- La hierarchy actual ya tiene selección y reparent. Agregar iconos y búsqueda
  es mejora incremental.
- Virtualización (F18) para escenas grandes.

### 6. Bottom panel (F4/F8)

Godot BottomPanel agrega/quita tabs dinámicamente, cada tab es un Control.
Soporta toggle con un solo click.

**Por qué adaptarlo:**
- Los bottom tabs actuales son fijos. Un framework de paneles permitiría
  mostrar/ocultar dinámicamente y compartir infraestructura.

---

## Patrones que NO adaptar / copiar

| Patrón Godot | Riesgo | Alternativa Motor |
|--------------|--------|-------------------|
| **Object / ClassDB** | Sistema de registro de clases en C++ con herencia dinámica. Sobredimensionado y acoplado al binding de GDScript. | Usar registry de componentes Python estándar (`component_registry.py`). |
| **Señales Godot como runtime principal** | Señales son el mecanismo de comunicación central en Godot. En el motor, las señales existen (`EventBus`, signals declarativas) pero no son el esqueleto del runtime. | Mantener EventBus + signals de EngineAPI. No convertir todo a señales. |
| **Serialización .tscn / .res** | Formato propio de Godot. No aplica. | El motor ya tiene `schema_v2` con JSON Scene/Prefab. Mantener ese contrato. |
| **Editor magic (autoload, tool scripts, editor plugins en GDScript)** | El editor de Godot permite ejecutar scripts `tool` en modo editor. Esto mezcla runtime y editor state de forma peligrosa para el modelo Scene/World. | El editor debe operar sobre `edit_world` via SceneManager. No ejecutar lógica runtime en modo EDIT. |
| **Resource loader complejo** | Caché de recursos, loading prioritario, background loading, subsistemas de import. | Mantener AssetService simple. Escalar solo si hay necesidad demostrada. |
| **Editor como plugin de sí mismo** | Godot está escrito en C++ y expone su editor como un "plugin" del engine. En un motor Python esto sería confuso y frágil. | El editor es parte del engine pero con capas separadas (`engine/editor/`). No necesita ser "plugin". |

---

## Ideas concretas para fases 1-9

| Fase | Idea Godot-inspirada |
|------|----------------------|
| F1 — Tokens/colores | Definir paleta baseline (oscuro tipo Godot Editor Dark) como tokens iniciales. |
| F2 — Widgets | Empezar con Label, Button, Checkbox, Slider como controles inmediatos con estado (idle/hover/active). |
| F3 — Top bar | Menú desplegable tipo Godot (File > New Scene, Save, etc.) con shortcuts visibles. |
| F4 — Panels | Crear `EditorPanel` base con header, título, contenido scrollable. Cada bottom tab existente migra a este panel. |
| F5 — Hierarchy | Agregar iconos por tipo de entidad (Sprite, TileMap, Camera, etc.). Filtro de búsqueda ya existe, mejorarlo con icon match. |
| F6 — Inspector | Agrupar propiedades por categoría (Transform, Physics, Render, UI). Widget por tipo (bool = checkbox, int = spinbox, vec2 = dos spinboxes). |
| F7 — Asset browser | Vista grid con thumbnails (si existen), vista lista con nombre/tipo/fecha. Breadcrumbs. |
| F8 — Console | Agregar badges de conteo por nivel (Godot Output panel). Filtros por nivel con toggle. |
| F9 — Viewport chrome | Grid configurable (tamaño, color, opacidad tipo Godot). Overlay de información (FPS, entidades, coordenadas). |

## Ideas concretas para fases 10-20

| Fase | Idea Godot-inspirada |
|------|----------------------|
| F11 — Control tree | `Control` base con `measure()` y `arrange()` (similar al sistema de contenedores de Godot pero simplificado). |
| F12 — Docking | Sistema de tabs arrastrables tipo Godot: drag cabecera de panel para reacoplar o flotar. Layout persistente en JSON. |
| F13 — Popups | `PopupMenu` con items, separadores, submenús, checkboxes. `PopupDialog` para confirmaciones. |
| F14 — Theme | Recurso theme con colores, fonts, icons, constants. Estilos por estado (normal/hover/pressed/disabled/focus). |
| F15 — Migración paneles | Feature flags para migrar panel por panel. Hierarchy primero, luego Inspector, Console, AssetBrowser. |
| F17 — Polish | Sombras, bordes redondeados, animaciones hover/focus, transiciones suaves. |
| F18 — Performance | Virtualización de Tree/ItemList. Dirty flags. Caché de estilos (theme cache). |

---

## Licencia y atribución

Godot Engine es software libre y de código abierto con licencia MIT. Su
código fuente público ha sido estudiado para comprender la arquitectura de su
editor. Este documento usa esa comprensión como **inspiración conceptual**
solamente.

- No se incluye código de Godot.
- No se reproduce lógica interna de Godot.
- Las adaptaciones propuestas respetan el modelo Scene/World, el contrato de
  serialización `schema_v2`, y la arquitectura inmediata del motor.

---

## Referencias Godot (código fuente público)

Las referencias a archivos Godot (`scene/gui/*.cpp`, `editor/*.cpp`) se basan en
el código fuente de Godot Engine disponible en https://github.com/godotengine/godot.
Se mencionan a nivel de ruta conceptual, no para reproducir implementación.
