# Editor UI Architecture — Pure Core vs Impure Shell

- **Estado:** canonical
- **Creado:** 2026-05-13 (Fase 10 del plan editor)
- **Propósito:** Definir el límite arquitectónico entre modelos de UI puros
  (serializables, testables sin ventana) y código impuro de render/input.

---

## Principio

La UI del editor se divide en dos capas con una regla de dependencia estricta:

```
engine/editor/ui_core/  (puro, sin pyray, sin dependencias del editor)
        ^
        | imports
        |
engine/editor/ui/      (impuro, puede importar pyray y raygui)
```

- **`ui_core`** contiene modelos de datos, lógica de layout, tokens de diseño,
  constantes y cualquier código que pueda ejecutarse sin una ventana Raylib.
- **`ui`** contiene render, input, dibujo con pyray/raygui, integración de
  paneles, y toda lógica que requiera una ventana activa.

El runtime UI (cuando exista) debe importar solo de `ui_core`, nunca de `ui`.

---

## Mapa de módulos vigente

### `engine/editor/ui_core/` — Pure data models

| Módulo | Contenido | Importa de |
|--------|-----------|------------|
| `tokens.py` | Constantes de diseño: colores, tamaños, espaciado, tipo `RGBA` | solo stdlib |
| `colors.py` | Helpers de color: `rgba()`, `lerp_color()`, `with_alpha()`, conversiones | `tokens` |
| `geometry.py` | Helpers de rect: `inset_rect()`, `split_*()`, `Rect`, `clamp_rect()` | solo stdlib |
| `widget_state.py` | `WidgetResult`, `WidgetState`, `WidgetVisualState`, `resolve_visual_state()` | solo stdlib |
| `theme.py` | `EditorTheme`, `UNITY_DARK`, `theme_to_raygui_map()` | `tokens` |
| `protocols.py` | `EntityLike`, `WorldLike`, `PropertyValue` para contratos estructurales puros | solo stdlib |
| `property_widgets.py` | `PropertyKind`, `PropertyDescriptor`, `EditTransaction`, `PropertyEditResult` | solo stdlib |
| `inspector.py` | `InspectorGroup`, `InspectorModel`, `build_inspector_model_from_dict()` | `property_widgets` |
| `tree_view.py` | `TreeModel`, `TreeNode`, `matches_search()`, `filter_nodes()` | solo stdlib |
| `docking.py` | `DockLayout`, `DockSplit`, `DockArea`, `dock_node_from_dict()`, `normalize_ratio()` — modelo puro serializable de docking | solo stdlib |
| `dock_rects.py` | `compute_dock_rects()`, `DockRects`, `RectTuple` — proyección de árbol dock a rectángulos visuales | solo stdlib |
| `__init__.py` | Re-export público de todos los símbolos de ui_core | todos los anteriores |
| `controls/__init__.py` | Re-export de símbolos públicos del subpaquete controls | todos los de controls/ |
| `controls/events.py` | `ControlEvent`, `ControlEventKind`, `Size`, `Anchor`, `Margin` | solo stdlib |
| `controls/control.py` | `Control`, `Label`, `Button`, `Panel`, `TextureRect` retained-mode | `controls.events`, `controls.focus` (TYPE_CHECKING) |
| `controls/container.py` | `Container`, `VBoxContainer`, `HBoxContainer`, `ScrollContainer` con measure/arrange | `controls.control`, `controls.events` |
| `controls/focus.py` | `FocusManager` con tab-order, grab, pick_at | `controls.control` (TYPE_CHECKING) |

Regla: **ningún módulo en `ui_core` puede importar `pyray`, `engine.editor.ui`,
ni ningún módulo del runtime.**

### `engine/editor/ui/` — Impure shell / shims

| Módulo | Ahora es | Importa de |
|--------|----------|------------|
| `tokens.py` | shim: `from engine.editor.ui_core.tokens import *` | `ui_core.tokens` |
| `colors.py` | shim parcial: re-exporta todo de `ui_core.colors` **excepto** `to_ray_color()` que queda aquí | `ui_core.colors`, `pyray` |
| `geometry.py` | shim: `from engine.editor.ui_core.geometry import *` | `ui_core.geometry` |
| `widget_state.py` | shim: `from engine.editor.ui_core.widget_state import *` | `ui_core.widget_state` |
| `theme.py` | shim: `from engine.editor.ui_core.theme import *` | `ui_core.theme` |
| `property_widgets.py` | shim: `from engine.editor.ui_core.property_widgets import *` | `ui_core.property_widgets` |
| `inspector.py` | shim: `from engine.editor.ui_core.inspector import *` | `ui_core.inspector` |
| `tree_view.py` | shim: `from engine.editor.ui_core.tree_view import *` | `ui_core.tree_view` |
| `draw.py` | impuro (render con pyray) | `ui_core.*`, `pyray` |
| `input.py` | impuro (input de ratón/teclado) | `pyray` |
| `icons.py` | impuro (carga/dibujo de iconos) | `pyray` |
| `panels.py` | impuro (layout de paneles) | `ui_core.*`, `pyray` |
| `scroll.py` | impuro (scroll con pyray) | `ui_core.*`, `pyray` |
| `widgets.py` | impuro (widgets raygui) | `ui_core.*`, `pyray` |
| `controls.py` | impuro (render retained-mode + process_input + `demo_control_tree()`) | `ui_core.controls.*`, `pyray` |
| `inspector_render.py` | impuro (render inspector + edición inline vía SceneManager/EngineAPI) | `inspector`, `property_widgets`, `pyray` |

