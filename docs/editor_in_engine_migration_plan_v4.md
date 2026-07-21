---
schema_version: 4
doc_type: architecture_migration_plan
status: ready_for_execution
repository: Yisuescopeta/OpenGame
baseline_branch: main
baseline_commit: 58b6671ef72e17d8b7c8602781765bb4d984f1fa
baseline_date: 2026-07-21
owner_accountable: "@Yisuescopeta"
target_scene_schema: 3
execution_model: solo_maintainer_optimized
supersedes: OpenGame_plan_migracion_editor_v3.md
---

# Arquitectura objetivo y plan ejecutable de migración del editor de OpenGame

## 0. Resumen ejecutivo

OpenGame ya dispone de una base válida para evolucionar hacia un editor profesional sin reescribir el subsistema de escenas. `Scene` representa el estado persistente de authoring; `SceneWorkspace` mantiene escenas abiertas y separa `edit_world` de `runtime_world`; `SceneManager` compone servicios de proyección, persistencia, authoring, historial y lifecycle; y `RuntimeController` coordina EDIT, PLAY, PAUSE, STEP y STOP.

La migración debe completar esa arquitectura, no sustituirla. El objetivo es eliminar todas las rutas que permiten tratar `World` como fuente persistente de verdad, consolidar identidad y selección mediante referencias estables, impedir que el composition root se distribuya por la aplicación, validar una única UI de producción y retirar físicamente la compatibilidad cuando llegue a cero consumidores.

Esta versión incorpora como requisitos obligatorios:

1. **Integridad híbrida y fail-closed:** `World.version` se usa solo como fast path. Save, autosave, PLAY, cambio/cierre de escena, cambio de proyecto, reload y export verifican además un fingerprint canónico capaz de detectar asignaciones directas a componentes aunque no se haya llamado a `touch_*`.
2. **Identidad de documento inmutable:** una escena abierta se identifica por `OpenDocumentId`; la ruta y la clave del workspace son localizadores mutables y nunca forman parte de una referencia estable.
3. **Schema de escena v3:** el schema v2 se conserva como entrada migrable, pero las nuevas escrituras usan referencias persistentes ID-first para jerarquía, reglas, signals, links y relaciones cross-scene.
4. **Cuarentena explícita `World -> Scene`:** no existe sincronización automática. Los consumidores legacy solo pueden importar cambios mediante un adaptador allowlisted, explícito, medido y con fecha de eliminación.
5. **Previews con lifecycle desde G0.5:** un registro mínimo de leases permite cancelar o bloquear previews antes de acciones protegidas; G3 sustituye cada frontera pública por contratos tipados por herramienta.
6. **Composition root no distribuible:** `EngineCompositionRoot` construye dependencias, pero ningún panel, presenter o caso de uso recibe el contenedor completo.
7. **Sin buses como autoridad genérica:** las escrituras usan casos de uso o puertos específicos; los eventos solo notifican hechos posteriores a un commit.
8. **Resultados tipados de adopción incremental:** las nuevas APIs usan `Result`; las APIs legacy mantienen temporalmente `bool`/`Optional` mediante adaptadores de frontera.
9. **`Scene` totalmente encapsulada:** `data`, `entities_data`, `rules_data`, `feature_metadata` y los resultados de búsqueda dejan de exponer referencias mutables.
10. **Cutover dividido y proporcionado:** los gates G5A–G5E conservan criterios independientes, pero los IDs de entrega son paquetes verificables que pueden agruparse en PRs coherentes para un mantenedor único.
11. **Compatibilidad final definida:** se especifica qué superficie conservará `SceneManager`, qué se moverá a una fachada legacy temporal y qué se eliminará.

El plan queda organizado en **doce gates ejecutables**: G0, G0.5, G1, G2, G3, G4, G5A, G5B, G5C, G5D, G5E y G6.

---

## 1. Dictamen y línea base

### 1.1 Cimientos que se conservan

- `Scene` como aggregate persistente serializable.
- Schema de escena v2 e IDs de entidad ya presentes como base de migración.
- `SceneProjectionService` como dirección principal `Scene -> World`.
- `SceneWorkspace` como autoridad de escenas abiertas, dirty state y lifecycle.
- Separación `edit_world` / `runtime_world`.
- `SceneManager` como fachada y punto de composición de servicios de escena.
- Puertos actuales de runtime, authoring y workspace como compatibilidad de transición.
- Authoring incremental, serializable y estructural ya extraído.
- Persistencia y transacciones existentes.
- `RuntimeController` como coordinador del runtime.
- Modelos puros de docking, foco, popups y foundation retained-mode.
- Tests existentes de lifecycle, sync, serialización y runtime.
- `engine.runtime` y su contrato de aislamiento para juegos exportados.

### 1.2 Deuda que bloquea el cutover

- `prepare_for_save()` puede promover cambios no registrados de `EditWorld` a `Scene`.
- `sync_from_edit_world(force=True)` puede aceptar cambios transitorios.
- `World.version` no observa necesariamente una asignación directa a un campo de componente; por tanto, no puede ser la única prueba de integridad.
- PLAY clona el `EditWorld` sin una comprobación canónica previa.
- Activar, cerrar o cambiar escenas no verifica la divergencia de la proyección saliente.
- Existen paneles y controllers que, si falta `SceneManager`, escriben directamente en `World`.
- `Scene.data`, `entities_data`, `rules_data`, `feature_metadata` y `find_entity*()` exponen estructuras mutables.
- APIs ID-first parciales vuelven internamente a nombres.
- El schema v2 conserva referencias persistentes name-first, como `parent` y `target_entity_name`.
- La clave del workspace puede cambiar después de guardar, por lo que no sirve como identidad estable de una escena abierta.
- La selección se replica entre sesión, workspace y `World`.
- `Game` sigue siendo host, god object, composition root distribuido y coordinador de wiring.
- `EditorLayout` mantiene demasiada autoridad.
- `EditorShellState` usa flags `request_*` para acciones momentáneas.
- La UI retained-mode convive con paneles legacy y adaptadores bidireccionales.
- `InspectorSystem`, `ProjectPanel` y `AssetService` mezclan capas.
- `Any`, `hasattr`, getters genéricos y accesos privados siguen apareciendo en fronteras.

### 1.3 Decisión

> La arquitectura de escenas se conserva y se endurece. La migración comienza demostrando integridad real, introduce identidad estable y schema v3, elimina autoridades duplicadas, completa authoring ID-first, tipa previews y contratos, valida la UI y retira físicamente legacy.

No se autoriza una reescritura simultánea de escenas, UI, assets y runtime. Tampoco se considera protegido un flujo mientras el guard no detecte una mutación directa de componente sin `touch_*`.

---

## 2. Objetivos y no objetivos

### 2.1 Objetivos obligatorios

- `Scene` es la única autoridad persistente.
- `EditWorld` es una proyección reconstruible y vigilada.
- `PlayWorld` es temporal y descartable.
- Save y autosave son fail-closed.
- PLAY, close, scene switch, project switch, reload y export validan integridad antes de continuar.
- El guard detecta divergencias aunque `World.version` no cambie.
- Toda mutación persistente pasa por un caso de uso transaccional o por un adaptador legacy allowlisted y explícito.
- Toda identidad interna de entidad es ID-first.
- Toda escena abierta dispone de un `OpenDocumentId` inmutable.
- Toda referencia persistente nueva se escribe en schema v3.
- La selección tiene una autoridad única.
- Preview y authoring son semánticamente distintos.
- Los paneles solo reciben queries y comandos específicos de su capacidad.
- Existe una única arquitectura UI de producción.
- Runtime no importa `engine.editor` ni `engine.inspector`.
- Los adaptadores temporales tienen owner, consumidores, gate y eliminación.
- Los presupuestos de rendimiento se miden en CI o benchmark reproducible.
- Las nuevas APIs usan `Result`; la compatibilidad legacy traduce a `bool`/`Optional` solo en la frontera.


### 2.2 No objetivos obligatorios

No bloquean el cutover:

- Multi-window nativo completo.
- Auto-hide avanzado.
- Docking idéntico a Unity o Godot.
- Marketplace o plugins públicos de terceros.
- Rediseño visual integral.
- Reemplazo de Raylib.
- Colaboración multiusuario.
- Accesibilidad completa.

Estas capacidades solo se incorporarán si no prolongan una arquitectura duplicada.

---

## 3. Invariantes no negociables

1. `Scene` es la única fuente persistente de verdad.
2. `EditWorld` puede reconstruirse desde `Scene`.
3. `PlayWorld` nunca se serializa hacia authoring.
4. `World.version` es una optimización de detección, nunca la única prueba de integridad.
5. Save, autosave, PLAY, close, scene switch, project switch, reload y export verifican la equivalencia canónica `Scene <-> EditWorld` después de cancelar previews.
6. Una divergencia no registrada produce error explícito; nunca sincronización automática.
7. El descarte de una divergencia requiere una acción explícita del usuario o del caller y nunca se presenta como guardado exitoso.
8. Toda mutación persistente es atómica.
9. Toda mutación persistente genera, cuando procede, una única entrada semántica de historial.
10. Los paneles no acceden a datos mutables internos de `Scene`.
11. Los paneles no mutan persistentemente `World`.
12. Preview no cambia `Scene`, dirty state ni payload guardado.
13. Preview solo puede modificar una capa temporal autorizada y registrada mediante lease.
14. Save y PLAY cancelan previews antes de validar la proyección.
15. La identidad de entidad no depende del nombre.
16. La identidad de un documento abierto no depende de ruta, nombre ni clave de workspace.
17. Una referencia persistente a una escena no usa `OpenDocumentId` ni la clave efímera del workspace.
18. La selección no forma parte del payload persistente.
19. El composition root no se inyecta en consumidores.
20. No existe un command bus genérico como autoridad de escritura.
21. Los eventos describen hechos ya confirmados; no ejecutan mutaciones implícitas.
22. Los read models son defensivos e inmutables para la UI.
23. Dependencias obligatorias ausentes fallan explícitamente.
24. Ningún fallback cambia la semántica de una operación.
25. No se usa `Any` o `hasattr` como contrato principal nuevo.
26. Las nuevas APIs de aplicación devuelven `Result`; los retornos legacy solo existen en adaptadores.
27. El writer de producción emite schema v3; schema v2 se acepta únicamente como entrada migrable.
28. Ninguna feature nueva se implementa sobre legacy congelado.
29. Un panel no está migrado mientras exista fallback o dualidad de producción.
30. La eliminación física forma parte de la definición de terminado.

