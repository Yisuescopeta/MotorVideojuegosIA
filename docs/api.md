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
- `login_agent_provider(provider_id, credential_source="user_local", base_url="", model="", api_key="", device_auth=False)`
- `logout_agent_provider(provider_id)`
- `get_agent_provider_status(provider_id="")`
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
- `replace_component_data(entity_name, component_name, data)`
- `remove_component(entity_name, component_name)`
- `edit_component(entity_name, component, property, value)`
- `set_component_enabled(entity_name, component_name, enabled)`

Helpers de componentes oficiales:

- camara: `create_camera2d`, `update_camera2d`, `set_camera_framing`
- input: `create_input_map`, `update_input_map`
- audio: `create_audio_source`, `update_audio_source`
- scripts: `add_script_behaviour`, `update_script_behaviour`, `set_script_public_data`
- render/fisica: `set_sorting_layers`, `set_render_order`, `set_physics_layer_collision`, `set_physics_backend`, `set_rigidbody_constraints`, `set_collision_filter`
- tilemap: `create_tilemap`, `set_tilemap_tile`, `clear_tilemap_tile`, `get_tilemap`, `get_tilemap_layer`, `create_tilemap_layer`, `update_tilemap_layer`, `delete_tilemap_layer`, `set_tilemap_tile_full`, `bulk_set_tilemap_tiles`, `resize_tilemap`, `set_cells_terrain_connect`
- animator: `list_animator_states`, `set_animator_sprite_sheet`, `upsert_animator_state`, `set_animator_state_frames`, `remove_animator_state`, `duplicate_animator_state`, `rename_animator_state`, `set_animator_flip`, `set_animator_speed`, `get_animator_info`, `create_animator_state`

Metadata:

- `set_feature_metadata(key, value)`

Señales declarativas (persistencia en escena):

- `get_signal_metadata()`
- `list_signal_connections_declarative()`
- `add_signal_connection(connection_data)`
- `remove_signal_connection(connection_id)`

En conexiones declarativas con `target.kind == "entity"`, `target.id` se usa
como identidad estable interna cuando esta disponible; `target.name` sigue
aceptado por compatibilidad.

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
- `get_raycast_result(entity_name)`: obtiene el resultado runtime de un RayCast2D como dict
- `set_character_max_slides(entity_name, max_slides)`: setea max_slides en CharacterController2D (default 4, rango 1-8, controla iteraciones de deslizamiento en move_and_slide)
- `floor_stop_on_slope` (bool, default False) configurable via `edit_component(entity, "CharacterController2D", "floor_stop_on_slope", True)`: cuando True, move_and_slide frena la velocidad al instante al contactar el suelo (sin deslizar remanente horizontal). No expone método EngineAPI dedicado; se accede por el campo serializable del componente.

Fisica:

- `query_physics_aabb(left, top, right, bottom)`
- `query_physics_ray(origin_x, origin_y, direction_x, direction_y, max_distance)`
- `query_physics_shape_cast(shape_type, shape_width, shape_height, origin_x, origin_y, direction_x, direction_y, max_distance, shape_params=None)`
  - `shape_type`: `'box'`, `'circle'`, `'capsule'` o `'polygon'`
  - `shape_width` / `shape_height`: tamaño base (diametro para circle/capsule)
  - `shape_params` (dict opcional): parametros explicitos que sobreescriben `shape_width`/`shape_height`. Claves soportadas:
    - `width`, `height` (box)
    - `radius` (circle)
    - `radius`, `height` (capsule)
    - `vertices` (polygon: lista de `[x, y]` locales)
  - El cast usa **barrido continuo con busqueda binaria TOI** (swept collision real), no pasos discretos. Retorna `list[ShapeCastResult]`.
