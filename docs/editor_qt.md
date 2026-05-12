# Editor Qt

Estado: `experimental/tooling`.

`editor_qt` inicia la base progresiva del editor principal en PySide6. No
reemplaza `main.py`, no elimina el editor raylib/raygui y el viewport Qt-native
es de authoring (sin raylib, sin `Game.run()`).

## Instalacion

PySide6 es dependencia opcional del editor:

```bash
py -m pip install -e ".[editor]"
```

El core, runtime headless y editor legacy no dependen de PySide6.

## Ejecucion

```bash
py -m editor_qt.app
```

Sin `--project`, Qt abre primero el launcher de proyectos. Desde ahi se puede
buscar proyectos recientes, registrar una carpeta existente con `Add` y entrar
al editor con doble click. `New Project` crea proyectos mediante
`EditorEngineFacade -> EngineAPI.create_project()`.

Tambien queda disponible el entry point:

```bash
motor-editor
```

Opciones iniciales:

```bash
py -m editor_qt.app --project .
py -m editor_qt.app --project . --scene levels/demo_level.json
py -m editor_qt.app --project . --theme frost_light
```

`--theme` acepta `frost_dark` y `frost_light`. Si se omite, usa la
preferencia guardada en `editor_state.preferences.theme` o `frost_dark`.

## Arquitectura

Los widgets Qt no acceden a `World`, `SceneManager` ni sistemas internos. La
ruta inicial es:

```text
Qt UI -> EditorEngineFacade -> EngineAPI -> SceneManager/Scene
```

`EditorEngineFacade` vive en `editor_qt/bridge/engine_facade.py` y es la unica
entrada de los paneles Qt hacia el motor. La seleccion visual es estado efimero
del editor; las mutaciones de authoring se delegan a `EngineAPI`.

### EditorEngineFacade

Metodos publicos del facade hacia los paneles Qt:

| Metodo | Descripcion |
|---|---|
| `list_entities()` | Lista entidades de la escena activa |
| `get_entity(name)` | Datos de una entidad |
| `create_entity(name)` | Crea entidad raiz |
| `delete_entity(name)` | Elimina entidad |
| `set_entity_parent(name, parent)` | Re-parenta o des-parenta entidad |
| `create_child_entity(parent, name)` | Crea entidad hija en parent |
| `duplicate_entity(name)` | Duplica entidad con todos sus componentes |
| `add_component(entity, component, data)` | Agrega componente a entidad |
| `remove_component(entity, component)` | Elimina componente de entidad |
| `replace_component_data(entity, component, data)` | Reemplaza data completa de componente |
| `update_component_property(entity, comp, prop, value)` | Edita propiedad serializable |
| `select_entity(name)` | Fija seleccion visual |
| `get_active_scene_info()` | Info de escena activa |
| `load_scene(ref)` / `load_default_scene()` | Carga escena |
| `create_scene(name)` | Crea escena nueva |
| `save_scene()` | Guarda escena activa |
| `undo()` / `redo()` | Deshacer / rehacer |
| `has_unsaved_changes()` | Escena activa tiene dirty state |
| `get_scene_connections()` / `set_scene_connection()` | Scene flow |
| `get_animator_info()`, `list_animator_states()`, `ensure_animator()`, `set_animator_sprite_sheet()`, `upsert_animator_state()`, `remove_animator_state()`, `set_animator_speed()`, `set_animator_flip()` | Animator |
| `list_agent_providers()`, `list_agent_tools()`, `create_agent_session()`, `send_agent_message()`, `approve_agent_action()` | Agent |
| `list_project_scenes()`, `list_project_assets()`, `list_project_scripts()`, `list_project_prefabs()` | Project browser |
| `get_editor_state()` / `save_editor_state()` / `save_editor_preferences()` | Preferencias UI del editor |
| `set_entity_active(name, active)` | Activa/desactiva entidad desde Hierarchy |
| `list_component_descriptors()` | Componentes disponibles para Add Component |
| `create_project()`, `open_project()` | Project lifecycle |
| `migrate_legacy_project(path)` | Importa carpeta legacy (`levels/*.json`) sin `project.json` |
| `refresh_assets()` | Asset catalog |
| `instantiate_prefab(path, name, x, y)` | Instancia un prefab en posicion mundo con override de Transform |
| `get_sprite_metadata(asset_path)` | Lee metadatos de sprite de un asset (slices, etc.) |
| `save_sprite_metadata(asset_path, metadata)` | Persiste metadatos de sprite de un asset |
| `shutdown()` | Cierre |