---

## 4. Arquitectura objetivo

```text
EngineCompositionRoot
├── RuntimeHost
│   └── RuntimeController
│       ├── Runtime systems
│       ├── Runtime services
│       └── PlayWorld
│
├── Scene subsystem
│   ├── SceneWorkspace
│   ├── SceneManagerFacade
│   ├── SceneAuthoringUseCases
│   ├── ScenePersistenceService
│   ├── SceneProjectionService
│   ├── HistoryPort
│   └── Scene (canonical state)
│       └── EditWorld projection
│
└── EditorHost
    ├── EditorApplication
    │   ├── EditorSession
    │   ├── feature-specific use cases
    │   ├── feature-specific query providers
    │   ├── PostCommitEventPublisher
    │   └── Preview coordinators
    │
    └── EditorShell
        ├── DockWorkspace
        ├── PanelRegistry
        ├── Focus/Pointer/Popup authority
        └── Views + Presenters
            └── receive only capability-specific contracts
```

### 4.1 Dirección de dependencias

```text
View -> Presenter -> Capability Commands / Queries -> Scene/Asset ports
                                              |
                                              └-> PostCommitEventPublisher
```

Nunca:

```text
View -> EditorCompositionRoot
View -> Game
View -> SceneManager concreto
View -> World mutable para authoring
Event handler -> nueva mutación implícita
```

---

## 5. Matriz de autoridades

| Responsabilidad | Autoridad final | Copias permitidas | Prohibido |
|---|---|---|---|
| Estado persistente de escena | `Scene` | Snapshots/read models | `World` como fuente persistente |
| Identidad de escena abierta | `OpenDocumentId` en `SceneWorkspaceEntry` | Refs inmutables | Ruta, nombre o workspace key como identidad |
| Localización de escena abierta | `SceneWorkspace` | Tabs/read models | Persistir el workspace key |
| Identidad de asset de escena | `SceneAssetRef` | Path hint | Usar solo path para identidad final |
| Integridad de proyección | `ProjectionIntegrityGuard` | Stamp y fingerprint cacheados | Confiar solo en `World.version` |
| Escenas abiertas y activa | `SceneWorkspace` | `WorkspaceTabsView` | Duplicar active scene en paneles |
| Selección del editor | `EditorSession.selection: EntityRef?` | Proyección visual en `World` | Sincronización bidireccional por frame |
| Dirty state | `SceneWorkspaceEntry` | Badge de UI | Inferir dirty desde cualquier panel |
| Undo/redo | `HistoryPort` | Vista de historial | Historial por panel |
| Preview lifecycle | `PreviewLeaseRegistry` | Estado tipado de herramienta | Preview no registrado |
| Preview state | Coordinador tipado de herramienta | Overlay temporal | `mark_edit_world_dirty` nuevo |
| Foco/input/pointer | `EditorShell` | Estado visual de controles | Paneles con autoridad global |
| Persistencia de layout | `DockWorkspaceStore` | Snapshot versionado | `EditorLayout` como estado global |
| Assets | Servicios de catálogo/authoring | Read models | Filesystem directo desde panel |
| Runtime | `RuntimeController` | Métricas/read views | Dependencias hacia `engine.editor` |

---

## 6. Cuarentena fail-closed de `World -> Scene`

Este trabajo se ejecuta antes de ampliar UI o composition. La cuarentena no puede depender exclusivamente de contadores de versión porque una asignación directa a un componente puede no invocar `touch_*`.

### 6.1 Evidencia de integridad híbrida

La proyección editable mantiene una evidencia canónica:

```python
@dataclass(frozen=True, slots=True)
class ProjectionIntegrityEvidence:
    scene_revision: int
    projected_world_version: int
    canonical_fingerprint: str
    projection_schema_version: int
```

`projected_world_version` permite un fast path, pero `canonical_fingerprint` es la prueba autoritativa en acciones protegidas.

El fingerprint:

- Representa exactamente el dominio proyectado `Scene -> EditWorld`.
- El fingerprint esperado se calcula desde el snapshot canónico de `Scene`.
- El fingerprint observado se calcula desde `EditWorld` y completa con datos canónicos de `Scene` que no estén materializados en `World`.
- Excluye selección, hover, caches, handles runtime y estado de preview.
- Incluye entidades, IDs, jerarquía, componentes serializables y metadata persistente proyectada.
- Usa canonicalización estable de claves, números y colecciones.
- No escribe en `Scene` ni normaliza silenciosamente un `World` inválido.
- Produce diagnóstico estructurado cuando no puede serializar una frontera.

Después de cada commit canónico:

1. `Scene` incrementa `scene_revision`.
2. Se calcula el fingerprint esperado desde el snapshot canónico de `Scene`.
3. La proyección se actualiza o reconstruye.
4. Se almacena la evidencia en `SceneWorkspaceEntry`.
5. El guard considera la proyección limpia.

El escaneo profundo de `EditWorld` se ejecuta en acciones protegidas, no en cada frame ni necesariamente en cada commit.

### 6.2 Algoritmo del guard

```python
class ProjectionIntegrityGuard:
    def inspect(
        self,
        action: ProtectedAction,
        entry: SceneWorkspaceEntry,
    ) -> Result[ProjectionIntegrityReport]: ...

    def assert_clean(
        self,
        action: ProtectedAction,
        entry: SceneWorkspaceEntry,
    ) -> Result[None]: ...
```

Secuencia obligatoria:

1. Resolver la entrada por `OpenDocumentId`.
2. Cancelar previews activos mediante `PreviewLeaseRegistry`.
3. Verificar que la cancelación dejó cero leases de escritura.
4. Usar versión/stamp como fast path diagnóstico.
5. Calcular el fingerprint canónico actual de `EditWorld`.
6. Compararlo con la evidencia de la última proyección canónica.
7. Si difiere, bloquear la acción.
8. Si coincide, continuar usando exclusivamente `Scene` para persistencia o para construir `PlayWorld`.

Test de autoridad obligatorio:

```python
transform.x = 72.0  # sin world.touch_transform()
result = save_scene(...)
assert result.error.code is UNREGISTERED_EDIT_WORLD_MUTATION
assert scene.snapshot() == scene_before
assert disk_payload == disk_before
```

Una acción no se considera protegida mientras este test no pase.

### 6.3 Acciones protegidas y semántica

Antes de ejecutar:

- `save` y `autosave` validan la escena objetivo.
- `enter_play` valida la escena activa y construye runtime desde `Scene`, no clonando una proyección divergente.
- `activate_scene` valida la escena saliente.
- `close_scene` valida la escena objetivo salvo que exista descarte explícito.
- `switch_project` valida todas las escenas abiertas salvo las descartadas explícitamente.
- `reload_from_disk` exige confirmación explícita si existe dirty state o divergencia.
- `export/build` valida todas las escenas incluidas.

El descarte explícito:

- No importa datos desde `World`.
- Registra la decisión y el consumidor que la originó.
- Reconstruye o elimina la proyección antes de continuar.
- Nunca devuelve el mismo resultado que un guardado exitoso.

### 6.4 Comportamiento fail-closed

Ante divergencia no registrada:

- No se serializa `World` hacia authoring.
- No se sobrescribe `Scene`.
- No se descarta el estado silenciosamente.
- La acción se bloquea con error tipado.
- Se muestra diagnóstico con escena, documento, revisiones, fingerprint y probable consumidor.
- Se ofrecen acciones explícitas de reconstruir/descartar o inspeccionar el consumidor.
- Una captura de recuperación, si se implementa, se guarda fuera del formato canónico y nunca sustituye automáticamente a `Scene`.

Códigos mínimos:

```text
UNREGISTERED_EDIT_WORLD_MUTATION
ACTIVE_PREVIEW_MUST_CLOSE
PREVIEW_CANCEL_FAILED
LEGACY_SYNC_CONSUMER_BLOCKED
PROJECTION_FINGERPRINT_MISMATCH
PROJECTION_SERIALIZATION_FAILED
PROJECTION_SCHEMA_MISMATCH
```

### 6.5 Preview lifecycle mínimo en G0.5

Antes de los contratos tipados de G3 existe un registro interno mínimo:

```python
@dataclass(frozen=True, slots=True)
class PreviewLease:
    lease_id: str
    document_id: OpenDocumentId
    owner: str
    target_ids: tuple[str, ...]
    cancel: Callable[[PreviewCancelReason], Result[None]]

class PreviewLeaseRegistry(Protocol):
    def register(self, lease: PreviewLease) -> Result[None]: ...
    def active_for(self, document_id: OpenDocumentId) -> tuple[PreviewLease, ...]: ...
    def cancel_all(self, document_id: OpenDocumentId, reason: PreviewCancelReason) -> Result[None]: ...
```

Este contrato no expone estado de preview genérico. Solo administra lifecycle. El estado editable público permanece tipado por herramienta en G3.

### 6.6 Compatibilidad temporal `World -> Scene`

Durante G0.5 puede existir una allowlist cerrada:

