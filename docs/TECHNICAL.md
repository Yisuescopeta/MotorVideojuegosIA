# Referencia tecnica

Esta referencia resume el estado verificable del codigo. Para el contrato
arquitectonico lee [architecture.md](architecture.md); para la taxonomia lee
[module_taxonomy.md](module_taxonomy.md); para serializacion lee
[schema_serialization.md](schema_serialization.md).

## Contrato base

- `scene schema_version = 2`
- `prefab schema_version = 2`
- migraciones `legacy/v1 -> v2`
- validacion posterior a la migracion
- guardado canonico `v2`

`Scene` es persistente. `World` es una proyeccion operativa.

## Componentes registrados

La fuente de verdad para componentes publicos registrados es
`engine/levels/component_registry.py`.

Familias principales:

- Espacial/render: `Transform`, `RectTransform`, `Sprite`, `Animator`, `Camera2D`, `RenderOrder2D`, `RenderStyle2D`.
- Gameplay/fisica: `Collider`, `RigidBody`, `CharacterController2D`, `PlayerController2D`, `Joint2D`, `InputMap`, `AudioSource`, `ScriptBehaviour`.
- Escena, tilemap y UI: `Tilemap`, `SceneLink`, `SceneEntryPoint`, `SceneTransition*`, `Canvas`, `UIText`, `UIButton`, `UIImage`.

No se debe asumir soporte publico para componentes no registrados.

## Runtime y sistemas

El runtime usa `Game` o `HeadlessGame` para coordinar sistemas sobre el mundo
activo. Los sistemas actuales incluyen render, fisica, colisiones, animacion,
input, controladores de personaje/jugador, scripts, audio y UI.

`RenderSystem` conserva el flujo visible actual del render 2D: render graph,
sorting layers, batching base, tilemap chunks, debug geometry y render targets
con fallback seguro cuando no hay backend grafico disponible. `engine/rendering/`
añade una foundation modular con planner/executor tipados para adaptar ese
flujo legacy y preparar fases futuras sin sustituir todavia el sistema actual.
`Animator` mantiene compatibilidad con el flujo actual basado en clips por
nombre (`animations`, `default_state`, `current_state`, `play()` y
`AnimationData.on_complete`) y ahora admite foundation opcional de state
machine de una sola capa:

- `parameters`: definiciones serializables de `bool`, `int`, `float` y `trigger`
- `state_machine`: `entry_state` y nodos por estado con `transitions`
- `transitions`: condiciones declarativas, `has_exit_time`, `exit_time` y
  `force_restart`

Los valores runtime de parametros y triggers no forman parte del payload
serializable del authoring.
`engine/audio/` define la foundation interna del runtime de audio. Expone
contratos runtime (`AudioPlaybackRequest`, `AudioVoiceState`,
`AudioRuntimeEvent`), un `NullAudioBackend` headless-safe y `AudioRuntime`
como nucleo independiente de ECS.

`RenderSystem` mantiene render graph, sorting layers, batching, tilemap chunks,
debug geometry y render targets con fallback seguro cuando no hay backend
grafico disponible.

`UIRenderSystem` renderiza la UI overlay serializable. `UISystem` conserva
layout e interaccion y ahora soporta dos modos de foundation sobre
`RectTransform`:

- `free` para el comportamiento legacy basado en anchors/pivot/anchored offsets
- `vertical_stack` y `horizontal_stack` para distribuir hijos con padding,
  spacing, orden, alineacion y fill/stretch por eje

`UIRenderSystem` sigue resolviendo solo la capa visual para `UIText`,
`UIButton` por color o sprite, y `UIImage`, usando los rects ya calculados por
`UISystem`.

El sistema fisico conserva `legacy_aabb` como fallback obligatorio y registra
`box2d` como backend opcional cuando la dependencia esta disponible.

`AudioSystem` sigue siendo la superficie ECS/runtime compatible y delega en la
foundation interna de `engine/audio/`. El backend real de audio, buses/mixer,
spatial audio completo y la integracion con el `EventBus` global quedan
preparados pero no implementados como contrato actual.

### Secuencia runtime foundation

`Game` y `HeadlessGame` comparten una secuencia interna explicita por frame:

`HeadlessGame` queda tocado solo como adaptador minimo porque `EngineAPI`
inicializa ese runtime y `step()` publica entra por `step_frame()`. Mantener la
misma secuencia evita que el foundation diverja entre runtime grafico y runtime
publico headless.

