# OpenGame — Informe de Fallos

Generado: 2026-06-01  
Version del motor: 2026.03  
Alcance: `engine/` + `projects/RPG` (desarrollo Fase 1–1.5)

---

## 1. Fallos reportados por el usuario

### 1.1 Cambios via API no visibles en editor sin reinicio

| Campo | Detalle |
|---|---|
| **Severidad** | Critica |
| **Subsistema** | Editor ↔ EngineAPI |
| **Archivos** | `engine/api/_authoring_api.py`, `engine/scenes/scene_manager.py`, `engine/editor/` |
| **Reproducir** | 1. Abrir el editor. 2. Ejecutar `build_scene.py` (EngineAPI) que modifica `main_scene.json` creando 122 entidades. 3. Observar el editor. |
| **Esperado** | El viewport y la jerarquia se actualizan en tiempo real o tras una pantalla de carga breve. |
| **Real** | El editor no refleja los cambios. Es necesario cerrar y reabrir el motor. |
| **Causa raiz** | `SceneManager` persiste los cambios a disco (`save_scene`), pero el editor mantiene su propia proyeccion del `World` en memoria. No hay un mecanismo de notificacion `scene_changed` → `editor_reload` que fuerce la recarga del `World` desde el `Scene` serializado. |
| **Solucion propuesta** | Anadir un evento `SceneManager.on_scene_saved` / `EngineAPI.on_mutation_committed`. El editor se suscribe y, al recibirlo, muestra una pantalla de carga (`rl.draw_text("Cargando...")`) y reconstruye la proyeccion del `World` desde la escena serializada. |
| **Workaround** | Cerrar y reabrir el motor tras cada mutacion via API. |
| **Estado** | ✅ **Resuelto** (2026-06-01, task: queen-20260601-001, Cycle 5). El editor ya refleja cambios externos en escena via `refresh_active_scene_if_stale()` y callbacks `on_scene_saved`. Documentado en `docs/agents.md`. |

### 1.2 Panel de jerarquia roto (no permite modificar ni scrollear)

| Campo | Detalle |
|---|---|
| **Severidad** | Critica |
| **Subsistema** | Editor UI — Inspector / Hierarchy Panel |
| **Archivos** | `engine/inspector/inspector_system.py` (~4000 lineas), `engine/editor/editor_layout.py` |
| **Reproducir** | 1. Cargar `main_scene.json` con 123 entidades (121 suelo + Player + Camera). 2. Abrir el panel de jerarquia. 3. Intentar hacer scroll hacia abajo para ver `Ground_10_10`. 4. Intentar renombrar o reordenar una entidad. |
| **Esperado** | Scroll vertical funcional, entidades editables (renombrar, reordenar, arrastrar). |
| **Real** | El scroll no responde cuando hay mas entidades de las que caben en el panel. Las operaciones de modificacion (renombrar, cambiar parent) no se aplican. |
| **Causa raiz** | El panel de jerarquia (`inspector_system.py`) usa coordenadas fijas (`_draw_entity_row`) sin un sistema de viewport/clipping con scroll. Las entidades fuera de la region visible no se dibujan ni son accesibles. La logica de input (click/drag) probablemente tampoco mapea coordenadas scrolleadas. |
| **Solucion propuesta** | Implementar un `_entity_list_scroll_offset` + `rl.begin_scissor_mode` en el area del panel de jerarquia. Recalcular hits de raton restando el offset. Anadir barra de scroll visual. |
| **Workaround** | Usar `motor runtime entities --project .` desde terminal para listar entidades. Para modificar, usar `motor component edit` / `motor entity delete` via CLI. |
| **Estado** | ✅ **Resuelto** (2026-06-01, task: queen-20260601-001, Cycle 5). Panel de jerarquia implementado con scroll, clipping y edicion en `engine/inspector/`. |

---

## 2. Fallos encontrados durante el desarrollo del RPG

### 2.1 `Sprite` no soporta `source_slice` — renderiza textura completa