```yaml
consumer: inspector.collider_drag
owner: editor-tools
allowed_until_gate: G3
mutation_scope: Collider
adapter: LegacyWorldAuthoringAdapter
reason: awaiting typed preview migration
```

Reglas:

- La allowlist es cerrada y versionada.
- No se añaden consumidores después de cerrar G0.5 salvo ADR de emergencia.
- Cada entrada tiene owner, métrica, tests y gate de eliminación.
- El consumidor abre un `LegacyMutationLease` explícito que captura revisión, fingerprint inicial y scope permitido.
- Solo `LegacyWorldAuthoringAdapter.commit(lease)` puede importar temporalmente `World -> Scene`.
- El adapter calcula el diff y rechaza cualquier cambio fuera de `mutation_scope`.
- Save, autosave y PLAY nunca invocan ese adaptador.
- Un lease abierto bloquea acciones protegidas hasta commit o cancelación explícita.
- `force=True` queda prohibido fuera de tests del adaptador legacy.

### 6.7 Cambios obligatorios en `SceneEditSyncCoordinator`

- `prepare_for_save()` deja de convertir version mismatches en authoring.
- `sync_from_edit_world(force=True)` deja de ser una API de producción.
- `mark_edit_world_dirty()` emite métrica y warning deprecado.
- La sincronización legacy solo puede invocarse desde `LegacyWorldAuthoringAdapter` con lease válido.
- La selección no se importa desde `World` durante una sincronización legacy.
- Al final de G3, las herramientas principales no tienen consumidores.
- En G6 se elimina el coordinador si su contador llega a cero; el `ProjectionIntegrityGuard` permanece como infraestructura estable.

---

## 7. Consolidación ID-first y schema v3

El schema v2 ya dispone de IDs de entidad, pero conserva relaciones name-first. G1 introduce identidad estable de documento y establece schema v3 como formato de escritura.

### 7.1 Tipos de referencia

```python
@dataclass(frozen=True, slots=True)
class OpenDocumentId:
    value: str

@dataclass(frozen=True, slots=True)
class OpenSceneRef:
    document_id: OpenDocumentId

@dataclass(frozen=True, slots=True)
class SceneAssetRef:
    guid: str
    canonical_path_hint: str = ""

@dataclass(frozen=True, slots=True)
class EntityRef:
    scene: OpenSceneRef
    entity_id: str

@dataclass(frozen=True, slots=True)
class ComponentRef:
    entity: EntityRef
    component_type: str
```

`OpenDocumentId` se genera al abrir o crear la entrada y no cambia cuando la escena se guarda, renombra, mueve o rekeyea.

### 7.2 Distinción obligatoria

- `OpenSceneRef` identifica un documento abierto durante la sesión.
- `SceneAssetRef` identifica una escena persistida entre sesiones.
- `workspace_key`, nombre y path son localizadores mutables.
- Nunca se persisten `OpenDocumentId` ni `workspace_key`.
- `EntityRef` opera dentro de una escena abierta.
- Links, rules y referencias cross-scene usan `SceneAssetRef` y `entity_id`.
- Una escena untitled usa `OpenDocumentId`; al primer save recibe o resuelve su GUID de asset.

### 7.3 Schema v3

La escritura canónica v3 usa:

```text
entity.id
entity.parent_id
rules[*].actions[*].entity_id / target_entity_id
signals.connections[*].target.id
scene_links[*].target_scene.guid
scene_links[*].target_scene.path_hint
scene_links[*].target_entity_id
prefab references y overrides con IDs estables cuando el target pertenece al payload
```

Los nombres pueden conservarse como hints de diagnóstico o presentación, pero nunca son la clave autoritativa de resolución. `SceneProjectionService` puede materializar `parent_name` u otros índices name-based en `World` como detalle runtime reconstruible.

Política de compatibilidad:

- Reader: schema v2 y v3.
- Writer después del cutover de G1: solo schema v3.
- Migración v2 -> v3: determinista para referencias locales resolubles.
- Referencias cross-scene no resolubles: se conservan como compatibilidad diagnosticada y bloquean la confirmación de migración; no se inventan IDs.
- Antes de reescribir un archivo se crea backup o snapshot recuperable.
- No existe downgrade automático v3 -> v2.
- El loader v2 puede permanecer después de G6 como migrador de formato, no como ruta de authoring legacy.

### 7.4 Migración de referencias

Orden obligatorio:

1. Asignar `OpenDocumentId` a todas las entradas abiertas.
2. Asignar/resolver `SceneAssetRef` para escenas persistidas.
3. Migrar selección a `EntityRef`.
4. Migrar `parent` a `parent_id`.
5. Create/delete/rename/reparent por ID.
6. Component add/remove/update por ID.
7. Prefab roots y overrides.
8. Signals.
9. Rules/actions.
10. Scene links y entry points.
11. Viewport tools.
12. EngineAPI y CLI.
13. Eliminar resoluciones internas name-first.

### 7.5 Compatibilidad name-first

Las APIs por nombre:

- Viven en `engine/scenes/compat/name_first.py`.
- Resuelven exactamente una vez a `EntityRef`.
- Devuelven errores de ambigüedad/no resolución explícitos.
- Emiten métrica de consumidor.
- No son utilizadas por paneles migrados.
- Se eliminan en G6.
- Nunca son llamadas desde una API ID-first.

### 7.6 Criterios de salida

- Guardar o mover una escena no invalida refs de sesión.
- Rename no obliga a descubrir identidad mediante nombre.
- Todas las operaciones internas reciben refs.
- APIs `*_by_id` no convierten nuevamente a nombre.
- IDs duplicados bloquean carga o migración.
- Round-trip v3 preserva IDs y referencias.
- La migración v2 -> v3 produce un informe reproducible.
- Referencias no resolubles generan diagnóstico estable.
- El writer de producción no emite `parent` o targets name-first como autoridad.

---

## 8. Composition root no distribuible

### 8.1 `EngineCompositionRoot`

Es el único lugar autorizado para construir el grafo. Corrige el composition root distribuido actual sin reemplazarlo por un service locator:

```python
@dataclass(frozen=True, slots=True)
class EngineCompositionRoot:
    runtime_host: RuntimeHost | None
    editor_host: EditorHost | None
```

Puede usar builders internos, pero no se distribuye como dependencia.

### 8.2 `EditorHost`

```python
@dataclass(frozen=True, slots=True)
class EditorHost:
    application: EditorApplication
    shell: EditorShell
    platform: EditorPlatform
```

El host coordina ciclo de ventana e input; no ejecuta authoring.

### 8.3 Contratos por capacidad

Ejemplos:

```python
class HierarchyCommands(Protocol):
    def create_entity(self, scene: OpenSceneRef, parent: EntityRef | None) -> Result[EntityRef]: ...
    def rename_entity(self, entity: EntityRef, name: str) -> Result[None]: ...
    def reparent_entity(self, entity: EntityRef, parent: EntityRef | None) -> Result[None]: ...
    def delete_entity(self, entity: EntityRef) -> Result[None]: ...

class HierarchyQueries(Protocol):
    def hierarchy(self, scene: OpenSceneRef) -> SceneHierarchyView: ...
```

`HierarchyPresenter` recibe solo esos dos contratos. El inspector, assets, flow y export reciben contratos equivalentes de su capacidad.

### 8.4 Command bus

No se crea un `EditorCommandBus` genérico durante esta migración.

Se reconsiderará únicamente mediante ADR si aparecen necesidades reales de:

- Middleware transversal.
- Replay.
- Ejecución remota.
- Cola diferida.
- Autorización.
- Plugins externos.

Mientras no existan, llamadas directas tipadas son la opción obligatoria.

### 8.5 Eventos

Existe un publicador post-commit mínimo:

```python
class PostCommitEventPublisher(Protocol):
    def publish(self, event: DomainEvent) -> None: ...
```

Reglas:

- Publica solo después de un commit exitoso.
- Un evento no ejecuta automáticamente otra mutación.
- Los handlers actualizan caches, read models, telemetría o UI.
- Una reacción que necesite escribir debe invocar explícitamente otro caso de uso.
- Runtime events y editor events son buses distintos.

---

## 9. Resultados y transacciones tipadas

La adopción es incremental: toda API nueva de aplicación usa `Result`; la superficie legacy conserva temporalmente `bool`/`Optional` mediante adaptadores que traducen errores y registran métricas.

### 9.1 Resultado discriminado

```python
from enum import StrEnum

T = TypeVar("T")

class CommandErrorCode(StrEnum):
    NOT_FOUND = "NOT_FOUND"
    VALIDATION_FAILED = "VALIDATION_FAILED"
    CONFLICT = "CONFLICT"
    PROJECTION_DIVERGED = "PROJECTION_DIVERGED"
    PREVIEW_ACTIVE = "PREVIEW_ACTIVE"
    PERSISTENCE_FAILED = "PERSISTENCE_FAILED"
    INTERNAL_ERROR = "INTERNAL_ERROR"

@dataclass(frozen=True, slots=True)
class CommandError:
    code: CommandErrorCode
    user_message: str
    technical_details: str | None = None
    field: str | None = None

@dataclass(frozen=True, slots=True)
class MutationMetadata:
    changed_entities: tuple[EntityRef, ...] = ()
    history_entry_id: str | None = None
    scene_revision: int | None = None

@dataclass(frozen=True, slots=True)
class Ok(Generic[T]):
    value: T
    metadata: MutationMetadata = MutationMetadata()

@dataclass(frozen=True, slots=True)
class Err:
    error: CommandError

Result = Ok[T] | Err
```

Este diseño impide combinaciones inválidas de `success`, `value` y `error`.

### 9.2 Adaptación legacy

```python
class LegacyResultAdapter:
    @staticmethod
    def to_bool(result: Result[object]) -> bool: ...

    @staticmethod
    def to_optional(result: Result[T]) -> T | None: ...
```

