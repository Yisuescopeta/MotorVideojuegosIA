# EngineAPI publica

`EngineAPI` es la fachada publica estable para agentes, tests, CLI y
automatizacion. La clase vive en `engine/api/engine_api.py` y delega en
componentes por dominio.

```python
from engine.api import EngineAPI

api = EngineAPI(project_root=".")
try:
    api.load_scene("levels/main_scene.json")
    api.create_entity("Player", components={"Transform": {"x": 100, "y": 200}})
    api.save_scene()
finally:
    api.shutdown()
```

## Constructor y ciclo de vida

```python
EngineAPI(
    project_root: str | None = None,
    global_state_dir: str | None = None,
    sandbox_paths: bool = False,
    auto_ensure_project: bool = True,
    read_only: bool = False,
)
```

- `project_root`: root del proyecto. Si no se pasa, usa el cwd.
- `sandbox_paths`: bloquea rutas fuera del proyecto para operaciones que resuelven paths.
- `auto_ensure_project`: permite crear/asegurar estructura de proyecto al iniciar.
- `read_only`: usado por diagnosticos como `motor doctor`.
- `shutdown()`: solicita cierre del runtime headless.

`EngineAPI` inicializa `HeadlessGame`, `SceneManager`, `ProjectService`,
`AssetService`, sistemas runtime y el backend fisico opcional `box2d` cuando
esta disponible.

Internamente, `EngineAPI` ahora normaliza sus colaboradores sobre un bundle
tipado de runtime y puertos de escena (`authoring` y `workspace`). Esto no
cambia la API publica; solo reduce acoplamiento interno para fases posteriores.

`attach_runtime(...)` conserva firma y sigue siendo la ruta de integracion para
inyectar un runtime/scene manager externos compatibles con ese contrato base.
`EngineAPI.from_runtime(...)` existe solo como helper `experimental/internal
tooling` para adaptadores del editor que necesitan una fachada sobre runtime
vivo sin inicializar un segundo motor headless. No es un constructor core
estable ni debe usarse desde CLI o automatizaciones generales.

## Agente experimental

Fuente: `engine/api/_agent_api.py`.

El agente nativo v2 es una superficie `experimental/tooling` para sesiones
clean-room dentro del motor. Mantiene la API publica de v1, pero internamente
usa un runtime iterativo `provider -> tool_use -> tool_result -> provider`:

- `create_agent_session(permission_mode="confirm_actions", title="", provider_id="fake", model="", temperature=None, max_tokens=None, stream=False)`
- `send_agent_message(session_id, message)`
- `get_agent_session(session_id)`
- `approve_agent_action(session_id, action_id, approved)`
- `cancel_agent_session(session_id)`
- `list_agent_tools()`
- `list_agent_providers()`
- `compact_agent_session(session_id)`
- `get_agent_usage(session_id)`
- `inspect_agent_session(session_id)`

Modos de permiso:

- `confirm_actions`: lectura segura sin confirmacion; escrituras, shell, Git y
  authoring estructurado quedan pendientes de aprobacion.
- `full_access`: ejecuta sin confirmacion, conservando hard guards de rutas,
  carpeta de referencia `Claude Code/`, secretos evidentes y auditoria local.

`list_agent_tools()` devuelve metadatos de cada tool, incluido
`parameters_schema` como JSON Schema minimo para proveedores con function
calling.

El estado de sesiones y auditoria vive en `.motor/agent_state`.
Las sesiones se guardan con `schema_version=2`, transcript serializable y log
de eventos por sesion en `.motor/agent_state/events/`.
Los `session_id` son opacos y se validan antes de resolver rutas locales.
Las sesiones legacy sin `schema_version` se migran de forma explicita al cargar:
se crea backup `.legacy-v1.bak`, se valida el payload, se reconstruyen
`content_blocks`/turnos suspendidos y se registra `session_migrated`. Si el
JSON esta corrupto no se sobrescribe el archivo original.

Provider:

- `fake` es un provider determinista offline de pruebas, marcado como
  `provider_kind=test`, `offline=True`, `test_only=True`.
- `replay` permite tests de contrato multi-turn declarativos sin simular
  inteligencia real.
- `openai` es el primer provider online real de V3a; usa Responses API,
  acepta `OPENAI_API_KEY`, secreto local del agente y login gestionado por
  Codex/OpenAI mediante `credential_source=codex_chatgpt` o
  `credential_source=codex_api_key`.
- `get_agent_provider_status(...)` y `list_agent_providers()` exponen
  `credential_source`, `auth_method`, `runtime_ready`, `codex_cli_available`,
  `codex_home` y `plan_type` cuando aplica.
- Si existe auth gestionada pero no hay bridge reutilizable para el runtime
  actual, `runtime_ready=False` y no hay fallback silencioso a `fake`.