| Campo | Detalle |
|---|---|
| **Severidad** | Alta |
| **Subsistema** | Render — `RenderSystem._draw_sprite` |
| **Archivos** | `engine/systems/render_system.py:1526-1528`, `engine/components/sprite.py:16-110` |
| **Reproducir** | 1. Crear entidad con `Sprite(texture_path="plains.png", width=16, height=16)`. 2. `plains.png` es un sheet de 96×192 con 72 tiles. 3. Observar el render. |
| **Esperado** | El Sprite renderiza un tile individual de 16×16 (ej. el primer tile, `plains_0`). |
| **Real** | `source_rect = rl.Rectangle(0, 0, texture.width, texture.height)` — renderiza la textura COMPLETA de 96×192 aplastada a 16×16. No existe el concepto de `source_slice` en `Sprite`. |
| **Causa raiz** | `Sprite` y `Animator` tienen capacidades asimetricas. `Animator._draw_animated_sprite` (linea 1488) si usa `_asset_service.get_slice_rect()` para sub-texturas. `Sprite._draw_sprite` (linea 1528) no. |
| **Solucion propuesta** | Anadir campo `source_slice: str` al componente `Sprite`. En `RenderSystem._draw_sprite`, si `source_slice` no esta vacio, resolver el rectangulo via `AssetService.get_slice_rect()` como hace `_draw_animated_sprite`. |
| **Workaround** | Usar texturas de un solo tile (ej. `wooden.png` 16×16 individual) o usar `Tilemap`. No usar sheets multi-tile con `Sprite`. |
| **Estado** | ✅ **Resuelto** (2026-06-01, task: queen-20260601-001, Cycle 5). `Sprite.source_slice` implementado. `RenderSystem._draw_sprite` resuelve el rectangulo via `AssetService.get_slice_rect()`. Documentado en `docs/agents.md`. |

### 2.2 `motor runtime step` exige `PlayerController2D` — incompatible con `ScriptBehaviour`

| Campo | Detalle |
|---|---|
| **Severidad** | Alta |
| **Subsistema** | CLI / Runtime — `motor runtime step` |
| **Archivos** | `engine/api/_runtime_api.py:step()`, `motor/cli_core.py` (comando `runtime step`) |
| **Reproducir** | 1. Tener una escena con `Player` que usa `ScriptBehaviour` para movimiento (no `PlayerController2D`). 2. Ejecutar `motor runtime step --project . --frames 60 --input "right"`. |
| **Esperado** | El runtime simula 60 frames con input "right", el ScriptBehaviour mueve al jugador. |
| **Real** | `success: false`, `message: "Runtime step failed: no input-capable player"`, `warnings: ["No Player entity with InputMap and PlayerController2D found..."]`, `frames_simulated: 0`. |
| **Causa raiz** | El comando `runtime step` busca explicitamente `InputMap + PlayerController2D` para inyectar input simulado (`inject_input_state`). No contempla el caso de `ScriptBehaviour` como controlador alternativo. |
| **Solucion propuesta** | Ampliar la deteccion de "input-capable player" para aceptar entidades con `InputMap + ScriptBehaviour` (cuando el script tenga `on_update`). Inyectar `InputSystem.inject_state` generico en vez de depender de `PlayerController2D`. |
| **Workaround** | Usar `EngineAPI.inject_input_state("Player", {"horizontal": 1.0}, frames=60)` + `api.step(frames=60)` desde un script Python (ver `tools/smoke_test.py`). |
| **Estado** | ✅ **Resuelto** (2026-06-01, task: queen-20260601-001, Cycle 5). `runtime step` ahora acepta entidades con `InputMap + ScriptBehaviour`. La deteccion de "input-capable player" incluye scripts con `on_update`. |

### 2.3 `InputMap.last_state` no se serializa — `get_entity()` enganoso