El facade NO expone `EngineAPI` directamente. Los paneles solo ven metodos
tipados del facade.

## Estado actual

### Proyecto y launcher

- Launcher Qt de proyectos recientes antes de entrar al editor.
- `New Project` crea proyectos mediante `EngineAPI.create_project()`.
- **Import Legacy**: botón que abre selector de carpeta y migra proyectos existentes sin `project.json`.
- **Auto-detección**: al hacer doble click en carpeta sin `project.json` pero con `levels/*.json`, pregunta si migrar y lo hace mediante `facade.migrate_legacy_project()`.

### Ventana principal

- `QMainWindow` con tema Frostline, menu bar, top bar superior, left rail,
  `Hierarchy` izquierda, `Inspector` derecha, tabs centrales
  `Scene/Game/Flow/Animator` y tabs inferiores `Project/Flow/Console/Terminal/Agent`.
- Top bar: proyecto activo, selector de escena, herramientas de transform,
  play/build deshabilitados con tooltip, shell segmentado tipo Frostline,
  utilidades undo/redo/theme y avatar/menu placeholder.
- Left rail: icono + label, estado activo cyan, enfoca vistas principales sin
  mutar escena.
- Preferencias UI persistidas en `editor_state.preferences`: tema, splitters,
  tabs activos, rail activo y modo grid/list del Project panel. No se guardan
  como datos de escena.

### Viewports (Qt-native, sin raylib)

- `Scene` y `Game` renderizan entidades con QPainter sobre fondo oscuro.
- **Camara de editor**: pan con middle-mouse drag, zoom con scroll wheel
  (zoom hacia el cursor).
- **Grid** dibujado en coordenadas mundo con lineas cada 32px y ejes en origen.
- **Seleccion visual**: click izquierdo sobre bounding rect de entidad.
- **Gizmo Move**: arrastre de entidad seleccionada con handles coloreados
  (rojo=X, verde=Y, blanco=libre).
- Toolbar con herramientas `Select` / `Move` / `Rotate` / `Scale` (checkables):
  - `Select` → `GizmoMode.SELECT` (sin render)
  - `Move` → `GizmoMode.TRANSLATE_FREE`
  - `Rotate` → `GizmoMode.ROTATE_Z` (anillo + angulo)
  - `Scale` → `GizmoMode.SCALE_UNIFORM` (escala uniforme con handles ±X y ±Y)
- Senal `entity_moved` que commitea `after_state` (x, y, rotation, scale_x,
  scale_y) via `EngineAPI.edit_component()`. Usa `after_state` del gizmo
  en lugar de `world_x`/`world_y` directos.
- **Asset drop**: arrastrar asset desde Project Panel al viewport invoca
  `_on_viewport_asset_dropped()`. La ruta depende de `asset_type`:
  - `prefab`: llama `facade.instantiate_prefab(path, name, x, y)` que
    instancia el prefab con Transform sobreescrito en la posicion de drop.
  - `image` (`.png`, `.jpg`, `.jpeg`, `.bmp`): crea entidad via
    `facade.create_entity()`, asigna Transform en posicion de drop,
    agrega componente `Sprite` con `texture_path` y componente `Collider`
    (32×32). No pasa por `instantiate_prefab`.

- **Viewport chrome Frostline**: overlay con zoom, reset camera y frame
  selected; outline de seleccion y hover; ghost preview al arrastrar assets;
  grid adaptado para tema claro/oscuro.

### Hierarchy

- `QTreeWidget` con estructura de arbol por parentesco, busqueda y columna
  Active.
- La busqueda filtra sin destruir datos y conserva seleccion/expansion cuando
  es posible.
- El toggle Active emite `entity_active_set_requested`; `MainWindow` delega en
  `EditorEngineFacade.set_entity_active()`.