Reglas:

- Los adapters viven en `compat/`.
- Registran código de error y consumidor.
- No eliminan diagnostics en logs/tests.
- Ninguna API nueva devuelve `bool` por comodidad.
- No se realiza un big-bang de todos los callers en G1.

### 9.3 Semántica de mutación

Cada caso de uso:

1. Resuelve refs estables.
2. Valida precondiciones y revisión base.
3. Captura snapshot o delta.
4. Muta `Scene` mediante una frontera interna.
5. Valida schema e invariantes.
6. Actualiza la proyección.
7. Recalcula evidencia de integridad.
8. Registra historial.
9. Marca dirty.
10. Publica eventos post-commit.
11. Devuelve `Ok`.

Ante fallo:

- Restaura estado.
- Reconstruye una proyección válida si fue alterada.
- No publica eventos.
- No deja historial parcial.
- No cambia dirty state salvo restauración del valor previo.
- Devuelve `Err` esperado o traduce la excepción inesperada en la frontera de aplicación.

---

## 10. Previews tipados

### 10.1 Separación entre lifecycle y estado

G0.5 introduce `PreviewLeaseRegistry` únicamente para lifecycle. G3 introduce fronteras públicas tipadas por herramienta. No se acepta una API pública genérica con `kind: str`, `state: object` o `dict[str, Any]` como estado principal.

### 10.2 Estados por herramienta

```python
@dataclass(frozen=True, slots=True)
class TransformPreviewState:
    x: float
    y: float
    rotation: float
    scale_x: float
    scale_y: float

@dataclass(frozen=True, slots=True)
class RectTransformPreviewState:
    anchored_x: float
    anchored_y: float
    width: float
    height: float

@dataclass(frozen=True, slots=True)
class ColliderPreviewState:
    shape_type: ColliderShapeType
    width: float
    height: float
    radius: float
    offset_x: float
    offset_y: float

@dataclass(frozen=True, slots=True)
class TilemapStrokePreviewState:
    layer_id: str
    cells: tuple[TileCellEdit, ...]
```

Los enums y DTOs específicos sustituyen strings libres cuando el dominio dispone de un conjunto cerrado.

### 10.3 Handles y control de concurrencia

```python
@dataclass(frozen=True, slots=True)
class TransformPreviewHandle:
    lease_id: str
    target: EntityRef
    base_scene_revision: int

class TransformPreviewCommands(Protocol):
    def begin(self, entity: EntityRef) -> Result[TransformPreviewHandle]: ...
    def update(self, handle: TransformPreviewHandle, state: TransformPreviewState) -> Result[None]: ...
    def commit(self, handle: TransformPreviewHandle, state: TransformPreviewState) -> Result[None]: ...
    def cancel(self, handle: TransformPreviewHandle, reason: PreviewCancelReason) -> Result[None]: ...
```

Se crean contratos equivalentes para camera, RectTransform, collider y tilemap. Puede existir infraestructura genérica interna, pero la frontera pública permanece tipada.

Política:

- Solo existe un preview de escritura por target y capacidad.
- Overlays de solo lectura pueden coexistir.
- `commit` comprueba que `Scene.revision == base_scene_revision` o aplica una política de rebase explícita.
- Un conflicto de revisión cancela el preview y devuelve `CONFLICT`; nunca sobrescribe silenciosamente otro cambio.

### 10.4 Política de conflicto y cancelación

Un preview se cancela si:

- El target desaparece.
- Cambia la escena activa.
- Cambia el proyecto.
- Se entra en PLAY.
- Comienza una operación incompatible.
- Se pierde pointer capture.
- Se ejecuta undo/redo.
- Save/autosave necesita continuar.
- Cambia la revisión base.
- Falla una validación final.

La cancelación:

- Restaura el overlay o la proyección temporal.
- Libera el lease incluso si la restauración produce un error diagnosticado.
- No modifica dirty state.
- Deja la proyección canónica verificable por el guard.

### 10.5 Commit

- `update` no cambia `Scene`.
- `commit` ejecuta exactamente un caso de uso.
- La entrada de historial describe estado inicial y final.
- El commit recalcula la evidencia de integridad.
- Si commit falla, se cancela y se reconstruye la proyección.
- El dirty state solo cambia después del commit.

---

## 11. Encapsulación de `Scene`

### 11.1 Superficie pública final

```python
class Scene:
    @property
    def name(self) -> str: ...

    @property
    def revision(self) -> int: ...

    def snapshot(self) -> SceneSnapshot: ...
    def to_dict(self) -> dict[str, JsonValue]: ...
    def find_entity_view(self, entity_id: str) -> EntityView | None: ...
    def list_entity_views(self) -> tuple[EntityView, ...]: ...
    def rules_view(self) -> tuple[RuleView, ...]: ...
    def feature_metadata_view(self) -> FeatureMetadataView: ...
```

Todos los retornos son DTOs inmutables o copias profundas. Ninguna búsqueda pública devuelve el diccionario almacenado internamente.

### 11.2 Superficies que se cierran

La transición cubre conjuntamente:

```text
Scene.data
Scene.entities_data
Scene.rules_data
Scene.feature_metadata
Scene.find_entity(...)
Scene.find_entity_by_id(...)
Cualquier getter que retorne una colección o dict interno
```

Cerrar solo `data` no satisface el gate.

### 11.3 Mutación interna

Las mutaciones solo se realizan mediante métodos de dominio internos o servicios de authoring:

```python
_scene_mutator.rename_entity(...)
_scene_mutator.replace_component(...)
_scene_mutator.reparent_entity(...)
```

Reglas:

- El mutator no se exporta desde `engine.scenes`.
- Solo se obtiene dentro de una transacción de aplicación.
- Toda mutación incrementa `Scene.revision` exactamente una vez por commit semántico.
- La validación y rollback pertenecen al pipeline, no a los paneles.

### 11.4 Transición

1. G0: inventario de todos los accesos y mutaciones.
2. G0.5: fitness test que impide nuevos accesos externos.
3. G1a: añadir snapshots/views y migrar lecturas críticas.
4. G1b: getters legacy devuelven copias profundas y emiten deprecation warning.
5. G3: consumidores productivos migrados a snapshots/views.
6. G6: propiedades y getters legacy eliminados o convertidos en API interna no exportada.

Una `MappingProxyType` superficial no es suficiente porque existen estructuras anidadas.

### 11.5 Fitness rules

Fuera de `engine/scenes/` queda prohibido:

```text
scene._data
scene.data[...]
scene.entities_data.append(...)
scene.rules_data.append(...)
scene.feature_metadata[...] = ...
scene.find_entity(...)[...] = ...
scene.find_entity_by_id(...)[...] = ...
```

Los accesos de lectura usan snapshots/views; las escrituras usan puertos.

---

## 12. Superficie final de compatibilidad de `SceneManager`

### 12.1 APIs que se conservan

Como fachada estable:

```text
runtime_port
authoring_port
workspace_port
```

Operaciones de workspace y lifecycle que pueden conservar wrapper directo por compatibilidad externa:

```text
create_new_scene
load_scene
load_scene_from_file
save_scene_to_file
list_open_scenes
activate_scene
close_scene
enter_play
exit_play
reload_scene
```

Condiciones:

- Los wrappers delegan a puertos.
- No contienen lógica propia.
- Devuelven resultados tipados en la API nueva.
- EngineAPI/CLI pueden conservar adaptadores de salida legacy por una ventana definida.
- Los wrappers nuevos reciben refs estables y devuelven `Result`; los wrappers legacy traducen en `compat/`.

### 12.2 APIs que se mueven a compat temporal

```text
create_entity(name)
remove_entity(name)
update_entity_property(name, ...)
apply_edit_to_world(name, ...)
find_entity_data(name)
get_component_data(name, ...)
set_selected_entity(name)
*_by_id que vuelvan internamente a nombre
```

Viven temporalmente en:

```text
engine/scenes/compat/scene_manager_legacy_facade.py
```

### 12.3 APIs que se eliminan

```text
sync_from_edit_world
sync_from_edit_world(force=True)
mark_edit_world_dirty
LegacyWorldAuthoringAdapter
restore_world como authoring
serialización genérica de World para persistencia
fallbacks directos de World
```

### 12.4 Criterio de retirada

Una API legacy solo se elimina cuando:

- Su métrica de consumidores es cero.
- No aparece en import graph de producción.
- EngineAPI y CLI tienen reemplazo.
- Los tests relevantes han migrado.
- La documentación ya no la presenta como pública.
- Existe nota de migración.

---

## 13. Estrategia UI

### 13.1 Gate de validación retained-mode

La foundation retained-mode existente se conserva. No se migra toda la UI hasta demostrar dos slices de producción:

- Jerarquía.
- Inspector básico.

Debe probar:

- Foco.
- Tab order.
- Pointer capture.
- Scroll.
- Clipping.
- Popups y z-order.
- Input simulado sin ventana para lógica principal.
- Rendimiento con escenas grandes.
- Ausencia de sincronización bidireccional con legacy.

### 13.2 Autoridad del shell

`EditorShell` posee:

- Foco.
- Hover global.
- Pointer capture.
- Popups.
- Z-order.
- Docking.
- Registro de paneles.
- Dispatch de input.

Los paneles no acceden a campos privados del layout ni procesan menús globales directamente.

### 13.3 Cutover

Un panel está migrado solo cuando:

- La implementación nueva es la única de producción.
- No existe feature flag de selección.
- No existe fallback legacy.
- No existe adaptador bidireccional.
- No recibe `SceneManager`, `Game` o `World` mutable.
- Tiene presupuesto y tests propios.
- El código legacy correspondiente se elimina.

---

## 14. Assets

Separación final:

```text
AssetCatalogService
AssetAuthoringService
AssetReferenceResolver
AssetImporterRegistry
ImageDecoderPort
ThumbnailService
FileSystemPort
```

Reglas:

- `ProjectPanel` no crea servicios.
- El panel no usa `os`, `Path.write_*`, `shutil` ni Raylib para dominio.
- Decodificación gráfica queda en infraestructura.
- Move/rename/reimport son comandos transaccionales cuando afectan referencias.
- Las referencias usan GUID como identidad cuando existe y path canónico como hint/resolución; mover o renombrar no cambia el GUID.
- Los thumbnails tienen cache, cancelación y presupuesto.

---

## 15. Reglas de dependencia

| Capa | Puede depender de | Prohibido |
|---|---|---|
| Scene domain | Tipos serializables y schema | `pyray`, editor, `Game` |
| Scene application | Domain, workspace, ports | UI concreta, workspace key como identidad |
| Editor application | Puertos específicos | `pyray`, paneles |
| UI presenters | Commands/queries de capacidad | Composition root, `Game`, `World` mutable |
| UI renderer | `ui_core`, plataforma | Authoring |
| Raylib platform | `pyray`, contratos plataforma | Reglas de Scene |
| Runtime | ECS y runtime services | `engine.editor` |
| Assets domain/application | Ports y referencias | UI y Raylib |
| Infrastructure | Implementaciones de ports | Decisiones de UI |

Fitness tests mínimos:

- `engine/runtime/**` no importa `engine/editor`.
- `engine/editor/ui_core/**` no importa `pyray`.
- Paneles migrados no importan `engine.scenes.scene_manager`.
- Paneles no llaman `world.create_entity`, `world.remove_entity` o mutadores persistentes.
- Fuera de scene domain no hay acceso mutable a `Scene`.
- No se inyecta `EditorCompositionRoot`.
- No se añade `Any` en contratos nuevos sin waiver ADR.

---

## 16. Owners y gobernanza

### 16.1 Accountable

- **Arquitectura y decisión final:** `@Yisuescopeta`.

### 16.2 Roles de owner

En un equipo de una sola persona, `@Yisuescopeta` puede cubrir varios roles, pero cada PR debe declarar el rol ejercido.

| Rol | Responsabilidad |
|---|---|
| Scene Domain Owner | Schema, `Scene`, authoring, proyección y persistencia |
| Editor Application Owner | Sesión, casos de uso, selección y composition |
| UI Platform Owner | Shell, retained-mode, docking, foco e input |
| Editor Tools Owner | Gizmos, collider, tilemap y previews |
| Assets Owner | Catálogo, importación, referencias y thumbnails |
| Runtime Owner | RuntimeHost, `RuntimeController` y aislamiento |
| Quality/Performance Owner | Tests, benchmarks, fitness rules y evidencias |

### 16.3 Paquetes de entrega y PRs

Los IDs `PR-Gxx-yy` son **paquetes de entrega verificables**, no una obligación de crear exactamente una PR por ID. Para un mantenedor único:

- Un paquete puede dividirse si excede un write set, mezcla rollback o produce un diff difícil de revisar.
- Paquetes consecutivos del mismo gate pueden agruparse si comparten write set, rollback y evidencia.
- No se agrupan dos write sets de alto riesgo salvo dependencia inseparable.
- Cada PR debe poder revertirse sin restaurar dual-write.
- El gate, no el número de PRs, es la unidad de cierre.

Cada PR incluye:

```text
Planning ID(s)
Gate
Owner role
Write set
Contracts modified
Legacy consumer removed
Tests
Benchmark impact
Rollback
Documentation
```

No se mezclan cambios de schema, cutover UI y eliminación legacy no relacionada en una misma PR.


### 16.4 Revisión

- No se aprueba una PR con CI rojo.
- Cambios de contrato requieren ADR o actualización del plan.
- Si no hay segundo mantenedor, se exige una segunda pasada de review separada del desarrollo, checklist completa y diff limpio.
- Un gate no se cierra por número de commits; se cierra por evidencia.

---

## 17. Presupuestos de calidad y rendimiento

Los valores son objetivos iniciales. G0 captura el baseline real en una máquina documentada y genera `benchmarks/budget.json`. Solo pueden relajarse mediante ADR con evidencia.

### 17.1 Máquina de referencia

Se registra en:

```text
benchmarks/reference_machine.json
```

Incluye CPU, RAM, GPU, sistema operativo, Python, Raylib, resolución, modo headless/ventana y configuración.

### 17.2 Escenas de benchmark

| Escena | Entidades | Componentes medios | Objetivo |
|---|---:|---:|---|
| Small | 100 | 4 | interacción básica |
| Medium | 1.000 | 5 | uso habitual |
| Large | 5.000 | 5 | stress de jerarquía |
| XL serialization | 10.000 | 4 | save/load e integridad |

### 17.3 Presupuestos de integridad

| Métrica | Presupuesto inicial |
|---|---:|
| Fast path de stamp/revisión | `< 0,5 ms p95` |
| Fingerprint canónico Small | `< 15 ms p95` |
| Fingerprint canónico Medium | `< 60 ms p95` |
| Fingerprint canónico Large | `< 250 ms p95` |
| Fingerprint canónico XL | `< 800 ms p95` |
| Falsos negativos en corpus de mutaciones | `0` |
| Mutación directa sin `touch_*` detectada | `100%` en tests de autoridad |

El fingerprint profundo se ejecuta en acciones protegidas, no por frame. Si el baseline supera el objetivo, el gate no puede empeorar más de 10% y debe incluir una mejora o ADR.

### 17.4 Presupuestos funcionales iniciales

| Métrica | Presupuesto |
|---|---:|
| Build frío de hierarchy view, 5k | `< 25 ms p95` |
| Actualización incremental hierarchy | `< 4 ms p95` |
| Render CPU jerarquía visible | `< 4 ms p95/frame` |
| Render CPU inspector básico | `< 3 ms p95/frame` |
| UI total CPU editor | `< 8 ms p95/frame` a 60 FPS |
| Commit transform preview | `< 6 ms p95` en Medium, sin contar fingerprint de acción protegida |
| Undo/redo transform | `< 8 ms p95` en Medium |
| Save Small completo | `< 75 ms p95` |
| Save Medium completo | `< 250 ms p95` |
| Save XL completo | `< 1.200 ms p95` |
| Regresión de memoria por gate | `< 10%` frente a baseline comparable |
| Regresión de tiempo total suite | `< 15%` sin justificación |
| Nuevos warnings de compatibilidad | `0` fuera de allowlist |

### 17.5 Estabilidad de benchmark

- Cinco warmups y al menos veinte muestras para microbenchmarks.
- p50, p95, máximo y desviación relativa.
- Mismo commit, máquina y configuración para comparación.
- Un benchmark con variación relativa superior al 15% se marca inestable y no decide un gate hasta corregirse.
- Los visual benchmarks separan lógica headless de coste de render real.

### 17.6 Presupuestos arquitectónicos

| Métrica | Objetivo final |
|---|---:|
| Consumidores `mark_edit_world_dirty` | 0 |
| Consumidores `sync_from_edit_world` | 0 |
| Consumidores `LegacyWorldAuthoringAdapter` | 0 |
| Paneles con `SceneManager` concreto | 0 |
| Paneles con `World` mutable | 0 |
| APIs name-first internas | 0 |
| Adaptadores bidireccionales | 0 |
| Feature flags de cutover | 0 |
| Imports runtime -> editor/inspector | 0 |
| Accesos externos mutables a `Scene` | 0 |
| Refs de sesión basadas en workspace key/path | 0 |
| Writer de schema v2 | 0 |

---

## 18. Gates de ejecución

# G0 — Rebaseline, observabilidad y guardrails

**Owner:** Quality/Performance Owner
**Accountable:** `@Yisuescopeta`
**Dependencias:** ninguna.

### Trabajo

- Inventario AST/import graph.
- Inventario de todas las superficies mutables de `Scene`.
- Inventario de consumidores `World -> Scene`, incluyendo mutaciones sin `touch_*`.
- Corpus de mutaciones directas por familias de componentes.
- Métricas de consumidores legacy.
- Baseline funcional y de rendimiento.
- Golden tests EDIT/PLAY/STOP.
- Tests save/load/undo/redo/switch.
- Clasificación documental: `foundation`, `partial`, `production`, `retired`.
- Fitness tests que impidan deuda nueva.
- Especificación del payload canónico usado para fingerprint.

### Paquetes de entrega

- `PR-G00-01`: inventario, import graph y métricas de compatibilidad.
- `PR-G00-02`: corpus de mutaciones y tests que demuestran los límites de `World.version`.
- `PR-G00-03`: fitness rules e import boundaries.
- `PR-G00-04`: benchmark harness, escenas de referencia y budget file.

### Salida

- Inventario con owner y gate de eliminación.
- Baseline reproducible.
- Test rojo que demuestra una mutación directa sin `touch_*` en el comportamiento actual.
- Contrato de canonicalización aprobado.
- CI bloquea nuevas mutaciones directas y nuevas exposiciones mutables de `Scene`.
- No cambia semántica de producción.

### Rollback

Retirar únicamente instrumentación defectuosa; nunca retirar tests de frontera, corpus ni reglas ya validadas.

---

# G0.5 — Cuarentena fail-closed de `EditWorld`

**Owner:** Scene Domain Owner
**Support:** Quality/Performance Owner, Editor Tools Owner
**Dependencias:** G0.

### Trabajo