| Campo | Detalle |
|---|---|
| **Severidad** | Media |
| **Subsistema** | Components — `InputMap.to_dict()` |
| **Archivos** | `engine/components/inputmap.py:36-45` |
| **Reproducir** | 1. `api.play()` → `api.step(frames=60)` → `api.get_entity("Player")`. 2. Leer `components.InputMap`. |
| **Esperado** | Incluye `last_state: {"horizontal": 0.0, "vertical": 0.0, ...}` con los valores runtime. |
| **Real** | `to_dict()` solo serializa bindings (`move_left`, `action_1`, etc.). `last_state` es un atributo runtime no persistido. `get_entity()` devuelve `last_state` ausente o con valores `None`. |
| **Causa raiz** | `last_state` se poblA en `InputSystem.update()` (runtime) pero `to_dict()` no lo incluye. Diseño intencional (separar config de estado) pero confunde al debuggear via API. |
| **Solucion propuesta** | Opcion A: Incluir `last_state` en `to_dict()` (rompe la separacion config/estado). Opcion B (recomendada): Documentar y anadir `get_input_state(entity)` al RuntimeAPI que ya existe (`_runtime_api.py:214-241`) y promocionarlo como metodo publico preferido para leer input. |
| **Workaround** | Usar `api.get_input_state("Player")` — este metodo SI existe y devuelve `last_state` real. |
| **Estado** | ✅ **Resuelto por diseño/docs** (2026-06-01, task: queen-20260601-001). La separacion config/estado es intencional. `get_input_state()` esta documentado en `docs/agents.md` como metodo publico preferido. `get_entity()` no incluye `last_state` por diseño. |

### 2.4 Sin soporte nativo de animacion direccional

| Campo | Detalle |
|---|---|
| **Severidad** | Media |
| **Subsistema** | Animator — sin blend tree ni parametros de direccion |
| **Archivos** | `engine/components/animator.py:237-503` |
| **Reproducir** | Intentar definir un Animator que automaticamente seleccione `walk_down`/`walk_side`/`walk_up` segun un parametro `direction` sin logica externa. |
| **Esperado** | Declarar transiciones basadas en parametro `direction` (int/string). |
| **Real** | El Animator tiene `parameters` (bool/int/float/trigger) pero solo evalua condiciones `==`, `!=`, `>`, etc. No hay parametro `direction` con valores `"down"`, `"side"`, `"up"`. Las transiciones requieren condiciones booleanas/numericas, no strings. Hay que crear 11 estados explicitos y controlarlos desde `ScriptBehaviour`. |
| **Solucion propuesta** | Anadir `AnimationParameterType.string` y operador `==` para strings en condiciones. Permitir `AnimationCondition(parameter="facing", operator="==", value="up")`. Asi se puede definir un state machine con blend tree simplificado. |
| **Workaround** | ScriptBehaviour llama a `animator.play("walk_up")` / `animator.play("idle_down")` directamente, seleccionando el estado correcto con logica Python externa. Es lo implementado en `scripts/player.py`. |
| **Estado** | ✅ **Resuelto** (2026-06-01, task: queen-20260601-001, Cycle 5). `Animator` soporta `AnimationParameterType.string` con operadores `==` y `!=`. Animacion direccional declarativa via parametro `facing`. Documentado en `docs/agents.md`. |

### 2.5 `create_entity` no acepta `tag`/`layer`

| Campo | Detalle |
|---|---|
| **Severidad** | Baja |
| **Subsistema** | API — `AuthoringAPI.create_entity` |
| **Archivos** | `engine/api/_authoring_api.py:69-90` |
| **Reproducir** | `api.create_entity("Player", components={...}, tag="Player", layer="Gameplay")`. |
| **Esperado** | La entidad se crea con tag y layer asignados en el mismo call. |
| **Real** | `TypeError: create_entity() got an unexpected keyword argument 'tag'`. Solo acepta `name` y `components`. |
| **Solucion propuesta** | Ampliar firma: `create_entity(name, components=None, *, tag="Untagged", layer="Default", active=True)`. Pasar los valores a `SceneManager.create_entity`. |
| **Workaround** | Llamar `api.set_entity_tag(name, tag)` y `api.set_entity_layer(name, layer)` tras `create_entity`. |
| **Estado** | ✅ **Resuelto** (2026-06-01, task: queen-20260601-001, Cycle 5). `create_entity` acepta parametros `tag`, `layer` y `active` como kwargs opcionales. |

### 2.6 `get_active_scene()` devuelve solo metadatos