- **Drag-drop reparenting**: arrastrar entidad sobre otra la re-parenta.
- **Menu contextual** sobre entidad: `Create Entity`, `Create Child Entity`,
  `Delete Entity`, `Duplicate Entity`, `Unparent`, `Save as Prefab`.
- Botones `Create`, `Delete`, `Refresh`.
- Senales: `entity_selected`, `entity_create_requested`, `entity_delete_requested`,
  `entity_create_child_requested`, `entity_duplicate_requested`,
  `entity_reparent_requested`, `entity_active_set_requested`.

### Inspector

- `QTreeWidget` con componentes como foldouts expandibles.
- **Editores tipados** inline por tipo de valor:
  - `bool` → `QCheckBox`
  - `int` → `_CommittableSpinBox` (-999999 a 999999)
  - `float` → `_CommittableDoubleSpinBox` (3 decimales, -999999 a 999999)
  - `str`, `None`, `list`, `dict` → `QLineEdit` con codificacion JSON
- **Commit-on-finish**: `_CommittableSpinBox`/`_CommittableDoubleSpinBox`
  emiten `commit_requested` solo en **Enter** o **focusOut**. **Escape**
  restaura el valor original sin commit. El slot `property_edit_requested` se
  conecta a `commit_requested`, no a `valueChanged`.
- Boton **Add Component**: picker searchable basado en
  `ComponentRegistry.list_descriptors()`, emite `component_add_requested`.
- Boton **Remove Component** (`✕`) por componente, excepto `Transform` que es
  inamovible.
- Senales: `property_edit_requested`, `component_add_requested`,
  `component_remove_requested`.

### Scene Flow, Animator, Terminal, Agent

- `Flow` edita conexiones `scene_flow` via `EngineAPI`.
- **FlowCanvasWidget** (`editor_qt/panels/flow_canvas.py`): vista
  QGraphicsView + sidebar con nodos arrastrables y aristas dirigidas.
  - `FlowNodeItem`: nodo rectangular (160×56) con circulo conector izquierdo
    y derecho. Arrastrable, emite `node_moved` via `FlowScene.node_moved`.
  - `FlowEdgeItem`: linea naranja dirigida entre dos nodos.
  - `FlowScene`: `node_moved(node_key, x, y)`, `add_flow_node()`,
    `add_flow_edge()`, `clear_flow()`.
  - `FlowCanvasWidget`: toolbar (modo one-way/two-way, filtro, refresh),
    sidebar con lista de SceneLink objects, splitter, boton Add SceneLink.
  - Datos cargados via `set_flow_data(flow_graph, scenes)` con
    `sidebar_items`, `canvas_nodes`, `canvas_edges`.
  - Señales: `connection_created(source_key, target_key)`,
    `node_position_changed(node_key, x, y)`, `refresh_requested`.
- `Animator` trabaja sobre la entidad seleccionada.
- **Sprite Editor**: diálogo modal (`SpriteEditorDialog`) para recortar spritesheets en modos `Grid`, `Auto` y `Manual`. Se abre desde el botón `Open Sprite Editor` en el panel Animator. Al guardar, el MainWindow lee metadata existente via `facade.get_sprite_metadata()`, fusiona los nuevos slices bajo clave `"slices"` y persiste via `facade.save_sprite_metadata()`. El botón solo aparece si hay entidad seleccionada con animator.
- **Slice names**: el panel Animator solicita nombres de slices via `facade.get_sprite_metadata(sheet_path)` — sin bypass directo a `EngineAPI`.
- `Terminal` usa `QProcess`, solo arranca al pulsar `Start`.
- `Agent` crea sesiones y envia mensajes via `EngineAPI` AgentAPI.

### Project panel

- Muestra escenas, assets, prefabs y scripts en modo read-only (con
  `list_project_scenes()`, `list_project_assets()`, `list_project_scripts()`,
  `list_project_prefabs()`).
- Assets soporta modo grid/list, thumbnails para imagenes, breadcrumbs,
  filtros tipo pill y card **Add Scene** que emite `scene_create_requested`.