- Introducir `AuthoringProjectionFingerprintService`.
- Introducir `ProjectionIntegrityEvidence` y `ProjectionIntegrityGuard`.
- Introducir `PreviewLeaseRegistry` mínimo.
- Proteger save/autosave/PLAY/switch/close/project switch/reload/export.
- Cambiar PLAY para construir runtime desde `Scene` validada.
- Eliminar sync automática por version mismatch.
- Prohibir `force=True` en producción.
- Crear `LegacyWorldAuthoringAdapter` y allowlist cerrada.
- Añadir diagnóstico y recuperación explícita.
- Hacer que save falle ante divergencia no registrada, incluso sin `touch_*`.

### Paquetes de entrega

- `PR-G05-01`: canonical fingerprint y evidencia de proyección.
- `PR-G05-02`: integrity guard y tests de autoridad sin `touch_*`.
- `PR-G05-03`: save/autosave fail-closed.
- `PR-G05-04`: PLAY/switch/close/project/reload/export fail-closed.
- `PR-G05-05`: preview lease registry mínimo.
- `PR-G05-06`: adapter legacy, allowlist y métricas.

### Salida

- Un cambio directo en `EditWorld` no puede entrar en disco.
- Una mutación de componente sin `touch_*` se detecta.
- Preview no puede entrar en save.
- PLAY no comienza con proyección divergente y se construye desde `Scene`.
- Scene switch valida la escena saliente.
- Todos los consumidores legacy están registrados.
- Save y lifecycle no invocan `LegacyWorldAuthoringAdapter`.

### Rollback

Se puede desactivar temporalmente un check solo mediante configuración de diagnóstico local, nunca en release ni CI. No se restaura serialización automática. Un rollback conserva el fingerprint, los tests de autoridad y la prohibición de `force=True`.

---

# G1 — Identidad estable, schema v3 y encapsulación de `Scene`

**Owner:** Scene Domain Owner
**Support:** Editor Application Owner, Assets Owner
**Dependencias:** G0.5.

### Trabajo

- Introducir `OpenDocumentId`, `OpenSceneRef`, `SceneAssetRef`, `EntityRef` y `ComponentRef`.
- Hacer que save/rekey conserve `OpenDocumentId`.
- Diseñar e implementar migración schema v2 -> v3.
- Asignar/resolver GUID de assets de escena.
- Migrar `parent` y referencias locales a IDs.
- Corregir APIs ID-first que vuelven a nombre.
- Migrar selección y operaciones estructurales.
- Encapsular todas las superficies mutables de `Scene`.
- Introducir `Result` en contratos nuevos y adapters legacy.
- Crear compat name-first aislada.
- Migrar referencias de prefab, signals, rules y scene links por fases.

### Paquetes de entrega

- `PR-G10-01`: identidad estable de documento y refs.
- `PR-G10-02`: schema v3, migrador, backups e informe de migración.
- `PR-G10-03`: `Result`, catálogo de errores y adapters legacy.
- `PR-G10-04`: snapshots/views y deprecación de getters mutables.
- `PR-G10-05`: create/delete/rename/reparent ID-first y `parent_id`.
- `PR-G10-06`: componentes ID-first.
- `PR-G10-07`: prefab, signals, rules y referencias cross-scene.
- `PR-G10-08`: fachada name-first temporal y métricas.

### Salida

- Guardar, mover o rekeyear una escena no invalida refs de sesión.
- Panel o caso de uso nuevo puede operar exclusivamente por refs.
- Ningún getter público de `Scene` expone referencia mutable.
- Rename preserva identidad.
- Round-trip v3 conserva IDs y referencias.
- Migración v2 -> v3 es determinista o produce diagnóstico bloqueante.
- Ninguna API ID-first vuelve internamente a nombre.
- El writer de producción emite schema v3.

### Rollback

Mantener reader/migrador v2 y compat name-first temporal. No revertir `OpenDocumentId`, no reabrir estructuras mutables y no volver a escribir schema v2.

---

# G2 — Composition root no distribuible y autoridad de sesión

**Owner:** Editor Application Owner
**Support:** UI Platform Owner, Runtime Owner
**Dependencias:** G1.

### Trabajo

- Crear `EngineCompositionRoot`, `EditorHost` y `EditorApplication`.
- No exponer el root a consumidores.
- Crear `EditorSession` con selección `EntityRef | None` y escena activa por `OpenDocumentId`.
- Migrar selección, escena activa, modo y pestaña.
- Sustituir `request_*` por métodos/eventos consumibles.
- Introducir contratos por capacidad.
- Crear publicador post-commit.

### Paquetes de entrega

- `PR-G20-01`: composition root y hosts mínimos.
- `PR-G20-02`: `EditorSession` y selección única.
- `PR-G20-03`: casos de uso/queries de jerarquía.
- `PR-G20-04`: sustitución inicial de `request_*`.
- `PR-G20-05`: post-commit events y cache invalidation.

### Salida

- `Game` no recibe wiring nuevo individual y deja de crecer como god object.
- Ningún panel recibe composition root.
- Selección tiene una autoridad.
- Las acciones migradas no dependen de flags persistentes.
- Runtime y editor usan eventos separados.

### Rollback

`Game` puede seguir siendo host temporal, pero mantiene la composición única y no recupera service location.

---

# G3 — Previews tipados y cierre de herramientas legacy

**Owner:** Editor Tools Owner
**Support:** Scene Domain Owner, Editor Application Owner
**Dependencias:** G1 y G2.

### Trabajo

- Transform preview.
- Cámara preview.
- RectTransform preview.
- Collider preview.
- Tilemap stroke/fill preview.
- Cancelación uniforme mediante leases.
- Control de conflicto por `base_scene_revision`.
- Commit semántico único.
- Retirada progresiva de `mark_edit_world_dirty`.
- Tests de pérdida de target, pointer, undo, save y PLAY.

### Paquetes de entrega

- `PR-G30-01`: infraestructura interna y transform contract.
- `PR-G30-02`: transform gizmo cutover.
- `PR-G30-03`: cámara y RectTransform.
- `PR-G30-04`: collider.
- `PR-G30-05`: tilemap.
- `PR-G30-06`: eliminación de consumidores principales de edit sync.

### Salida

- Preview no cambia `Scene`.
- Commit produce una entrada de historial.
- Save/PLAY cancelan o bloquean correctamente.
- Herramientas principales no usan sync inverso.
- Un fallo o conflicto de commit restaura una proyección válida y libera el lease.

### Rollback

Reactivar temporalmente una vista antigua solo si envía commits por el caso de uso nuevo. No se reactiva sync genérica.

---

# G4 — Validación retained-mode

**Owner:** UI Platform Owner
**Support:** Quality/Performance Owner, Editor Application Owner
**Dependencias:** G2 y G3.

### Trabajo

- Slice de jerarquía.
- Slice de inspector básico.
- Foco, pointer, clipping, popups y teclado.
- Input simulado.
- Benchmark.
- Decisión go/no-go mediante ADR.

### Paquetes de entrega

- `PR-G40-01`: controles/foco/pointer necesarios.
- `PR-G40-02`: jerarquía retained slice.
- `PR-G40-03`: inspector básico retained slice.
- `PR-G40-04`: benchmark, visual tests y ADR go/no-go.

### Salida

- Presupuestos cumplidos.
- No hay pérdida funcional frente a legacy.
- No hay adaptador bidireccional.
- ADR aprueba retained-mode o prescribe correcciones concretas.
- No se introduce un tercer toolkit.

### Rollback

Detener migración general y corregir toolkit. Los casos de uso y read models se conservan.

---

# G5A — Cutover de jerarquía

**Owner:** UI Platform Owner
**Support:** Editor Application Owner, Scene Domain Owner
**Dependencias:** G4 aprobado.

### Trabajo

- Árbol virtualizado.
- Búsqueda.
- Selección ID-first.
- Reparent.
- Context actions.
- Teclado.
- Clipboard.
- Eliminación de `HierarchyPanel` legacy.

### Paquetes de entrega

- `PR-G5A-01`: presenter/read model definitivo.
- `PR-G5A-02`: vista retained de producción.
- `PR-G5A-03`: eliminar fallback y código legacy.

### Salida

- Una sola jerarquía de producción.
- Cero mutaciones directas de `World`.
- Cero dependencias concretas de `SceneManager`.
- Presupuesto de 5k entidades cumplido.

### Rollback

Restaurar el renderer legacy sobre el presenter nuevo, solo lectura y comandos nuevos; no restaurar mutaciones directas.

---

# G5B — Cutover del inspector básico

**Owner:** UI Platform Owner
**Support:** Editor Application Owner, Scene Domain Owner
**Dependencias:** G4 y G5A.

### Trabajo

- Entity header.
- Bool/int/float/string.
- Add/remove component.
- Validación.
- Commit/cancel.
- Read model incremental.
- Eliminación de rutas básicas de `InspectorSystem`.

### Paquetes de entrega

- `PR-G5B-01`: inspector queries y property contracts.
- `PR-G5B-02`: property editors retained.
- `PR-G5B-03`: cutover y eliminación básica legacy.

### Salida

- Propiedades básicas usan comandos tipados.
- No existe acceso mutable a componente runtime.
- Errores son visibles y tipados.
- Presupuesto del inspector cumplido.

### Rollback

Renderer legacy puede consumir el nuevo read model y commands; no recibe objetos mutables.

---

# G5C — Viewport e inspector especializado

**Owner:** Editor Tools Owner
**Support:** UI Platform Owner, Scene Domain Owner
**Dependencias:** G3 y G5B.

### Trabajo

- Collider UI.
- Tilemap palette/tools.
- Animator/camera specialized editors.
- Drag & drop de assets.
- Overlays de viewport.
- División final de `InspectorSystem`.

### Paquetes de entrega

- `PR-G5C-01`: specialized editor registry tipado.
- `PR-G5C-02`: collider UI cutover.
- `PR-G5C-03`: tilemap UI cutover.
- `PR-G5C-04`: animator/camera y asset fields.
- `PR-G5C-05`: eliminar `InspectorSystem` monolítico.

### Salida