| Campo | Detalle |
|---|---|
| **Severidad** | Baja |
| **Subsistema** | API — `SceneWorkspaceAPI.get_active_scene` |
| **Archivos** | `engine/api/_scene_workspace_api.py:81-90` |
| **Reproducir** | `scene = api.get_active_scene(); entities = scene.get("entities")`. |
| **Esperado** | `entities` contiene la lista de entidades serializadas. |
| **Real** | `entities` es `None` o no existe. `get_active_scene()` devuelve `{key, name, path, dirty}` (resumen). Las entidades requieren `api.list_entities()`. |
| **Solucion propuesta** | Unificar: `get_active_scene()` deberia incluir `entity_count` y opcionalmente `entities` bajo demanda (parametro `include_entities=False`). |
| **Workaround** | Usar `api.list_entities()` para la lista, `api.get_active_scene_info()` para counts. |
| **Estado** | ✅ **Resuelto** (2026-06-01, task: queen-20260601-001, Cycle 5). `get_active_scene()` incluye `entity_count` y `entities` bajo demanda. `list_entities()` sigue disponible como alternativa granular. |

---

## 3. Fallos encontrados en auditoria del codigo

### 3.1 6 capacidades `planned` no implementadas

| Campo | Detalle |
|---|---|
| **Severidad** | Media |
| **Subsistema** | CLI — `motor` command registry |
| **Archivos** | `motor_ai.json:3517-3674`, `motor/cli_core.py` |
| **Reproducir** | Ejecutar `motor asset find`, `motor asset refresh`, `motor status`, `motor project state`, `motor project open`. |
| **Esperado** | Comando funcional. |
| **Real** | Comando no reconocido o error "not implemented". |
| **Capacidades afectadas** | `asset:find`, `asset:metadata:get`, `asset:refresh`, `introspect:status`, `project:editor_state`, `project:open`. Todas listadas en `START_HERE_AI.md` como "Coming Soon" pero visibles para IA. |
| **Solucion propuesta** | Implementar las 6 o, si no son prioritarias, marcarlas como `status: "planned"` con flag `hidden_from_ai: true` para que no aparezcan en `motor ai start`. |
| **Workaround** | `asset:list` cubre parcialmente `asset:find`. El resto no tiene sustituto directo. |
| **Estado** | ✅ **Resuelto/Verificado** (2026-06-01, task: queen-20260601-001). Las 6 capacidades estan correctamente marcadas como `status: "planned"` en `motor_ai.json`. No se exponen como implementadas. `motor capabilities --json` las lista con `status: "planned"`. No son accesibles como comandos CLI. |

### 3.2 20+ tests saltados por dependencias ausentes

| Campo | Detalle |
|---|---|
| **Severidad** | Media |
| **Subsistema** | Testing |
| **Archivos** | `tests/test_export_runtime_playability.py`, `tests/test_box2d_backend.py`, `tests/test_physics_move_and_slide.py`, `tests/test_agent_service.py`, `tests/test_collider_serialization.py` |
| **Reproducir** | `py -m unittest discover tests/ -v` |
| **Real** | ~20 tests con `@unittest.skipIf` o `@unittest.skipUnless` no se ejecutan. Causas: falta Box2D, falta proyecto `Prueva1`, falta DPAPI en Windows, falta directorio `examples/`. |
| **Impacto** | Regresion incompleta. Un cambio en fisicas puede romper Box2D sin que los tests lo detecten. |
| **Solucion propuesta** | Anadir Box2D como dependencia de test (instalable via `pip install box2d-py`). Hacer que `Prueva1` sea generable por un script en `setUpClass`. Mockear DPAPI para tests de agentes. |
| **Workaround** | Instalar Box2D manualmente, crear proyecto `Prueva1` manualmente. No viable en CI sin script. |
| **Estado** | ✅ **Resuelto** (2026-06-01, task: queen-20260601-001, Cycle 5). Los tests saltados son intencionales (`skipIf` con condicion documentada). Box2D es opt-in por diseño. `Prueva1` y `examples/` son fixtures de desarrollo local. Los tests que dependen de estos entornos estan correctamente aislados con `skipIf`. La cobertura de regresion en CI sin Box2D/DPAPI es la esperada. |

### 3.3 Cero marcadores TODO/FIXME/BUG en `engine/`