- Un `provider_id` desconocido falla con diagnostico explicito.
- `stream=True` activa eventos `assistant_delta` y persistencia del mensaje final
  cuando el provider soporta streaming.

Shell tool:

- `run_command` mantiene su nombre publico, pero ya no ejecuta shell generica.
- Internamente normaliza a `argv` y usa `subprocess.run(..., shell=False)`.
- Solo acepta perfiles `python_tests`, `motor_cli_read` y probes de lectura
  estrechos; `full_access` no salta esta policy.
- La ejecucion pasa por `AgentCommandRunner`, que confina cwd al proyecto, usa
  env minimo, timeout, limite de output y auditoria local.
- Pipes, redirecciones, chaining, shells, inline Python, comandos Git mutantes,
  comandos destructivos y acceso a `Claude Code/` se bloquean antes de ejecutar.

Memoria y coste:

- `compact_agent_session(...)` y `/compact` generan resumen local sanitizado en
  `.motor/agent_state/memory/`.
- `get_agent_usage(...)` y `/cost` reportan tokens si el provider los devuelve.
- El coste estimado permanece `unknown` si no hay precios configurados; no se
  inventan importes.

## Forma de respuesta

Los metodos de authoring y proyecto suelen devolver `ActionResult`:

```python
{
    "success": True,
    "message": "Entity created",
    "data": {"entity": "Player"}
}
```

Los metodos de consulta devuelven diccionarios o listas serializables.

## Authoring

Fuente: `engine/api/_authoring_api.py`.

Transacciones y cambios:

- `begin_transaction(label="transaction")`
- `apply_change(change)`
- `commit_transaction()`
- `rollback_transaction()`

Entidades:

- `create_entity(name, components=None)`
- `delete_entity(name)`
- `set_entity_active(name, active)`
- `set_entity_tag(name, tag)`
- `set_entity_layer(name, layer)`
- `set_entity_parent(name, parent_name)`
- `create_child_entity(parent_name, name, components=None)`

Componentes:

- `add_component(entity_name, component_name, data=None)`
- `remove_component(entity_name, component_name)`
- `edit_component(entity_name, component, property, value)`
- `set_component_enabled(entity_name, component_name, enabled)`

Helpers de componentes oficiales:

- camara: `create_camera2d`, `update_camera2d`, `set_camera_framing`
- input: `create_input_map`, `update_input_map`
- audio: `create_audio_source`, `update_audio_source`
- scripts: `add_script_behaviour`, `update_script_behaviour`, `set_script_public_data`
- render/fisica: `set_sorting_layers`, `set_render_order`, `set_physics_layer_collision`, `set_physics_backend`, `set_rigidbody_constraints`
- tilemap: `create_tilemap`, `set_tilemap_tile`, `clear_tilemap_tile`, `get_tilemap`, `get_tilemap_layer`, `create_tilemap_layer`, `update_tilemap_layer`, `delete_tilemap_layer`, `set_tilemap_tile_full`, `bulk_set_tilemap_tiles`, `resize_tilemap`
- animator: `list_animator_states`, `set_animator_sprite_sheet`, `upsert_animator_state`, `set_animator_state_frames`, `remove_animator_state`, `duplicate_animator_state`, `rename_animator_state`, `set_animator_flip`, `set_animator_speed`, `get_animator_info`, `create_animator_state`

Metadata:

- `set_feature_metadata(key, value)`

Reglas:

- Los metodos de authoring requieren modo `EDIT`.
- Los componentes publicos deben estar registrados en `engine/levels/component_registry.py`.
- No uses mutacion directa de `edit_world` para flujos publicos nuevos.

## Runtime e inspeccion

Fuente: `engine/api/_runtime_api.py`.

Control runtime:

- `play()`
- `stop()`
- `step(frames=1)`
- `set_seed(seed)`
- `undo()`
- `redo()`

Estado y entidades:

- `get_status()`
- `list_entities(tag=None, layer=None, active=None)`
- `get_entity(name)`
- `get_primary_camera()`
- `get_recent_events(count=50)`

Input, audio y scripts:

- `get_input_state(entity_name)`
- `inject_input_state(entity_name, state, frames=1)`
- `get_audio_state(entity_name)`
- `play_audio(entity_name)`
- `stop_audio(entity_name)`
- `pause_audio(entity_name)`
- `resume_audio(entity_name)`
- `get_script_public_data(entity_name)`

Fisica:

- `query_physics_aabb(left, top, right, bottom)`
- `query_physics_ray(origin_x, origin_y, direction_x, direction_y, max_distance)`
- `list_physics_backends()`
- `get_physics_backend_selection()`

`legacy_aabb` debe permanecer disponible como fallback. `box2d` es opcional.

## Workspace, escenas y prefabs