- Todas las herramientas especializadas usan previews/casos de uso.
- `InspectorSystem` deja de ser autoridad.
- No quedan consumidores productivos de edit sync.
- Viewport no escribe persistencia directamente.

### Rollback

Cada specialized editor puede desactivarse individualmente usando el presenter anterior sobre contratos nuevos.

---

# G5D — Assets y Project Browser

**Owner:** Assets Owner
**Support:** UI Platform Owner, Editor Application Owner
**Dependencias:** G2 y G4.

### Trabajo

- Separar catálogo y authoring.
- Extraer filesystem y decoder.
- Migrar thumbnails.
- Migrar move/rename/reimport.
- Cutover de project browser.
- Eliminar creación interna de servicios.

### Paquetes de entrega

- `PR-G5D-01`: asset ports y separación service.
- `PR-G5D-02`: filesystem/decoder/thumbnail adapters.
- `PR-G5D-03`: asset commands y referencia canónica.
- `PR-G5D-04`: project browser retained.
- `PR-G5D-05`: eliminar `ProjectPanel` legacy y facade monolítica.

### Salida

- Panel sin filesystem directo.
- Servicios de dominio sin Raylib.
- Referencias se mantienen tras move/rename.
- Thumbnail cache cumple presupuesto.
- Una sola vista de assets.

### Rollback

Vista legacy consume `AssetCatalogView` y commands nuevos; no crea servicios ni toca filesystem.

---

# G5E — Paneles auxiliares y shell completo

**Owner:** UI Platform Owner
**Support:** owners de capacidad
**Dependencias:** G4; cada panel declara dependencias adicionales.

### Trabajo

- Console.
- Flow.
- Animator panel.
- Terminal.
- Agent.
- Export.
- Launcher.
- DockWorkspace y PanelRegistry definitivos.
- Eliminación de `EditorPanelSlots` y flags de cutover.

### Paquetes de entrega

- `PR-G5E-01`: console y logs.
- `PR-G5E-02`: flow.
- `PR-G5E-03`: animator panel.
- `PR-G5E-04`: terminal y agent.
- `PR-G5E-05`: export y launcher.
- `PR-G5E-06`: PanelRegistry/DockWorkspace cutover.
- `PR-G5E-07`: eliminar slots, adapters y feature flags.

### Salida

- Una única arquitectura UI.
- Un único foco/input authority.
- Cero adaptadores bidireccionales.
- Cero flags de selección legacy/new.
- Layout persistido y recuperable.

### Rollback

Por panel, usando presenters y contratos nuevos. No se restaura el shell legacy como autoridad global.

---

# G6 — Hosts, aislamiento y eliminación final

**Owner:** Runtime Owner
**Support:** todos los owners
**Dependencias:** G5A–G5E.

### Trabajo

- Extraer `RuntimeHost` y `EditorHost` definitivos.
- Reducir `Game` a fachada o eliminarlo como composition root.
- Eliminar `SceneEditSyncCoordinator`.
- Eliminar name-first interno.
- Eliminar todas las superficies mutables legacy de `Scene`.
- Eliminar legacy facades sin consumidores.
- Conservar el reader/migrador de schema v2 como compatibilidad de archivo, no como writer ni authoring path.
- Corregir documentación pública.
- Ejecutar validación final y benchmark comparativo.

### Paquetes de entrega

- `PR-G60-01`: RuntimeHost/EditorHost cutover.
- `PR-G60-02`: eliminar edit sync.
- `PR-G60-03`: eliminar name-first y todas las superficies mutables legacy de `Scene`.
- `PR-G60-04`: eliminar facades, shims y flags.
- `PR-G60-05`: documentación, migración y release validation.

### Salida

- Runtime no importa editor ni inspector.
- Cero rutas `World -> Scene` en producción; solo fixtures de migración histórica.
- Cero mutaciones directas desde paneles.
- Cero compatibilidad sin consumidores.
- `Game` no es composition root distribuido ni service locator.
- Benchmarks no exceden presupuestos.
- Documentación coincide con producción.

### Rollback

Rollback por PR, no restauración global de arquitectura legacy. Una retirada que revele consumidor oculto se corrige mediante adaptador explícito y con gate de eliminación.

---

## 19. Secuencia de paquetes prioritaria

Los paquetes iniciales deben ejecutarse en este orden. Pueden agruparse en PRs si respetan write sets, rollback y revisión:

1. `PR-G00-01` — inventario y métricas.
2. `PR-G00-02` — corpus de mutaciones sin `touch_*`.
3. `PR-G00-03` — fitness rules.
4. `PR-G00-04` — benchmarks.
5. `PR-G05-01` — fingerprint canónico.
6. `PR-G05-02` — integrity guard y test de autoridad.
7. `PR-G05-03` — save/autosave fail-closed.
8. `PR-G05-04` — PLAY y lifecycle fail-closed.
9. `PR-G05-05` — preview lease registry.
10. `PR-G05-06` — adapter legacy y allowlist.
11. `PR-G10-01` — identidad estable de documento.
12. `PR-G10-02` — schema v3 y migración.
13. `PR-G10-03` — resultados tipados/adapters.
14. `PR-G10-04` — encapsulación de `Scene`.
15. `PR-G10-05` — operaciones estructurales ID-first.
16. `PR-G20-01` — composition root y hosts mínimos.
17. `PR-G20-02` — selección única.
18. `PR-G30-01` — transform preview contract.
19. `PR-G30-02` — transform cutover.
20. `PR-G40-01` — UI control gaps.
21. `PR-G40-02` — jerarquía slice.
22. `PR-G40-03` — inspector slice.
23. `PR-G40-04` — decisión go/no-go.

Después de G4, G5A y G5D pueden avanzar en paralelo si sus write sets son disjuntos. G5B y G5C son secuenciales. G5E se divide por panel.

No se inicia un cutover UI mientras existan fallos abiertos de integridad, identidad o migración de schema.

---

## 20. Write sets

| Área | Write set principal |
|---|---|
| Scene integrity | fingerprint service, integrity guard, `edit_sync.py`, persistence, workspace, tests |
| Identity/schema | schema v3, scene, workspace identity, asset refs, contracts, authoring services |
| Composition | `engine/core/game.py`, `engine/app`, editor application |
| Preview | editor interaction, gizmos, inspector tools, scene authoring |
| UI core | `engine/editor/ui_core`, renderer, shell |
| Hierarchy | hierarchy presenter/view/tests |
| Inspector | inspector presenters/editors/tests |
| Assets | `engine/assets`, project browser, infrastructure |
| Runtime isolation | runtime host, imports, exports |
| Legacy removal | compat namespaces, flags, adapters, docs |

Builders concurrentes solo si no escriben el mismo set o contrato.

---

## 21. Estrategia de tests

### 21.1 Unitarios

- Canonical fingerprint determinista.
- Fingerprint ignora selección y preview, pero incluye authoring.
- Result discriminado y adapters legacy.
- Ref resolvers y estabilidad de `OpenDocumentId` tras save/rekey.
- Migración schema v2 -> v3.
- Projection guard.
- Scene mutators y views inmutables.
- Preview lease registry y state machines.
- Queries/read models.
- Focus/pointer/layout.
- Asset services.

### 21.2 Tests de autoridad de integridad

Como mínimo, para cada familia representativa:

- Asignación directa a `Transform.x` sin `touch_*`.
- Cambio directo de collider.
- Cambio directo de una lista/dict anidado serializable.
- Creación/eliminación estructural.
- Cambio de metadata persistente.
- Cambio de selección que **no** debe considerarse divergencia.
- Preview registrado que debe cancelarse y no persistirse.

Cada caso se verifica contra save, PLAY y scene switch.

### 21.3 Integración

- Create/rename/reparent/save/load por refs.
- Save con mutación no registrada sin version bump.
- PLAY con preview activo.
- Save/rekey conserva `OpenDocumentId` y selección.
- Undo/redo tras preview commit.
- Scene switch con dirty, preview y divergencia.
- Migración v2 -> v3 y round-trip v3.
- Prefab rename/override.
- Asset move y referencias.
- Dock layout round-trip.

### 21.4 Contract tests

Cada implementación de port ejecuta la misma suite contractual. Los adapters legacy tienen una suite separada que exige equivalencia semántica y métrica de uso.

### 21.5 Arquitectónicos

- Import graph.
- AST mutation rules.
- Sin `Any` en contratos nuevos.
- Sin `SceneManager` en paneles migrados.
- Sin `pyray` en dominio.
- Sin runtime -> editor/inspector.
- Sin workspace key/path como identidad de refs.
- Sin writer schema v2.
- Sin getters mutables de `Scene` fuera del compat namespace.

### 21.6 Visuales

- Golden screenshots deterministas.
- Clipping.
- Popups.
- Jerarquía grande.
- Inspector de componentes.
- Dock restore.

### 21.7 Rendimiento

- p50, p95, máximo y variación.
- Warm/cold.
- Memoria.
- Cache hit rate.
- Fingerprint por tamaño de escena.
- Comparación con baseline del mismo commit, máquina y configuración.

---

## 22. Registro de riesgos

