# Arquitectura canonica

Este documento fija el contrato arquitectonico vigente del repo. La referencia
de clasificacion por subsistema esta en [module_taxonomy.md](module_taxonomy.md).

## Principio central

El motor no debe esconder estado funcional en la UI. La fuente de verdad
persistente vive en datos serializables.

- `Scene` es la fuente de verdad persistente.
- `World` es una proyeccion operativa.
- `SceneWorkspace` es la autoridad interna del workspace editable y de su ciclo
  `EDIT -> PLAY -> STOP`.
- `SceneManager` conserva la coordinacion compatible y enruta sus wrappers hacia
  el workspace y las politicas de escena.
- `EngineAPI` es la fachada publica para agentes, tests, CLI y automatizacion.

El contrato base vigente usa:

- `scene schema_version = 2`
- `prefab schema_version = 2`
- migracion explicita de payloads legacy y `v1` a `v2`
- guardado canonico en `v2`

## Representaciones

### Scene

`Scene` conserva el contenido editable y persistible: entidades, componentes
serializables, reglas, `feature_metadata` y referencias de prefab. Un cambio de
authoring que deba persistir tiene que terminar en `Scene`.

`Scene.remove_entity_subtree(name)` elimina la raiz y todos sus descendientes
transitivos por `parent`, conserva el orden relativo de supervivientes y publica
una sola reconstruccion de los indices de nombre, ID y `SceneEntryPoint`.

### World

`World` contiene entidades activas para editor y runtime. No es un formato de
persistencia ni sustituye a `Scene`.

`SceneManager.edit_world` es una reconstruccion editable desde la escena.
`SceneManager.runtime_world` es un clon temporal usado en `PLAY`.
`Game.world` y `HeadlessGame.world` exponen el mundo activo para sistemas, pero
no son la fuente de verdad persistente.

`World` conserva la autoridad operativa sobre entidades activas, callbacks,
notificaciones y versionado. `SceneWorkspace` conserva la seleccion por entrada
y la propaga a los mundos editables o de runtime; la seleccion no forma parte
del payload persistente. La separacion interna de servicios de `World` queda asi:

- `engine.ecs.group_registry.GroupRegistry` es la autoridad del indice de
  grupos. `world.group_registry` sigue siendo la superficie estable y el
  registro mantiene su dependencia de `World` para resolver entidades.
- `engine.ecs.world_serialization.serialize_world()` es la autoridad de
  serializacion; `World.serialize()` permanece como fachada compatible.
- `engine.ecs.world_clone.clone_world()` es la autoridad de clonacion;
  `World.clone()` permanece como fachada compatible y pasa la factory exacta
  `World`. El clon conserva exactamente los contadores global, estructural,
  transform, render, fisica, layout UI y seleccion, pero no copia telemetria ni
  caches.

Esta separacion no cambia Scene v2, el schema ni el payload serializado, la
superficie publica de `EngineAPI` o el ciclo `EDIT -> PLAY -> STOP`.

## Ciclo EDIT -> PLAY -> STOP

```text
Scene serializable
  -> edit_world para authoring
  -> runtime_world temporal para PLAY
  -> vuelta a edit_world sin contaminar authoring
```

Invariantes:

1. Las mutaciones de runtime no se guardan como authoring por accidente.
2. La seleccion puede sobrevivir a cambios de modo sin volverse dato serializable de escena.
3. Previews transitorios de gizmos no deben marcar dirty state ni autosave.
4. Un save/load roundtrip conserva entidades, componentes, jerarquia y `feature_metadata`.

## Superficie de mutacion autorizada

Las rutas compartidas de authoring son:

- `SceneManager.apply_edit_to_world()`
- `SceneManager.update_entity_property()`
- `SceneManager.replace_component_data()`
- `SceneManager.add_component_to_entity()`
- `SceneManager.remove_component_from_entity()`
- operaciones estructurales de `SceneManager`
- metodos publicos equivalentes en `EngineAPI`

`sync_from_edit_world()` existe como API deprecada para compatibilidad legacy
explicita y conserva su warning. No es la ruta normal para nuevas superficies
publicas de authoring.

## Responsabilidades por capa

### Export pipeline

El build oficial de juegos separa editor y runtime:

```text
Proyecto editable -> validacion -> grafo de contenido -> content pack ->
runtime template de plataforma -> artefacto jugable -> smoke/report
```

`Scene` sigue siendo fuente persistente de verdad. `World` no se serializa como
authoring durante export. La automatizacion publica entra por `EngineAPI` o
`py -m motor export ...`. El runtime exportado usa `engine/runtime/exported_game.py`
y carga `runtime_config.json`, `game.manifest.json`, `game.pak` o `content/` sin
arrancar paneles de editor.