- `query_physics_motion(entity_name, motion_x, motion_y, margin=0.08, recovery_as_collision=False, exclude_entity_names=None, collision_mask=0xFFFFFFFF, collide_with_bodies=True, collide_with_areas=False)`
  - Prueba de movimiento no mutante sobre una entidad. No modifica el Transform ni el estado del mundo. Retorna dict con: `travel_x`, `travel_y`, `remainder_x`, `remainder_y`, `collision_point_x`, `collision_point_y`, `collision_normal_x`, `collision_normal_y`, `collider_velocity_x`, `collider_velocity_y`, `collision_depth`, `collision_safe_fraction`, `collision_unsafe_fraction`, `collision_local_shape`, `collider_id`, `collider_entity_name`, `collider_shape`.
- `apply_force(entity_name, force_x, force_y)`
- `apply_impulse(entity_name, impulse_x, impulse_y)`
- `apply_torque(entity_name, torque)`
- `list_physics_backends()`
- `get_physics_backend_selection()`
- `get_solver_metrics()`: Retorna metricas del solver PGS: `{"warm_start_cache_size": int, "iterations": int, "island_count": int, "sleeping_islands": int}`

#### Ejemplo: aplicar fuerzas a un RigidBody

```python
# Crear entidad con RigidBody
api.create_entity("player", components={"RigidBody": {}, "Collider": {}, "Transform": {}})
api.edit_component("player", "RigidBody", "body_type", "dynamic")
api.edit_component("player", "RigidBody", "mass", 2.0)

# Aplicar fuerza continua (acelera cada frame)
api.apply_force("player", 500.0, 0.0)

# Aplicar impulso instantáneo (cambio de velocidad inmediato)
api.apply_impulse("player", 0.0, -300.0)

# Aplicar torque (rotación)
api.apply_torque("player", 50.0)
```

#### MoveResult2D — Resultado de movimiento de personaje

Estructura de datos devuelta por `PhysicsBackend.move_and_slide()` y
`move_and_collide()`. Contiene la posición y velocidad final tras resolver
colisiones, más flags de estado.

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `position_x`, `position_y` | float | Posición final tras colisiones |
| `velocity_x`, `velocity_y` | float | Velocidad ajustada tras colisiones |
| `on_floor` | bool | True si el cuerpo está sobre una superficie |
| `on_wall` | bool | True si el cuerpo colisiona con una pared |
| `on_ceiling` | bool | True si el cuerpo colisiona con un techo |
| `collision_normal_x/y` | float | Normal de la última colisión |
| `contacts` | list[PhysicsContact] | Contactos generados durante el movimiento |
| `slide_count` | int | Iteraciones de deslizamiento reales (0 si no hubo colisión, 1 en colisión simple, >1 en esquinas/paredes secuenciales) |
| `floor_angle` | float | Ángulo del suelo detectado (rad) |

> **Nota:** `move_and_slide` y `move_and_collide` son contratos internos de
> `PhysicsBackend`. El acceso público para agentes IA es a través de
> `EngineAPI.step()` y el componente `CharacterController2D`, que internamente
> usan el backend configurado.
>
> **Cambio P0-2:** `move_and_slide` en `LegacyAABBPhysicsBackend` fue
> reescrito de barrido por eje separado (horizontal + vertical por iteración)
> a un **bucle de deslizamiento basado en `body_test_motion`** unificado 2D.
> Cada iteración prueba el vector de movimiento completo contra el mundo,
> aplica el `travel` seguro, y proyecta el `remainder` deslizando sobre la
> normal de colisión (Godot `Vector2.slide`). Esto mejora la resolución de
> esquinas y el deslizamiento en paredes diagonales. El nuevo parámetro
> `floor_stop_on_slope` detiene la velocidad al primer contacto con el suelo.
> Se añadió detección de one-way collision basada en normal (Godot-style).

#### MotionResult2D — Resultado de prueba de movimiento (sweep-test no mutante)