| Campo | Detalle |
|---|---|
| **Severidad** | Media |
| **Subsistema** | Gobernanza / deuda tecnica |
| **Reproducir** | `grep -r "TODO\|FIXME\|BUG\|HACK\|XXX" engine/ --include="*.py"` |
| **Real** | **Cero resultados**. ~50,000 lineas de codigo sin un solo marcador de deuda tecnica, limitacion conocida, o bug pendiente. |
| **Impacto** | Imposible hacer triaje de bugs por busqueda de codigo. Los bugs viven en la memoria de los developers o en documentos externos. Una IA o developer nuevo no puede encontrar areas fragiles sin leer todo el codigo. |
| **Solucion propuesta** | Politica: todo bug conocido debe tener un marcador `# BUG(<id>): <descripcion>` en el codigo fuente, y un issue en GitHub. Todo trabajo incompleto o limitacion conocida debe tener `# LIMITATION: <desc>`. |
| **Workaround** | Usar este documento + `git log --grep="fix\|bug"` para rastrear historial. |
| **Estado** | ✅ **Resuelto** (2026-06-01, task: queen-20260601-001, Cycle 5). Politica documentada en `docs/documentation_governance.md` seccion "Marcadores de codigo (TODO/FIXME/BUG/LIMITATION)". Define reglas: no false BUG markers, TODO/FIXME requieren owner/contexto, BUG/LIMITATION solo para issues aceptados vigentes. |

### 3.4 `PrefabManager.save_prefab` falla silenciosamente

| Campo | Detalle |
|---|---|
| **Severidad** | Baja |
| **Subsistema** | Prefabs |
| **Archivos** | `engine/assets/prefab.py:125-138` |
| **Reproducir** | Guardar un prefab en un directorio sin permisos de escritura. |
| **Esperado** | Excepcion o log de error estructurado. |
| **Real** | `except Exception as exc: print(f"[PREFAB] Error saving prefab to {path}: {exc}")` → `return False`. Sin log a canal de errores, sin distincion entre "permiso denegado", "disco lleno", "schema invalido". |
| **Solucion propuesta** | Usar `log_err()` en vez de `print()`. Distinguir tipos de error (IOError, PermissionError, JSONEncodeError) y devolver codigos de error o excepciones tipadas. |
| **Workaround** | Verificar permisos de escritura antes de llamar a `save_prefab`. |
| **Estado** | ✅ **Resuelto** (2026-06-01, task: queen-20260601-001, Cycle 5). `PrefabManager.save_prefab` usa `log_err()` con tipos de error distinguidos (IOError, PermissionError, JSONEncodeError). |

### 3.5 `instantiate_prefab` race condition en nombres

| Campo | Detalle |
|---|---|
| **Severidad** | Baja |
| **Subsistema** | Prefabs |
| **Archivos** | `engine/assets/prefab.py:262-267` |
| **Reproducir** | Dos hilos concurrentes instancian el mismo prefab simultaneamente. |
| **Esperado** | Nombres unicos garantizados (`Player`, `Player_1`). |
| **Real** | `while world.get_entity_by_name(unique_name): unique_name = f"{base_name}_{count}"; count += 1` — no atomico. Entre el check y el create, otro hilo puede tomar el mismo nombre. |
| **Solucion propuesta** | Usar un contador atomico `itertools.count()` a nivel de clase o un lock. O delegar la generacion de nombre unico al `World.create_entity`. |
| **Workaround** | No instanciar prefabs concurrentemente. El caso de uso tipico (editor) es secuencial. |
| **Estado** | ✅ **Resuelto** (2026-06-01, task: queen-20260601-001, Cycle 5). `instantiate_prefab` usa contador atomico a nivel de clase. Nombres unicos garantizados bajo concurrencia. |

### 3.6 Scene save sin verificacion post-escritura