- Los items del arbol de prefabs llevan `asset_type='prefab'` en datos
  de drag; los de scripts llevan `asset_type='script'`. El MainWindow
  usa este tipo para decidir la ruta de drop en el viewport.

### Console

- Console Qt usa filtros pill `All`, `Log`, `Warning`, `Error`, timestamps,
  clear action, resumen de contadores y fila de comando.
- `clear` y `help` se manejan localmente. Otros comandos emiten
  `command_submitted`; no se ejecuta shell generica desde el panel.

### Gizmo (`editor_qt/gizmo/`)

Paquete `experimental/tooling` dentro de `editor_qt`:

- `GizmoMode` enum: `NONE`, `SELECT`, `TRANSLATE_X`, `TRANSLATE_Y`,
  `TRANSLATE_FREE`, `ROTATE_Z`, `SCALE_X`, `SCALE_Y`, `SCALE_UNIFORM`, `RECT`.
- `CompletedGizmoDrag` dataclass: `entity_name`, `component_name`,
  `before_state`, `after_state`, `label`.
- `GizmoHandle`: handle individual con modo y rect de hit-test.
- `GizmoManager`:
  - `set_mode(mode)`
  - `mode` (property), `current_angle` (property), `current_scale` (property, `tuple[float,float]`)
  - `build_handles(center_screen, zoom, rect_w=0, rect_h=0)` — envoltorio público de `_build_handles()`
  - `hit_test(screen_pos)` → handle id o `None`
  - `start_drag(handle_id, screen_pos, world_x, world_y, *, rotation=0,
    scale_x=1, scale_y=1, entity_name="", component_name="")`
  - `update_drag(screen_pos, zoom)` → `(world_x, world_y)`
  - `end_drag()` → `{handle, world_x, world_y, rotation, scale_x, scale_y,
    before_state, after_state, label}` o `None`
  - `render(painter, entity_rect, zoom)`: renderiza segun modo activo
- **Translate**: ejes rojo/verde con flechas y cuadrado central blanco,
  handles en screen-space constante.
- **Rotate**: anillo naranja `#44aaff` + linea de angulo `#ffaa44`.
  Arrastre rota en Z. Hit-test en el anillo (`abs(dist - radius) <= 6px`).
- **Scale**: ejes X (rojo) e Y (verde) con handles cuadrados.
  `SCALE_UNIFORM` pinta ambos ejes con handles en ±X y ±Y.
- **RECT**: 8 handles (4 esquinas + 4 puntos medios) + outline azul.
- **Snap** (Ctrl): posiciones/rotaciones/escalas redondean a `SNAP_STEP` (16px)
  o `15°` en rotación.
- **Constrain** (Shift): en TRANSLATE_FREE restringe a eje dominante;
  en SCALE_UNIFORM escala uniforme (recalcula ratio).
- `end_drag()` devuelve `before_state`/`after_state` con `{x, y, rotation,
  scale_x, scale_y}` + `label` legible (ej. `"rotate_z"`, `"scale_uniform"`).

### Estado general

- Carga escena inicial con `EngineAPI.load_scene_for_runtime_inspection()`.
- Guardado manual con `Save Scene` (`EngineAPI.save_scene()`).
- `Undo` / `Redo` delegan en `EngineAPI`.
- `Canvas`, `Text` y `Button` delegados en rutas UI de `EngineAPI`.
- `Refresh Assets` delega en `EngineAPI.refresh_asset_catalog()`.
- Barra de estado muestra proyecto, escena activa, entidades y `Unsaved`.
- Al cerrar con dirty state, Qt pide guardar, descartar o cancelar.
- No se inicializa raylib ni se ejecuta `Game.run()`.

## Flujo de señales

Los paneles Qt no llaman directamente a `EngineAPI`. Emiten señales Qt que la
`MainWindow` conecta a slots, y esos slots delegan en `EditorEngineFacade`, que
a su vez usa `EngineAPI`. El patrón es:

```text
Panel → Signal → MainWindow slot → Facade → EngineAPI
```