Documentacion relacionada: [export_pipeline.md](export_pipeline.md),
[export_presets.md](export_presets.md), [runtime_templates.md](runtime_templates.md),
[build_artifacts.md](build_artifacts.md), [mobile_export.md](mobile_export.md),
[troubleshooting_export.md](troubleshooting_export.md).

### SceneManager

Conserva los wrappers compatibles y el routing de operaciones de authoring,
persistencia y scene flow hacia la entrada activa o la entrada indicada. Tambien
coordina transacciones, historial y operaciones estructurales sin duplicar el
estado cuya autoridad pertenece al workspace.

La persistencia tecnica queda separada por responsabilidades:

- `ScenePersistenceService` es la autoridad de resolucion de rutas, storage
  default o custom, escritura temporal y reemplazo del storage default,
  verificacion de readback, recuento de entidades y lectura de mtime.
- `SceneProjectionService` es la autoridad tecnica de migracion, validacion y
  canonicalizacion en los limites de proyeccion, conversion `Scene <-> World`
  y materializacion incremental. Opera sobre payloads, escenas y mundos; no
  conserva estado de `SceneWorkspaceEntry` ni decide lifecycle, seleccion o
  dirty state.
- `SceneWorkspace` es la autoridad de entradas abiertas y activa, seleccion y
  dirty state por entrada, claves, normalizacion de rutas y rekey, ademas del
  ciclo de vida `EDIT -> PLAY -> STOP` en memoria. `activate_scene()` es la
  transicion explicita para activar una entrada ya abierta y es la ruta usada
  por `SceneManager` al reutilizar `load_scene_from_file`. Delega conversion
  tecnica en
  `SceneProjectionService` y reglas de scene flow en `SceneFlowPolicy`; no
  realiza I/O. `install_entry_state()` es el unico punto que instala juntos
  `scene`, `edit_world` y `edit_world_version` en una entrada.
- `SceneEditSyncCoordinator` es la autoridad unica de razones y estado de
  pending sync entre `edit_world` y `Scene`. Depende de `SceneWorkspace` para
  solicitar transiciones de dirty state y de `SceneProjectionService` para
  canonicalizar la proyeccion; no posee persistencia, CRUD ni scene flow.
- `SerializableMutationCoordinator` es la autoridad de captura, commit y
  rollback semantico de una mutacion serializable. Depende de `SceneWorkspace`,
  `SceneProjectionService` y `SceneEditSyncCoordinator`. Antes de mutar, su token
  prepara una `Scene` semanticamente valida y, en las rutas que tambien mutan o
  sincronizan metadata con `World`, conserva un clon del mundo. El token es
  opaco: su tipo y sus campos no forman parte de ningun contrato.
- `SceneIncrementalAuthoring` es la autoridad de edicion directa de componentes
  `Transform` y `RectTransform` ya presentes en `Scene` y `edit_world`. Posee la
  normalizacion numerica, los deltas, el estado de transaccion diferencial y su
  undo/redo. Depende de `SceneWorkspace`, `SceneEditSyncCoordinator` y
  `SceneHistoryPort`; no posee prefab overrides, persistencia, scene flow ni
  rebuild completo.
- La decision de cohesion S7C es `split_component_and_entity`.
  `SceneSerializableAuthoring` permanece como fachada de compatibilidad: compone
  un unico `SceneSerializableAuthoringPipeline`, un `SceneComponentAuthoring` y
  un `SceneEntityAuthoring`, y conserva los wrappers existentes sin implementar
  una segunda ruta de authoring.
- `SceneComponentAuthoring` es la autoridad de consultas defensivas, CRUD y
  metadata de componentes. Tambien posee la mutacion transaccional de scene flow.
  `SceneEntityAuthoring` es la autoridad de consultas defensivas y CRUD de
  entidades, incluida la creacion incremental y su historial diferencial.
- `SceneSerializableAuthoringPipeline` es el unico limite transaccional compartido
  por ambos propietarios. Encapsula flush, captura, rollback o commit, dirty state
  e historial mediante `SceneWorkspace`, `SceneEditSyncCoordinator`,
  `SerializableMutationCoordinator` y `SceneHistoryPort`. El port de historial
  es failure-atomic: si el registro falla, no deja historia observable y el
  pipeline revierte la transaccion completa. `SceneChangeCoordinator` hace
  efectiva esa garantia mediante el checkpoint opaco de captura/restauracion
  cuando el backend lo ofrece, preservando undo/redo sin inspeccionar sus stacks;
  un backend sin checkpoint debe proporcionar un `push` failure-atomic.