| Riesgo | Impacto | Mitigación | Owner |
|---|---|---|---|
| Guard basado solo en versiones produce falsos negativos | Crítico | Fingerprint canónico y tests sin `touch_*` | Scene Domain / Quality |
| Fingerprint profundo degrada acciones protegidas | Alto | Cache, canonicalización incremental futura y presupuestos por tamaño | Quality |
| Guard bloquea consumidores ocultos | Alto | Métricas G0, allowlist y adapter explícito G0.5 | Scene Domain |
| Save/rekey invalida referencias de sesión | Alto | `OpenDocumentId` inmutable y tests de estabilidad | Editor Application |
| Migración schema v3 pierde referencias | Crítico | Backup, informe determinista, bloqueo ante referencias no resolubles | Scene Domain |
| GUID de escena ausente o inconsistente | Alto | Asignación/resolución en AssetDatabase y auditoría | Assets |
| Pérdida de cambios al cancelar preview | Alto | Base state, leases y tests de conflicto | Editor Tools |
| Commit de preview pisa una revisión nueva | Alto | `base_scene_revision` y error `CONFLICT` | Editor Tools |
| Composition root se filtra a paneles | Alto | Fitness test de inyección/import | Editor Application |
| Eventos crean cadenas de mutación | Alto | Solo post-commit; no writes implícitos | Editor Application |
| Retained-mode no cumple input | Alto | Gate G4 y no-go real | UI Platform |
| G5 se vuelve interminable | Alto | G5A–G5E, paquetes agrupables y eliminación por panel | Architecture |
| Assets rompen referencias | Alto | GUID/path hint, transacciones y round-trip | Assets |
| Benchmarks inestables | Medio | Máquina/config fijas, repeticiones y umbral de variación | Quality |
| Rollback reintroduce dual-write | Alto | Rollback solo sobre contratos nuevos | Architecture |
| Encapsulación rompe consumidores ocultos | Medio | Inventario, warnings, snapshots y fitness tests | Scene Domain |
| Compat facade permanece indefinida | Alto | contador, owner, gate y CI final | Architecture |

---

## 23. ADRs obligatorios

- `ADR-001`: `Scene` como autoridad persistente.
- `ADR-002`: integridad híbrida fail-closed y canonical fingerprint.
- `ADR-003`: `OpenDocumentId`, `SceneAssetRef` y schema v3 ID-first.
- `ADR-004`: composition root no distribuible.
- `ADR-005`: casos de uso directos, `Result` incremental y ausencia de command bus genérico.
- `ADR-006`: eventos post-commit.
- `ADR-007`: preview lease lifecycle y previews tipados.
- `ADR-008`: decisión retained-mode.
- `ADR-009`: superficie final de `SceneManager`.
- `ADR-010`: separación de assets y autoridad de GUID/path hint.

---

## 24. Acciones prohibidas

1. Volver a serializar genéricamente `World` desde save o lifecycle.
2. Confiar en `World.version` como única prueba de integridad.
3. Hacer save best-effort ante divergencia.
4. Añadir consumidores a `mark_edit_world_dirty`.
5. Invocar `LegacyWorldAuthoringAdapter` desde save, autosave, PLAY o switch.
6. Llamar una API name-first desde una API ID-first.
7. Usar workspace key, ruta o nombre como identidad estable de documento abierto.
8. Persistir `OpenDocumentId`.
9. Escribir schema v2 después del cutover de G1.
10. Inventar IDs para referencias cross-scene no resolubles.
11. Inyectar `EngineCompositionRoot` o `EditorCompositionRoot`.
12. Crear un service locator alternativo.
13. Crear un command bus “por si acaso”.
14. Usar eventos para ejecutar mutaciones implícitas.
15. Crear previews públicos con `object`, `dict[str, Any]` o strings libres como contrato principal.
16. Abrir un preview sin lease.
17. Exponer cualquier estructura mutable interna de `Scene`.
18. Añadir feature flags sin gate de eliminación.
19. Mantener dos paneles de producción para la misma capacidad.
20. Mezclar un cutover UI con cambios de schema no relacionados.
21. Declarar estable una feature opt-in.
22. Cerrar un gate sin benchmarks y evidencia.
23. Aceptar un fallo conocido sin issue, owner y condición de desbloqueo.
24. Reintroducir fallbacks que cambian semántica.
25. Hacer rollback a una ruta de escritura legacy.
26. Ocultar un descarte explícito detrás de un resultado de guardado exitoso.

---

## 25. Primeros incrementos de valor

### Incremento 1 — Detección real de divergencia

- Canonical fingerprint.
- Test de mutación directa sin `touch_*`.
- Informe de integridad.
- Sin cambios visuales ni de persistencia todavía.

**Valor:** demuestra que el guard puede detectar el defecto que pretende cerrar.

### Incremento 2 — Save y lifecycle fail-closed

- Save/autosave protegidos.
- PLAY construido desde `Scene` validada.
- Scene/project switch, close, reload y export protegidos.
- Preview lease registry mínimo.
- Error visible y recuperación explícita.

**Valor:** impide corrupción semántica y ejecución sobre una proyección divergente.

### Incremento 3 — Identidad estable y schema v3

- `OpenDocumentId` conserva refs tras save/rekey.
- Migración v2 -> v3.
- Jerarquía local por `parent_id`.
- Backup e informe de referencias.

**Valor:** elimina la dependencia estructural de nombres y localizadores mutables.

### Incremento 4 — Jerarquía sin fallback

- Puerto obligatorio.
- Create/select/reparent por refs.
- Sin `world.create_entity`.
- Vista actual conservada temporalmente.

**Valor:** elimina una ruta alternativa real sin depender del cutover UI.

### Incremento 5 — Transform preview tipado

- Begin/update/commit/cancel con lease y revisión base.
- Una entrada de historial.
- Save y PLAY seguros.
- Eliminación del primer consumidor de transient sync.

**Valor:** prueba la frontera de authoring interactivo más difícil.

---

## 26. Definition of Done por PR

Una PR está terminada cuando:

- Tiene planning ID y gate.
- Declara owner y write set.
- No introduce autoridad alternativa.
- Incluye tests unitarios e integración relevantes.
- Incluye benchmark si toca hot path o acción protegida.
- Documenta contrato modificado.
- Tiene rollback compatible con la arquitectura nueva.
- Actualiza contador de consumidores legacy y, si aplica, informe de migración de schema.
- No añade warnings fuera de allowlist.
- CI está verde.
- Ninguna ref estable depende de workspace key/path.
- Ningún cambio de integridad depende solo de `World.version`.

## 27. Definition of Done por gate

Un gate está terminado cuando:

- Todos sus criterios de salida tienen evidencia reproducible.
- No existen fallos conocidos sin issue y owner.
- Los presupuestos se cumplen o existe ADR aprobado.
- Los adaptadores creados tienen eliminación asignada.
- El camino anterior se ha eliminado cuando sus consumidores son cero.
- La documentación refleja el estado real.
- La aplicación y la suite acordada se ejecutan desde `main`.
- El owner firma el cierre en el documento de gate.

---

## 28. Estado final esperado

Al terminar G6:

- `Scene` es canónica, versionada y encapsulada.
- `EditWorld` no puede entrar accidentalmente en persistencia.
- El guard detecta mutaciones aunque no exista version bump.
- Save, PLAY y lifecycle son fail-closed.
- No existe sync genérica `World -> Scene`.
- `OpenDocumentId` mantiene estable la identidad de documentos abiertos.
- El writer usa schema v3; schema v2 solo se conserva como formato migrable.
- Operaciones internas y relaciones persistentes son ID-first.
- Selección tiene una autoridad.
- Previews son registrados, tipados y conflict-aware.
- Los paneles reciben contratos pequeños.
- Composition root no se distribuye.
- `Game` deja de crecer como god object y no funciona como service locator.
- No existe command bus genérico.
- Eventos son post-commit.
- Existe una única UI de producción.
- Assets están separados por responsabilidad y conservan identidad mediante GUID.
- Runtime no importa editor ni inspector.
- `SceneManager` conserva solo su fachada estable y puertos.
- Legacy, flags, shims y facades sin consumidores han sido eliminados.
- Tests, benchmarks, migraciones y documentación describen la arquitectura real.

---

## 29. Decisión final

Este plan queda **aprobado para ejecución** en el orden de gates establecido.

La primera modificación productiva no será visual ni una nueva capa de UI. Antes de bloquear save debe existir una prueba que demuestre que el sistema detecta una asignación directa a un componente sin `touch_*`. Solo después se activará el comportamiento fail-closed en save, PLAY y lifecycle.

La ejecución prioriza, en este orden:

1. Probar integridad real.
2. Cerrar rutas automáticas `World -> Scene`.
3. Estabilizar identidad de documentos abiertos.
4. Migrar referencias persistentes a schema v3.
5. Encapsular `Scene` y adoptar casos de uso tipados.
6. Retirar consumidores legacy mediante vertical slices.
7. Validar y completar la UI retained-mode.
8. Eliminar físicamente compatibilidad, dualidades y wiring distribuido.

Cada contrato nuevo debe retirar deuda concreta; cada compatibilidad debe tener fecha de muerte; cada migración debe ser recuperable; y cada cutover debe terminar con eliminación física del camino anterior.

Un gate no se cierra por intención ni por número de commits. Se cierra únicamente cuando sus invariantes, tests de autoridad, migraciones y presupuestos tienen evidencia reproducible desde `main`.

---

## Registro de ejecución del repositorio

- Plan fuente: `D:\putas\OpenGame_plan_migracion_editor_v4.md`
- Copia registrada: 2026-07-22
- Rama de ejecución: `feat/EditorArchitectureUnification`
- Modo: flujo estándar, agente único; Reina no se utiliza.
- Estado inicial: working tree limpio; baseline dirigido de escena/lifecycle: 59 tests OK.
- Runtime de validación: Python bundled del entorno Codex; `py` no encuentra intérprete instalado.
- Política de commits: un commit autocontenido por paquete `PR-*`; documentación inicial tiene commit propio.
- Gate actual: G0 — `PR-G00-01` pendiente.

### Commits

| Commit | Gate | Estado | Evidencia |
|---|---|---|---|
| `docs: register editor migration plan v4` | Registro | Completado | Commit documental inicial; copia, ledger, índice, diff y gobernanza validados. |

### Actualizaciones

- 2026-07-22: plan copiado sin cambios; hash SHA-256 fuente/copia verificado.