1. `FIXED_UPDATE`: simulacion runtime con `fixed_dt = 1/60` y acumulador con
   limite de pasos por frame.
2. `UPDATE`: animacion normal o preview y trabajo variable que no entra todavia
   en fixed-step.
3. `POST_UPDATE`: UI runtime/render-like, bookkeeping y transicion
   `STEPPING -> PAUSED`.
4. `RENDER`: solo en el loop grafico; el foundation no cambia `RenderSystem`.

El lifecycle minimo queda asi:

- `EDIT -> PLAY`: clona `runtime_world`, resetea el estado del loop y dispara
  hooks runtime existentes (`on_play`).
- `PLAY/PAUSED -> STEPPING`: fuerza exactamente un `FIXED_UPDATE`.
- `PLAY/PAUSED/STEPPING -> EDIT`: limpia el estado transitorio del loop,
  ejecuta `on_stop` y restaura `edit_world`.

Esto prepara fases posteriores de render/fisica sin abrir callbacks publicos
nuevos ni alterar `EngineAPI`, CLI o schema serializable.

## Reglas y eventos

`EventBus` y `RuleSystem` permiten gameplay declarativo desde datos de escena.

Acciones de reglas soportadas por contrato:

- `set_animation`
- `set_position`
- `destroy_entity`
- `emit_event`
- `log_message`

## Workspace y authoring

`SceneManager` coordina carga/guardado, workspace multi-escena, escena activa,
dirty state, historial, transacciones, `EDIT -> PLAY -> STOP`, operaciones
estructurales y prefabs.

Las rutas recomendadas para cambios persistentes son `SceneManager` y
`EngineAPI`. `sync_from_edit_world()` queda como compatibilidad legacy.

## Foundation del editor

La foundation visual del editor vive en `engine/editor/` y se organiza alrededor
de `EditorShell`, `EditorShellState`, `EditorPanelSlots` y
`EditorSelectionState`.

- `EditorShell` compone layout, jerarquia y paneles montables.
- `EditorLayout` sigue siendo la superficie visual compatible, pero ya no crea
  por si mismo todos los paneles del shell.
- `EditorSelectionState` es estado efimero compartido entre shell, jerarquia e
  interaccion; no reemplaza a `SceneManager`, `World` ni a la ruta canonica de
  authoring.
- El runtime sigue orquestado por `Game`; la costura editor/runtime solo monta
  la foundation del editor y no redefine contratos del motor.
### Foundation incremental de tilemap

`Tilemap` conserva su payload serializable actual y su superficie publica para
compatibilidad con escenas, `EngineAPI`, inspector y runtime existente.

La foundation del dominio vive en `engine/tilemap/model.py`. Esa capa mantiene:

- orden estable de capas por lista
- almacenamiento interno por coordenada tipada
- emision canonica de tiles como lista serializable
- metadata existente de mapa, layer y tile-instance sin introducir schema nuevo

`engine/components/tilemap.py` sigue siendo el componente serializable estable;
usa esa foundation para parseo y serializacion canonica, sin convertirse en un
espejo complejo del dominio ni en una integracion fuerte con editor/runtime. En
runtime mantiene tiles por coordenada `tuple[int, int]` y chunks efimeros con
`version`/`dirty`; ese cache alimenta el render sin cambiar el payload de
escena ni serializar estado runtime.

Esta foundation prepara evolucion futura de metadata por tile, layers y reglas
sin mezclar aun editor visual nuevo ni cambios amplios en runtime/render.
Base tecnica interna compartida:

- `engine/scenes/contracts.py` separa `SceneRuntimePort`,
  `SceneAuthoringPort` y `SceneWorkspacePort` como puertos internos sobre
  `SceneManager`.
- `engine/core/runtime_contracts.py` encapsula el wiring requerido por
  `RuntimeController` en `RuntimeControllerContext`.
- `engine/api/_contracts.py` tipa el bundle interno que `EngineAPI` expone a
  sus colaboradores privados.

## EngineAPI publica

`EngineAPI` es la fachada estable para agentes, tests, CLI y automatizacion.
Internamente delega por dominios: authoring, runtime, workspace y scene flow,
assets/proyecto, debug/profiler y UI serializable.

Desde Fase 1, esos colaboradores privados consumen puertos tipados de escena y
runtime en vez de depender de `Game` o `SceneManager` completos cuando no hace
falta. La semantica publica no cambia.