- `SceneChangeCoordinator` es un coordinador pasivo de almacenamiento,
  agrupacion y restauracion de historial. No recibe un contexto de callbacks, no
  mantiene dispatch de operaciones de authoring, no conoce CRUD ni servicios de
  authoring y no escribe dirty state. Recibe closures estrechos de undo/redo o
  una capacidad de restauracion solo al cerrar o revertir una transaccion.
- `PrefabOverrideService` es la autoridad unica de overrides genericos de una
  instancia expandida. Implementa las cuatro operaciones de `PrefabOverridePort`:
  actualizar propiedades de componente o entidad, reemplazar componentes y
  eliminarlos. No posee schema, persistencia, historial, rebuild ni callbacks al
  manager.
- `ScenePrefabAuthoring` conserva las operaciones completas de prefab: crear,
  instanciar, unpack y aplicar overrides al asset. Esta responsabilidad sigue
  separada de la mutacion generica de overrides.
- `SceneFlowPolicy` concentra, sin estado de workspace ni I/O, las reglas
  deterministas de precedencia, sincronizacion y validez entre `SceneLink` y
  `feature_metadata.scene_flow`.
- `SceneManager` es una fachada de composicion, wiring, routing y coordinacion
  transversal. Conserva compatibilidad publica, callbacks de guardado, tracking
  de mtime y la coordinacion entre persistencia, workspace, runtime y las
  autoridades de authoring. No implementa schema, proyeccion, pending sync,
  snapshots, historial, scene flow, transforms, prefabs ni algoritmos de
  jerarquia; los solicita a los servicios propietarios. Los wrappers privados de
  entrada que siguen existiendo solo delegan una resolucion al workspace.

Antes de una mutacion serializable o estructural, la ruta propietaria delega el
flush legacy en `SceneEditSyncCoordinator.flush_pending()`. El guardado delega en
`prepare_for_save()`: descarta el preview transitorio sin persistirlo o integra
el pending legacy antes de escribir. Si el snapshot legacy es invalido, el
coordinador reconstruye la proyeccion y solicita a `SceneWorkspace` restaurar
exactamente el dirty baseline capturado. El metodo deprecado
`SceneManager.sync_from_edit_world()` permanece como wrapper y conserva su
warning. `SceneManager.mark_edit_world_dirty()` permanece como wrapper legacy
compatible, sin marcarse deprecado.

El contrato de bajo nivel de `flush_pending()` conserva la compatibilidad S4:
un pending legacy de una entrada inactiva retorna `True` como no-op y no consume
ni modifica su estado. Los limites que necesitan una `Scene` fresca son mas
estrictos. `SceneSerializableAuthoringPipeline` rechaza ese caso con `False`
antes de consultas o mutaciones; las APIs publicas conservan sus sentinels
(`None`, coleccion vacia o `False`) sin capturar estado ni registrar historial.
`prepare_for_save()` tambien retorna `False` antes de sincronizar o persistir una
entrada inactiva con pending legacy, sin modificar workspace ni storage. El
tratamiento del preview transitorio no cambia: se descarta al reconstruir la
proyeccion y no se incorpora al payload persistido.

En un sync activo `SceneEditSyncCoordinator` serializa `World` una sola vez y
enriquece solo ese snapshot separado con los IDs serializados vivos, resueltos
por el nombre actual, antes de canonicalizar y validar. Asi conserva identidad a
traves de rename y del root compacto de prefab. Un ID ausente queda a cargo de
la generacion canonica; un ID invalido, conflictivo o duplicado rechaza el sync
en lugar de reasignar identidad. Al reactivar la entrada, el flush normal puede
integrar el pending y la operacion serializable y su undo/redo conservan los IDs
y datos sincronizados.

Cuando existe pending legacy activo, el pipeline serializable prepara un guard
tecnico previo al flush para contener fallos de proyeccion y restaurar el estado
sin reproyectarlo. Ese guard no es el snapshot de authoring: tras un flush
exitoso se captura uno fresco, por lo que el orden contractual sigue siendo
flush -> capture. Sin pending no se crea el guard.

Los wrappers publicos de Transform, RectTransform y transacciones diferenciales
delegan en `SceneIncrementalAuthoring`. La ruta valida actualiza `Scene` y
`edit_world` sin rebuild; seleccion y dirty state se solicitan a
`SceneWorkspace`, y pending sync se limpia mediante `SceneEditSyncCoordinator`.
`SceneManager` decide entre esa ruta incremental y
`SceneSerializableAuthoring` para la mutacion general. Al actualizar `parent`,
el manager conserva la prevalidacion estructural de ciclos antes de delegar la
mutacion serializable.