`MotionResult2D` es la estructura de datos devuelta por
`PhysicsBackend.body_test_motion()`. Representa el resultado de barrer
(sweep) el collider de una entidad a lo largo de un vector de movimiento **sin
modificar el mundo** — ni el Transform de la entidad ni el estado de colisión.

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `travel_x`, `travel_y` | float | Vector de movimiento seguro recorrido antes de la colisión |
| `remainder_x`, `remainder_y` | float | Porción restante del movimiento original tras la colisión |
| `collision_point_x`, `collision_point_y` | float | Punto de impacto en espacio mundo |
| `collision_normal_x`, `collision_normal_y` | float | Normal de la superficie en el punto de colisión |
| `collider_velocity_x`, `collider_velocity_y` | float | Velocidad del colisionador impactado (útil para colisiones con cuerpos móviles) |
| `collision_depth` | float | Profundidad de penetración |
| `collision_safe_fraction` | float | Fracción del movimiento que se puede recorrer sin colisionar (0.0 = colisión en origen, 1.0 = sin colisión) |
| `collision_unsafe_fraction` | float | Fracción del movimiento restante tras la colisión |
| `collision_local_shape` | int | Índice de la shape local que colisionó (-1 si no aplica) |
| `collider_id` | int | ID de la entidad impactada |
| `collider_entity_name` | str | Nombre de la entidad impactada |
| `collider_shape` | int | Índice de la shape del colisionador impactado |

**Signature del método `body_test_motion` en `PhysicsBackend`:**

```python
def body_test_motion(
    self,
    world: Any,
    entity: Any,
    motion: tuple[float, float],
    margin: float = 0.08,
    recovery_as_collision: bool = False,
    exclude_ids: Optional[list[int]] = None,
    collision_mask: int = 0xFFFFFFFF,
    collide_with_bodies: bool = True,
    collide_with_areas: bool = False,
) -> MotionResult2D:
```

**Parámetros:**
- `world`: mundo activo sobre el que realizar la prueba
- `entity`: entidad cuyo collider se usa como origen del barrido
- `motion`: vector de movimiento `(x, y)` a probar
- `margin`: margen de colisión para broad-phase (default: 0.08)
- `recovery_as_collision`: si `True`, el recovery de penetración cuenta como colisión
- `exclude_ids`: IDs de entidades a excluir de la prueba
- `collision_mask`: máscara de bits para filtrado por capas (default: todas las capas)
- `collide_with_bodies`: colisiona con cuerpos no-trigger (default: `True`)
- `collide_with_areas`: colisiona con áreas/triggers (default: `False`)

> **Relación con `move_and_slide`:** `body_test_motion` es el bloque fundamental
> sobre el que se construye `move_and_slide`. Mientras que `move_and_slide`
> itera múltiples veces (resolviendo colisiones, deslizando y repitiendo hasta
> `max_slides`), `body_test_motion` realiza una **única prueba no-mutante**.
> Para simular `move_and_slide` manualmente, se puede invocar
> `body_test_motion`, avanzar la entidad el `travel` resultante, ajustar la
> velocidad según la normal, y repetir.

### Area2D — Monitoreo de overlaps

Area2D monitorea cuerpos (RigidBody) y otras áreas que entran/salen de su zona.
Requiere un Collider para definir la forma del área.

**Eventos emitidos vía EventBus:**
- `body_entered` / `body_exited`: cuando un RigidBody entra/sale del área
- `area_entered` / `area_exited`: cuando otra Area2D entra/sale del área

**Payload de eventos:** `{entity_id, other_entity_id, entity_name, other_entity_name}`

```python
# Crear área de daño
api.create_entity("damage_zone", components={"Area2D": {}, "Collider": {}, "Transform": {}})
api.edit_component("damage_zone", "Collider", "width", 100)
api.edit_component("damage_zone", "Collider", "height", 100)
api.edit_component("damage_zone", "Collider", "is_trigger", True)

# Suscribirse a eventos
api.connect_signal("damage_zone", "body_entered", on_body_entered)
```

### RayCast2D — Detección de colisiones por rayo

RayCast2D es un componente que lanza un rayo cada frame desde la posición de
la entidad usando `query_physics_ray` internamente. El sistema
`RayCast2DSystem` (wired en `EngineAPI` y `RuntimeController`) actualiza los
campos runtime automáticamente.