```python
from engine.api import EngineAPI

api = EngineAPI(project_root=".")
api.load_level("levels/platformer_test_scene.json")
api.set_entity_tag("Hero", "Player")
api.play()
api.step(2)
events = api.get_recent_events(count=10)
selection = api.get_physics_backend_selection()
api.shutdown()
```

La referencia agrupada vive en [api.md](api.md).

## CLI oficial

La CLI publica es `motor`, implementada en `motor/cli.py`.

Comandos base:

- `motor capabilities`
- `motor doctor`
- `motor project info`
- `motor project bootstrap-ai`
- `motor scene list/create/load/save`
- `motor entity create`
- `motor component add`
- `motor prefab create/instantiate/unpack/apply/list`
- `motor animator ...`
- `motor asset ...`

La referencia completa vive en [cli.md](cli.md).

## IA, RL y tooling experimental

`engine/rl`, datasets, runners paralelos y workflows AI-assisted existen, pero
pertenecen a `experimental/tooling`, no al `core obligatorio`.

`engine/navigation` mantiene una foundation `grid-first` experimental con
`NavigationGrid`, `NeighborMode`, `PathRequest`, `PathResult` y una API
canonica `NavigationService.request_path(...)`; `query_path(...)` y
`query_world_path(...)` permanecen como wrappers de compatibilidad.

`engine/agent/` implementa una base clean-room para sesiones tipo agente dentro
del motor. Es `experimental/tooling`: no cambia `Scene`, `World`,
`SceneManager` ni el contrato de runtime.

- `AgentSessionService` es la fachada compatible; delega en `AgentRuntime`, que
  ejecuta turnos iterativos `provider -> tool_use -> tool_result -> provider`.
- Las aprobaciones suspenden un turno y `approve_agent_action(...)` lo reanuda
  con un `tool_result` de ejecucion o rechazo.
- Las herramientas pasan por pipeline de validacion, preview, permiso,
  ejecucion y mapeo de resultado.
- `run_command` esta endurecida por `AgentCommandPolicy` y `AgentCommandRunner`:
  no usa shell, ejecuta `argv` con `shell=False`, confina cwd al proyecto, limita
  entorno/output/timeout y conserva la misma policy en `confirm_actions` y
  `full_access`.
- `FakeLLMProvider` y `ReplayLLMProvider` son providers offline de prueba con
  metadata explicita (`provider_kind=test`, `test_only=True`); `OpenAIProvider`
  es el primer adapter online real y exige credenciales por entorno.
- El runtime soporta eventos de streaming (`assistant_delta` y lifecycle de
  provider) y persiste el mensaje final reconstruido.
- `AgentMemoryStore` y `AgentCompactionService` guardan resumen local sanitizado;
  `AgentUsageRecord` conserva usage de provider con coste `unknown` si no hay
  precios configurados.
- Las herramientas de authoring del motor usan un puerto de engine: `EngineAPI`
  en API/CLI y un adaptador vivo del editor para el panel visual.
- La construccion `EngineAPI` ligada a runtime vivo vive en tooling interno del
  editor; no se promociona como constructor core estable.
- Los modos de permiso iniciales son `confirm_actions` y `full_access`.
- El estado versionado y la auditoria local viven bajo `.motor/agent_state`; las
  sesiones legacy se migran con backup, validacion y evento `session_migrated`.
- `AgentPanel` monta una interfaz simple en el panel inferior del editor, junto
  a `Terminal`.

Docs relevantes:

- [rl.md](rl.md)
- [ai_assisted_workflows.md](ai_assisted_workflows.md)
- [navigation.md](navigation.md)

## Tests de contrato

- `tests/test_core_regression_matrix.py`
- `tests/test_schema_validation.py`
- `tests/test_scene_workspace.py`
- `tests/test_engine_api_public_contract.py`
- `tests/test_motor_cli_contract.py`
- `tests/test_official_contract_regression.py`
- `tests/test_repository_governance.py`

Cobertura relevante:

- roundtrip `load -> edit -> save -> load`
- preservacion de `feature_metadata`
- migraciones `legacy/v1 -> v2`
- aislamiento de `PLAY`
- equivalencia funcional de authoring por `EngineAPI`
- fallback fisico y queries publicas
- separacion entre capabilities implementadas y planificadas

## Limites actuales

- No se promete determinismo cross-platform estricto.
- Existen rutas legacy de edicion directa que deben permanecer acotadas.
- `box2d` no es dependencia obligatoria.
- `engine/rl` y datasets son experimentales.
- Material archivado en `docs/archive/` no es contrato vigente.