La decision S6 es `extract`: las rutas serializables y estructurales comparten
una unica instancia de `PrefabOverrideService`. `SceneManager` la entrega a
`SceneSerializableAuthoring` y `SceneStructuralAuthoring`; ambos consumen
`PrefabOverridePort` sin depender entre si. Jerarquias y el ciclo completo de
prefab permanecen en structural authoring.

`SceneSerializableEntityPort` define el limite minimo de creacion y actualizacion
de entidades serializables para structural authoring. `SceneManager` entrega a
`SceneStructuralAuthoring` exactamente la instancia compartida de
`SceneEntityAuthoring` expuesta por la fachada. Structural authoring no usa un
contexto ni callbacks al manager: recibe exactamente `SceneWorkspace`, el
`SceneSerializableTransactionPort` compartido, `SceneSerializableEntityPort` y
`PrefabOverridePort`. La dependencia queda unidireccional:
`SceneStructuralAuthoring -> SceneSerializableEntityPort`; authoring serializable
no depende de structural authoring y no se introduce un ciclo.

En commit, projection valida y canonicaliza las representaciones que
`SceneWorkspace` publica. En rollback, el token instala mediante el workspace la
`Scene` semantica preparada antes de mutar y el `World` capturado, sin reutilizar
la proyeccion que pudo fallar; despues restaura seleccion y dirty state, y pending
sync mediante `SceneEditSyncCoordinator`. Las rutas que mutan o sincronizan
metadata con el mundo capturan un clon. El coordinador tambien valida y publica
el commit incremental de una entidad, con el mismo rollback semantico ante fallo.
`SceneSerializableAuthoringPipeline` maneja el token opaco y el historial de las
operaciones serializables. `SceneComponentAuthoring.set_scene_flow_target()`
posee el limite completo de esa transaccion; el wrapper homonimo de
`SceneSerializableAuthoring` mantiene compatibilidad y `SceneManager` solo
delega.

La ruta serializable rechaza PLAY antes de capturar estado y ejecuta, en orden,
flush de pending, captura, mutacion encapsulada de `Scene`, commit o rollback,
dirty state e historial. Una excepcion durante commit o registro de historial
restaura el snapshot, retorna `False` y no deja historia observable; las consultas
devuelven copias defensivas.

`SceneManager.apply_change()` conserva el routing de alto nivel de `Change`.
Parsea y enruta los seis kinds compatibles hacia las autoridades publicas de
authoring y solo agrega metadata defensiva a la transaccion general cuando la
operacion termina con exito. `begin_transaction()`, `commit_transaction()` y
`rollback_transaction()` mantienen sus firmas publicas: el manager resuelve la
entrada y captura los extremos serializables, mientras
`SceneChangeCoordinator` agrupa metadata y registra closures sin despachar CRUD.

`SerializableMutationCoordinator.restore_scene_data()` es la capacidad estrecha
de restauracion por key. Reinstala una copia mediante `SceneWorkspace`, conserva
la seleccion vigente a traves de esa autoridad, limpia pending mediante
`SceneEditSyncCoordinator` y solicita al workspace marcar dirty. History no
conoce entries, projection ni esas autoridades.

Los cambios serializables y estructurales por snapshot pasan por la misma
instancia de `SceneSerializableAuthoringPipeline`. Structural authoring
prevalida, abre el token, muta solo mediante primitivas de `Scene`, sincroniza
scene flow cuando aplica y confirma el snapshot. Un `False` posterior a la
captura revierte; un fallo de commit o history restaura payload, mundo,
seleccion, dirty, pending, versiones y undo/redo. Esta atomicidad cubre el estado
en memoria. Los archivos prefab ya escritos no se revierten: su I/O no forma
parte de la transaccion atomica. `SceneChangeCoordinator` permanece pasivo y
`SceneManager` ya no define callback estructural de historial.

En scene flow, metadata aporta el mapa base. Un `SceneLink` con el mismo
`flow_key` lo reemplaza; si hay duplicados gana el ultimo en orden serializado.
Un `target_path` ausente hereda metadata cuando existe, mientras un
`target_path` presente pero vacio elimina esa clave efectiva y marca el link
invalido. Las claves de metadata sin link se conservan. Estas reglas se aplican
sobre la entrada destinataria con la misma semantica tanto si esta activa como
si permanece inactiva. Si el mapa efectivo queda vacio, `SceneFlowPolicy` usa
`Scene.remove_feature_metadata()` para retirar `feature_metadata.scene_flow` en
vez de serializar un objeto vacio que el schema no admite.