**Campos serializables (autor: `add_component`):**
- `enabled`: activa/desactiva el raycast (default: `true`)
- `cast_to_x`, `cast_to_y`: dirección y distancia del rayo (default: `0, 50`)
- `collision_mask`: bitmask de capas con las que colisiona (default: `1`)
- `collide_with_areas`: colisiona con áreas (default: `false`)
- `collide_with_bodies`: colisiona con bodies (default: `true`)
- `exclude_parent`: excluye la entidad padre del resultado (default: `true`)

**Campos runtime (lectura tras cada frame):**
- `is_colliding`: `true` si hay colisión
- `collision_point_x`, `collision_point_y`: punto de impacto
- `collision_normal_x`, `collision_normal_y`: normal de la superficie
- `collider_entity`: nombre de la entidad con la que colisionó

```python
api.add_component("player", "RayCast2D", {
    "cast_to_x": 0,
    "cast_to_y": 100,
    "collision_mask": 1
})
# El sistema actualiza is_colliding, collision_point_*, etc. cada frame
```

El sistema `RayCast2DSystem` aplica los filtros configurados en cada frame, en
este orden:

1. `exclude_parent`: descarta hits contra la propia entidad y sus hijos
   (por `parent_name`)
2. `collide_with_areas`: si es `false`, descarta hits con `is_trigger=True`
3. `collide_with_bodies`: si es `false`, descarta hits con `is_trigger=False`
4. `collision_mask`: descarta entidades cuya capa (`CollisionFilter2D.layer`)
   no esté incluida en la máscara de bits. Si la entidad golpeada no tiene
   `CollisionFilter2D`, se asume capa `1`.

#### Consultar resultados runtime con `get_raycast_result`

`get_raycast_result(entity_name)` expone los campos runtime del RayCast2D
como un diccionario plano:

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `is_colliding` | bool | `true` si hay colisión este frame |
| `collision_point_x`, `collision_point_y` | float | Punto de impacto |
| `collision_normal_x`, `collision_normal_y` | float | Normal de la superficie |
| `collider_entity` | str | Nombre de la entidad golpeada |

Si la entidad no existe, no tiene `RayCast2D` o el runtime no está activo,
retorna `{}`.

```python
result = api.get_raycast_result("player")
if result.get("is_colliding"):
    print(f"Colisión con: {result['collider_entity']}")
```

### NavigationObstacle2D — Obstáculo estático para navegación

Componente data-only que marca una entidad como obstáculo para el sistema de
avoidance de `NavigationAgentSystem`.

**Campos serializables:**
- `radius`: radio del obstáculo (default: `0.0`)
- `affect_avoidance`: si afecta el cálculo de avoidance (default: `true`)

No requiere configuración runtime ni expone métodos públicos adicionales.
`NavigationAgentSystem` consume estos datos cada frame.

```python
api.add_component("enemy", "NavigationObstacle2D", {
    "radius": 32.0,
    "affect_avoidance": True
})
```

### RigidBody contact_monitor — Monitoreo de contactos runtime

`RigidBody` expone monitoreo de contactos estilo Godot, activado por campos
serializables y consultable mediante métodos runtime.

**Campos serializables (via `add_component` o `set_rigidbody_property`):**

| Campo | Tipo | Default | Descripción |
|-------|------|---------|-------------|
| `contact_monitor` | bool | `false` | Activa el tracking por frame |
| `max_contacts_reported` | int | `0` | Máx. contactos a reportar (`0` = deshabilitado) |
| `physics_material_override_path` | str | `""` | Ruta a PhysicsMaterial `.json` para sobreescribir fricción/rebote |

**Métodos públicos runtime (solo durante PLAY):**
- `get_colliding_bodies(entity_name) -> list[int]`: IDs de entidades en contacto este frame.
- `get_contact_count(entity_name) -> int`: Número de contactos activos.

Ambos wrappers delegan en `RigidBody.get_colliding_bodies()` / `get_contact_count()`
de la entidad indicada. Retornan `[]` y `0` respectivamente si la entidad no existe,
no tiene `RigidBody`, o `contact_monitor` está desactivado.