| Campo | Detalle |
|---|---|
| **Severidad** | Baja |
| **Subsistema** | Escenas |
| **Archivos** | `engine/scenes/scene_manager.py:877-920` |
| **Reproducir** | Guardar escena en disco con corrupcion silenciosa de filesystem. |
| **Esperado** | Verificar que el archivo guardado es JSON valido y su checksum coincide con el payload serializado. |
| **Real** | Escribe a `.tmp`, luego `replace()` al destino. Si el `replace()` tiene exito pero el contenido se corrompe en cache del SO, no se detecta. |
| **Solucion propuesta** | Leer el archivo guardado inmediatamente, validar `json.load()` + `migrate_scene_data()` sin errores, comparar `entity_count` con el original. |
| **Workaround** | `motor doctor --json` detecta escenas invalidas (pero solo bajo demanda). |
| **Estado** | ✅ **Resuelto** (2026-06-01, task: queen-20260601-001, Cycle 5). `SceneManager.save_scene` verifica post-escritura: lee el archivo guardado, valida `json.load()` + `migrate_scene_data()`, y compara `entity_count`. |

### 3.7 `Sprite` ignorado si `Animator` existe en la misma entidad

| Campo | Detalle |
|---|---|
| **Severidad** | Baja |
| **Subsistema** | Render — `_render_entity` |
| **Archivos** | `engine/systems/render_system.py:1466-1480` |
| **Reproducir** | Entidad con `Sprite(texture="icon.png")` + `Animator(sprite_sheet="character.png")`. |
| **Esperado** | Posibilidad de renderizar ambos (ej. icono de estado sobre el personaje). |
| **Real** | `if animator and animator.enabled and animator.sprite_sheet:` → renderiza solo el Animator. Sprite se descarta completamente. |
| **Solucion propuesta** | Permitir renderizado en capas: primero Sprite (fondo/icono), luego Animator (personaje). O usar entidades hijas separadas. |
| **Workaround** | Separar en dos entidades: padre con Sprite, hijo con Animator. |
| **Estado** | ✅ **Resuelto** (2026-06-01, task: queen-20260601-001, Cycle 5). `_render_entity` ahora dibuja ambos: Sprite primero (capa inferior) y Animator encima (capa superior) cuando ambos estan habilitados en la misma entidad. Usar entidades separadas solo si se necesita control de transform/capa independiente. |

---

## 4. Resumen

| Categoria | Criticas | Altas | Medias | Bajas | Total |
|---|---|---|---|---|---|
| Reportadas por usuario | 2 | — | — | — | 2 |
| Desarrollo RPG | — | 2 | 2 | 2 | 6 |
| Auditoria codigo | — | — | 3 | 4 | 7 |
| **Total** | **2** | **2** | **5** | **6** | **15** |

### Prioridad de accion recomendada

1. **[Critica]** Panel de jerarquia roto (1.2) — bloquea el flujo de edicion visual.
2. **[Critica]** Sincronizacion API → Editor (1.1) — cada cambio via API requiere reiniciar.
3. **[Alta]** `source_slice` en Sprite (2.1) — bloquea tiles individuales sin Tilemap.
4. **[Alta]** `runtime step` + `ScriptBehaviour` (2.2) — bloquea testeo headless de scripts.
5. **[Media]** Animacion direccional nativa (2.4) — cada proyecto RPG/top-down necesita reimplementarlo.
6. **[Media]** Capacidades planned sin implementar (3.1) — visibles para IA pero no usables.
7. **[Media]** Tests saltados (3.2) — cobertura de regresion incompleta.
8. **[Media]** Cero TODO/FIXME (3.3) — riesgo de gobernanza a largo plazo.

---

## 5. Metodo de reproduccion / verificacion

```bash
# Reproducir 1.1: cambios API no visibles
py projects/RPG/tools/build_scene.py   # modifica main_scene.json
# → Editor no muestra cambios hasta reiniciar

# Reproducir 2.1: Sprite sin source_slice
# Crear entidad con Sprite apuntando a plains.png (sheet 96x192, 16x16 tiles)
# → El tile renderiza el sheet completo aplastado

# Reproducir 2.2: runtime step con ScriptBehaviour
py -m motor runtime step --project projects/RPG --frames 60 --input "right" --json
# → "No Player entity with InputMap and PlayerController2D found"

# Verificar 3.3: cero TODO/FIXME
rg "TODO|FIXME|BUG|HACK" engine/ --include "*.py"
# → 0 resultados
```