La separacion mantiene las firmas publicas, Scene v2 y su schema. Tambien
preserva la atomicidad vigente: temporal mas reemplazo para storage default y
la semantica provista por cada storage custom.

### Game y HeadlessGame

Coordinan tiempo, estado del motor y sistemas sobre el mundo activo. No deben
convertirse en una ruta paralela de persistencia.

### EngineAPI

`EngineAPI` expone authoring, runtime, workspace, scene flow, assets, proyecto,
debug y UI serializable. Wrappers RL, CLI, tests y automatizacion deben usar
esta fachada en vez de internals privados.

## Contratos internos base

La base tecnica compartida de Fase 1 hace explicitos tres puertos internos de
escena y un contexto de runtime:

- `SceneRuntimePort`: ciclo `EDIT -> PLAY -> STOP` y acceso al mundo activo.
- `SceneAuthoringPort`: mutaciones serializables y operaciones estructurales.
- `SceneWorkspacePort`: workspace multi-escena, guardado y scene flow.
- `RuntimeControllerContext`: wiring explicito entre runtime, escena y sistemas.

`SceneManager` sigue siendo la implementacion concreta y `EngineAPI` mantiene la
misma superficie publica. El cambio solo formaliza limites internos para que
fases posteriores extiendan runtime, render, fisica, tilemaps, animacion, UI,
audio, navegacion, editor y tooling sin introducir nuevos accesos cruzados.

### Editor/UI

La UI visualiza y traduce acciones de usuario. Puede mantener estado efimero de
layout, hover o seleccion visual. No debe introducir comportamiento funcional
inaccesible por `EngineAPI` o por datos serializables.

Sincronizacion escena-editor: `Scene` es la fuente de verdad. `World` se refresca
como proyeccion operativa cuando la escena se recarga. Un guardado exitoso de
escena puede notificar al editor para refrescar vistas. La recarga segura de
archivo stale evita descartar estado de authoring sucio no guardado.

## Contrato fisico

El core conserva un contrato comun de backends fisicos:

- `legacy_aabb` esta siempre disponible
- `box2d` es opcional
- si `box2d` no puede activarse, el runtime cae a `legacy_aabb`
- el backend solicitado en `feature_metadata.physics_2d.backend` no debe sobrescribirse por el fallback efectivo
- `query_physics_ray` y `query_physics_aabb` mantienen su significado publico
- `body_test_motion` añade un sweep-test no-mutante (barrido de colisión sin modificar el mundo), bloque fundamental del que depende `move_and_slide`
- **PGS Impulse Solver (dos fases):** tras integrar fuerzas, el sistema construye constraints de contacto y joints bilaterales (fixed, distance, pin) entre cuerpos, agrupa en islas via BFS, y ejecuta:
  1. **PGS velocity solve** (8 iteraciones): impulsos normales con clamp no-negativo y friccion Coulomb
  2. **PGS position solve** (3 iteraciones): correccion mass-weighted sobre transforms con age-based damping
  Los joints bilaterales usan `is_bilateral=True` para permitir impulso negativo.
- **Broadphase unificado**: `SpatialHash2D` compartido y reutilizado entre
  `PhysicsSystem`, `CollisionSystem` y queries espaciales. El tamano de celda se
  selecciona de forma determinista desde el tamano mediano de los colliders,
  limitado a `32..256px`; AABB gigantes usan un registro conservativo separado.
- **Cache geometrica runtime**: AABB y `ShapeInstance` se reutilizan entre
  frames mientras no cambien transform, estado enabled ni geometria del
  collider. La cache no es authoring state ni se serializa.
- **Joint stiffness**: `Joint2D.joint_stiffness` (default 0.2) controla bias en constraints PGS bilaterales.

## Taxonomia arquitectonica

Los documentos principales usan tres categorias:

- `core obligatorio`
- `modulos oficiales opcionales`
- `experimental/tooling`

La clasificacion completa vive en [module_taxonomy.md](module_taxonomy.md).

## Cobertura relevante

- `tests/test_core_regression_matrix.py`
- `tests/test_scene_workspace.py`
- `tests/test_engine_api_public_contract.py`
- `tests/test_schema_validation.py`
- `tests/test_physics_backend.py`
- `tests/test_repository_governance.py`

## Regla de extension

Antes de introducir una feature nueva, definir:

1. Donde se serializa.
2. Como se edita sin depender de UI.
3. Como se valida en headless.
4. Como vuelve a estado editable tras `STOP` si participa en runtime.
5. Si pertenece a `core obligatorio`, `modulos oficiales opcionales` o `experimental/tooling`.