```python
api.create_entity("player", components={"RigidBody": {}, "Collider": {}, "Transform": {}})
api.edit_component("player", "RigidBody", "body_type", "dynamic")
api.edit_component("player", "RigidBody", "contact_monitor", True)
api.edit_component("player", "RigidBody", "max_contacts_reported", 10)

# En PLAY, tras colisionar:
bodies = api.get_colliding_bodies("player")
count = api.get_contact_count("player")
```

**Comportamiento (anti-humo):**
- `contact_monitor=false` o `max_contacts_reported=0`: sin tracking.
- Solo colisiones reales (no triggers) registran contactos.
- Los contactos se limpian cada frame — no persisten entre frames.

### CollisionFilter2D — Filtrado por capas

Controla qué entidades colisionan entre sí usando máscaras de bits (uint32).
Adaptado del sistema collision_layer/collision_mask de Godot.

- **layer**: bitmask que define en qué capas está la entidad (default: 1 = capa 1)
- **mask**: bitmask que define con qué capas colisiona (default: 0xFFFFFFFF = todas)

**Regla de colisión:** `(A.mask & B.layer) != 0 AND (B.mask & A.layer) != 0`

```python
# Entidad en capa 1 (bit 0), colisiona solo con capa 1
api.set_collision_filter("player", layer=1, mask=1)

# Entidad en capa 2 (bit 1), colisiona solo con capa 2
api.set_collision_filter("enemy", layer=2, mask=2)

# player (layer=1, mask=1) vs enemy (layer=2, mask=2):
# player.mask & enemy.layer = 1 & 2 = 0     ❌
# enemy.mask & player.layer = 2 & 1 = 0     ❌
# Resultado: NO colisionan
```

La CLI oficial expone verificacion headless stateless sobre estos metodos:

```bash
py -m motor runtime play --project . --headless --json
py -m motor runtime step --project . --frames 300 --json
py -m motor runtime stop --project . --json
```

Cada invocacion inicializa `EngineAPI`, carga una escena mediante superficies
publicas y sale sin guardar mutaciones runtime como authoring state.

Señales runtime:

- `connect_signal(source_id, signal_name, callback, flags=None, binds=None, connection_id=None, description="", target_id=None)`
- `emit_signal(source_id, signal_name, *args, **kwargs)`
- `disconnect_signal(connection_id)`
- `list_signal_connections(source_id=None, signal_name=None)`

Grupos:

- `get_group_entities(group_name)`
- `get_entities_in_group(group_name)`
- `get_first_in_group(group_name)`
- `is_in_group(entity_name, group_name)`
- `count_group(group_name)`
- `get_entity_groups(entity_name)`
- `add_entity_to_group(entity_name, group_name)`
- `remove_entity_from_group(entity_name, group_name)`
- `call_group(group_name, method_name, *args, **kwargs)`
- `emit_group(group_name, signal_name, *args, **kwargs)`

Servicios globales y autoloads:

- `get_service(name)`
- `has_service(name)`
- `register_service_runtime(name, service)`
- `register_service_builtin(name, service)`

Contrato de uso:

- `connect_signal` crea conexiones sobre `SignalRuntime` del runtime activo y espera un callable Python directo.
- `list_signal_connections` devuelve conexiones runtime activas serializadas a diccionario.
- `add_entity_to_group` y `remove_entity_from_group` persisten el cambio via `SceneManager` cuando el motor esta en `EDIT`.
- En `PLAY`, las mutaciones de grupos afectan solo al `World` runtime activo.
- `get_service` y `has_service` consultan el `RegistroServicios` del runtime actual, incluyendo builtins y servicios de la sesion de juego.

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
- `list_project_scenes()`
- `to_project_relative_path(path)`
- `resolve_project_path(path)`
- `get_startup_scene()`
- `set_startup_scene(path)`
- `run_ai_compliance(strict=False)`

Editor:

- `list_editor_themes()`
- `get_active_editor_theme()`
- `set_active_editor_theme(name)`
- `export_editor_theme(path, name=None)`
- `import_editor_theme(path, activate=True)`

El tema activo del editor se persiste en `.motor/editor_state.json` bajo
`preferences.editor_theme`. No forma parte del schema de escena.

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