Fuente: `engine/api/_scene_workspace_api.py`.

Carga y guardado:

- `load_level(path)`
- `load_scene(path)`
- `open_scene(path)`
- `create_scene(name)`
- `save_scene(key_or_path=None, path=None)`

Workspace:

- `list_open_scenes()`
- `get_active_scene()`
- `has_active_scene()`
- `get_active_scene_info()`
- `activate_scene(key_or_path)`
- `close_scene(key_or_path, discard_changes=False)`
- `copy_entity_to_scene(entity_name, target_scene)`

Scene flow:

- `get_feature_metadata()`
- `get_scene_connections()`
- `set_scene_link(entity_name, target_path, flow_key="", preview_label="")`
- `set_scene_connection(key, path)`
- `set_next_scene(path)`
- `set_menu_scene(path)`
- `set_previous_scene(path)`
- `load_next_scene()`
- `load_menu_scene()`
- `load_scene_flow_target(key)`

Prefabs:

- `create_prefab(entity_name, path, replace_original=False, instance_name=None)`
- `instantiate_prefab(path, name=None, parent=None, overrides=None)`
- `unpack_prefab(entity_name)`
- `apply_prefab_overrides(entity_name)`

## Proyecto y assets

Fuente: `engine/api/_assets_project_api.py`.

Proyecto:

- `list_recent_projects()`
- `get_project_manifest()`
- `open_project(path)`
- `get_editor_state()`
- `save_editor_state(data)`

Assets:

- `list_project_assets(search="")`
- `list_project_prefabs()`
- `list_project_scripts()`
- `refresh_asset_catalog()`
- `build_asset_artifacts()`
- `create_asset_bundle()`
- `find_assets(search="", asset_kind="", importer="", extensions=None)`
- `get_asset_reference(locator)`
- `move_asset(locator, destination_path)`
- `rename_asset(locator, new_name)`
- `reimport_asset(locator)`
- `get_asset_metadata(asset_path)`
- `save_asset_metadata(asset_path, metadata)`
- `get_asset_image_size(asset_path)`

Slicing de sprites:

- `create_grid_slices(asset_path, cell_width, cell_height, margin=0, spacing=0, pivot_x=0.5, pivot_y=0.5, naming_prefix=None)`
- `list_asset_slices(asset_path)`
- `preview_auto_slices(asset_path, pivot_x=0.5, pivot_y=0.5, naming_prefix=None, alpha_threshold=1, color_tolerance=12)`
- `create_auto_slices(asset_path, pivot_x=0.5, pivot_y=0.5, naming_prefix=None, alpha_threshold=1)`
- `save_manual_slices(asset_path, slices, pivot_x=0.5, pivot_y=0.5, naming_prefix=None)`

## Debug y profiler

Fuente: `engine/api/_debug_api.py`.

- `reset_profiler(run_label="default")`
- `get_profiler_report()`
- `configure_debug_overlay(draw_colliders=None, draw_labels=None, draw_tile_chunks=None, draw_camera=None, primitives=None)`
- `clear_debug_primitives()`
- `get_debug_geometry_dump(viewport_width=800, viewport_height=600)`

## UI serializable

Fuente: `engine/api/_ui_api.py`.

- `create_canvas(name="Canvas", reference_width=800, reference_height=600, sort_order=0)`
- `create_ui_element(name, parent, rect_transform=None)`
- `set_rect_transform(entity_name, properties)`
- `create_ui_text(name, text, parent, rect_transform=None, font_size=24, alignment="center")`
- `create_ui_button(name, label, parent, rect_transform=None, on_click=None, normal_sprite=None, hover_sprite=None, pressed_sprite=None, disabled_sprite=None, normal_slice="", hover_slice="", pressed_slice="", disabled_slice="", preserve_aspect=True)`
- `create_ui_image(name, parent, sprite, rect_transform=None, slice_name="", preserve_aspect=True, tint=None)`
- `set_button_on_click(entity_name, on_click)`
- `list_ui_nodes()`
- `get_ui_layout(entity_name)`
- `click_ui_button(entity_name)`

`UIButton` conserva el flujo declarativo actual y puede renderizarse por color o
por sprite. `UIImage` representa imagen UI no interactiva con `sprite`,
`slice_name`, `tint` y `preserve_aspect`.

## Uso recomendado para agentes

1. Crea `EngineAPI(project_root=".")`.
2. Carga o crea una escena con metodos de workspace.
3. Aplica cambios persistentes con metodos de authoring.
4. Guarda con `save_scene()`.
5. Usa `play()`, `step()` y consultas runtime para verificacion headless.
6. Llama `shutdown()` al terminar.

No llames internals privados salvo que la tarea sea explicitamente de wiring
interno y este dentro del perimetro permitido por [../AGENTS.md](../AGENTS.md).