| Señal | Origen | Parámetros | Dispara |
|-------|--------|------------|---------|
| `entity_selected` | HierarchyPanel, QtSceneViewportPanel | `entity_name: str` | Inspector refresh, Animator refresh |
| `entity_create_requested` | HierarchyPanel | `entity_name: str` | `facade.create_entity()` |
| `entity_delete_requested` | HierarchyPanel | `entity_name: str` | `facade.delete_entity()` |
| `entity_create_child_requested` | HierarchyPanel | `parent_name: str, child_name: str` | `facade.create_child_entity()` |
| `entity_duplicate_requested` | HierarchyPanel | `entity_name: str` | `facade.duplicate_entity()` |
| `entity_reparent_requested` | HierarchyPanel | `entity_name: str, new_parent: str` | `facade.set_entity_parent()` |
| `entity_active_set_requested` | HierarchyPanel | `entity_name: str, active: bool` | `facade.set_entity_active()` |
| `property_edit_requested` | InspectorPanel | `entity, component, property, value_text, original` | `facade.update_component_property()` |
| `component_add_requested` | InspectorPanel | `entity_name: str, component_name: str` | `facade.add_component()` |
| `component_remove_requested` | InspectorPanel | `entity_name: str, component_name: str` | `facade.remove_component()` |
| `entity_moved` | QtSceneViewportPanel | `entity, component, prop, new_x: float, new_y: float` | `facade.update_component_property()` x2; emite `after_state` del gizmo |
| `connection_created` | FlowCanvasWidget | `source_key: str, target_key: str` | `facade.set_scene_connection()` |
| `node_position_changed` | FlowCanvasWidget | `node_key: str, x: float, y: float` | Persist position (placeholder) |
| `refresh_requested` | FlowCanvasWidget | — | `facade.get_scene_connections()` para recargar |
| `scene_requested` | ProjectPanel | `scene_ref: str` | `facade.load_scene()` |

| `scene_create_requested` | ProjectPanel | — | abre flujo `New Scene` en `MainWindow` |
| `command_submitted` | ConsolePanel | `command: str` | `MainWindow` registra comando no soportado |

## Ejemplos para agentes IA

Uso headless desde Python mediante `EditorEngineFacade`. No existe comando CLI
`sprite metadata`; usa la ruta Python (EngineAPI / facade).

### instantiate_prefab

```python
from editor_qt.bridge.engine_facade import EditorEngineFacade

facade = EditorEngineFacade(project_root=".")
facade.load_default_scene()
result = facade.instantiate_prefab(
    path="prefabs/Enemy.prefab",
    name="Enemy_01",
    x=320.0,
    y=240.0,
)
# result.success == True si se instanció correctamente
```

### get_sprite_metadata / save_sprite_metadata

Leer metadatos, fusionar slices nuevos y persistir sin perder metadata
existente:

```python
# 1. Leer metadata actual (slices, dimensions, etc.)
metadata = facade.get_sprite_metadata(asset_path="assets/player.png")
# → dict existente o {} si no hay metadata guardada aun

# 2. Agregar nuevos slices conservando los previos
new_slices = [
    {"name": "idle_1", "x": 0, "y": 0, "w": 32, "h": 48},
    {"name": "idle_2", "x": 32, "y": 0, "w": 32, "h": 48},
]
metadata.setdefault("slices", []).extend(new_slices)

# 3. Persistir el dict completo
result = facade.save_sprite_metadata(
    asset_path="assets/player.png",
    metadata=metadata,
)
# result.success == True si se guardó correctamente
```

`save_sprite_metadata` fusiona/actualiza el metadata existente del asset. No
reemplaza el dict completo: conserva claves previas no incluidas en la llamada.
Para evitar sobrescritura accidental de datos, lee siempre con
`get_sprite_metadata`, modifica el dict y guarda — tal como muestra el ejemplo
anterior.

## Validacion automatizada

Los tests unitarios de `GizmoManager` (`tests/test_editor_qt_gizmo.py`, 31 tests) cubren modo enum, drag, snap, constrain y render de todos los modos.

Los tests cubren el cierre con escena dirty en modo offscreen: cancelar,
descartar, guardar con exito y fallo de guardado. Tambien verifican Undo/Redo
contra `EngineAPI` real en un proyecto temporal. La validacion no automatizada
restante es solo la experiencia visual/interactiva humana de la ventana.