La función `to_ray_color()` es la única función que vive en el shim
`colors.py` (no en `ui_core.colors`) porque requiere `import pyray` en
tiempo de dibujo.

---

## Patrón de shim

Cada módulo puro que se mueve a `ui_core` deja atrás un shim en `ui/`
que re-exporta todo con `from engine.editor.ui_core.<module> import *`.
Esto garantiza que el código existente que importa de `engine.editor.ui`
siga funcionando sin cambios.

Excepciones a `import *`:
- Si el módulo original tenía funciones impuras (como `to_ray_color`),
  esas se quedan en el shim y no se mueven a `ui_core`.

Los shims son mantenimiento mínimo. El código nuevo debe importar
directamente de `engine.editor.ui_core` cuando solo necesite modelos
puros, y de `engine.editor.ui` solo cuando necesite render/input.

---

## Pruebas de pureza

`tests/test_ui_core_purity.py` verifica:

1. **`test_import_ui_core_does_not_import_pyray`**: importar `ui_core` no
   arrastra `pyray` a `sys.modules`.
2. **`test_ui_core_static_imports_stay_pure`**: análisis AST de cada módulo
   en `ui_core` — ningún import a `pyray`, `engine.editor.ui` ni sus
   submódulos (icons, input, draw, panels, widgets, scroll).
3. **`test_core_symbols_accessible`**: los símbolos clave son accesibles
   desde `engine.editor.ui_core`.
4. **`test_old_shim_paths_match_core_symbols`**: los shims legacy re-exportan
   los mismos objetos (misma identidad `is`) que `ui_core`.

---

## Reglas para contribuidores

1. **Código nuevo puro** (sin pyray, sin ventana, serializable) →
   `engine/editor/ui_core/`.
2. **Código nuevo impuro** (render, input, pyray, raygui) →
   `engine/editor/ui/`.
3. **No importes `engine.editor.ui` desde runtime** — el runtime solo debe
   ver `engine.editor.ui_core`.
4. **No importes `engine.editor.ui_core` desde `engine.editor.ui`** con
   dependencia inversa — `ui` importa `ui_core`, nunca al revés.
5. **Si una función pura necesita un parámetro que solo el render conoce**
   (ej. un `pyray.Color`), pasa el valor ya resuelto desde el caller
   impuro; no arrastres la dependencia al modelo puro.

---

## Ejemplos de uso

### Imports puros desde `ui_core`

```python
from engine.editor.ui_core import EntityLike, PropertyDescriptor, PropertyKind, TreeModel


def build_editor_tree(world: object) -> TreeModel:
    return TreeModel.build(world)


def label_for(entity: EntityLike) -> PropertyDescriptor:
    return PropertyDescriptor("name", PropertyKind.STR, value=entity.name)
```

### Pruebas de pureza

```python
import ast
from pathlib import Path


def test_ui_core_module_has_no_impure_imports() -> None:
    path = Path("engine/editor/ui_core/tree_view.py")
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imports = [node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom) and node.module]

    assert "pyray" not in imports
    assert "engine.editor.ui" not in imports
```

### Shims legacy

```python
# Codigo nuevo puro: preferido.
from engine.editor.ui_core.tree_view import TreeModel

# Codigo legacy: permitido para compatibilidad, re-exporta el mismo objeto.
from engine.editor.ui.tree_view import TreeModel as LegacyTreeModel

assert LegacyTreeModel is TreeModel
```

### Anti-patron

```python
# No hacer esto dentro de engine/editor/ui_core/.
import pyray
from engine.editor.ui.widgets import button
```

`ui_core` no debe depender de render, input, ventana activa ni shims impuros.

---

## Relación con Runtime UI

El runtime UI (UI serializable en escenas, como Canvas/Button/Text) es
un sistema diferente. No comparte estado de authoring ni persistencia con
el editor UI. Lo que comparte son los _modelos de datos puros_ de
`ui_core` (colores, geometría, temas) cuando el runtime necesita dibujar
controles con apariencia consistente.

El runtime UI **no debe**:
- Importar `engine.editor.ui`
- Importar módulos de `engine.editor.ui_core` que sean específicos del
  editor (como `InspectorModel`, `TreeModel`)
- Usar `WidgetState` del editor (el runtime tiene su propio estado de UI)

El runtime UI **puede**:
- Usar `tokens`, `colors`, `geometry` de `ui_core` para mantener
  consistencia visual
- Usar `Rect` y helpers geométricos

---

## Historial

| Fecha | Cambio |
|-------|--------|
| 2026-05-13 | Creación del documento (Fase 10) |
| 2026-05-14 | Añadido `inspector_render.py` como capa impura editor UI (InspectorPanel v1 opcional) |
| 2026-05-14 | Añadidos `docking.py` y `dock_rects.py` al mapa puro de `ui_core` (Fase 12) |
