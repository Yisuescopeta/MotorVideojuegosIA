# Diseno de escenas chunked

Estado: Fase 1 parcial implementada.

Este documento propone una evolucion futura del formato de escenas para
proyectos grandes. No cambia el contrato vigente del motor.

El formato oficial actual sigue siendo una escena JSON con `schema_version = 2`.
`Scene` continua siendo la fuente persistente de verdad. `World` continua siendo
una proyeccion operativa. Las rutas publicas de authoring siguen siendo
`SceneManager` y `EngineAPI`.

La implementacion actual agrega `ChunkedSceneStorage` como backend experimental
opt-in interno. Solo soporta carpetas `.scene/` con manifest `scene.json` y
chunks secuenciales de entidades en `entities/chunk_*.json`. Carga todos los
chunks y reconstruye una `Scene` completa; no implementa streaming parcial,
dirty chunks, tilemaps chunked ni migracion automatica desde JSON.

## Objetivo

Permitir que una escena pueda representarse como una carpeta `Nombre.scene/`
con manifest, chunks de entidades, chunks de tilemap y metadata separada. La
meta es reducir coste de guardado incremental, facilitar escenas grandes y
preparar streaming futuro sin romper la ruta actual basada en `Scene`.

La primera implementacion compatible deberia cargar la carpeta `.scene/` y
reconstruir una `Scene` completa. El streaming parcial real queda para fases
posteriores.

## Comparacion con JSON actual

El formato actual guarda una escena completa en un unico archivo `.json` con:

- `schema_version`
- `name`
- `entities`
- `rules`
- `feature_metadata`

Ventajas del JSON actual:

- Es simple de leer, migrar y validar.
- Encaja directamente con `SceneManager.load_scene_from_file` y
  `SceneManager.save_scene_to_file`.
- Tiene una unica operacion de guardado y una unica fuente fisica de verdad.

Limitaciones en escenas grandes:

- Cualquier cambio puede reescribir el archivo completo.
- Los conflictos de merge son mas probables cuando muchas entidades o tiles
  comparten el mismo archivo.
- El formato no expresa carga parcial ni dirty state por region.

El formato propuesto usa una carpeta `.scene/` con manifest y datos
particionados. Sus beneficios esperados son:

- Guardado incremental por chunk.
- Menos conflictos de merge en equipos.
- Base para streaming de escenas grandes.
- Mejor separacion entre entidades, tilemaps y metadata.

Sus costes son:

- Validacion mas compleja.
- Mas operaciones de IO.
- Migraciones y herramientas de reparacion mas exigentes.
- Atomicidad de guardado mas dificil al escribir multiples archivos.

## Estructura propuesta

La estructura implementada en Fase 1 parcial es intencionalmente mas estrecha:

```text
levels/Level1.scene/
  scene.json
  entities/
    chunk_0000.json
    chunk_0001.json
```

`scene.json` contiene `name`, `schema_version`, `rules`, `feature_metadata`,
`storage_format`, `storage_version` y una lista `chunks`. Cada chunk actual es
de tipo `entities` y contiene `schema_version`, `chunk_index` y `entities`.

Una escena chunked vive en una carpeta:

```text
levels/Level1.scene/
  scene.json
  entities/
    region_0_0.json
    region_1_0.json
  tilemaps/
    Ground/
      chunk_0_0.json
      chunk_1_0.json
  metadata/
    editor.json
```

`scene.json` es el manifest principal. Debe contener:

- identidad de escena: nombre, id estable opcional y version del formato
  chunked
- version de schema de escena compatible con el contrato vigente
- `rules`
- `feature_metadata`
- politica de particion de entidades
- indice de chunks de entidades
- indice de chunks de tilemap
- metadata global necesaria para reconstruir una `Scene`
- informacion de compatibilidad para exportar a JSON actual

El manifest no debe duplicar el contenido completo de los chunks. Su funcion es
coordinar referencias y permitir validacion temprana.

## Chunks de entidades

Los chunks de entidades almacenan subconjuntos de `entities`. La politica de
particion debe estar declarada en `scene.json` para evitar ambiguedad. Politicas
posibles:

- region espacial fija, por ejemplo `region_x`, `region_y`
- grupo logico, por ejemplo `gameplay`, `ui`, `spawn`
- particion manual declarada por tooling

Cada chunk de entidades debe conservar payloads compatibles con las entidades
serializables actuales: identidad, estado, jerarquia, grupos, componentes y
referencias de prefab.

Restricciones de diseno:

- Una entidad pertenece a un unico chunk propietario.
- Las referencias entre entidades pueden cruzar chunks, pero se validan al
  reconstruir la escena completa.
- La jerarquia no puede depender del orden fisico de lectura de archivos.
- El resultado ensamblado debe producir el mismo contrato que una escena JSON
  `schema_version = 2`.

## Chunks de tilemap

Los tilemaps grandes deben poder partirse por layer y coordenada de chunk. La
estructura propuesta separa metadata de layer y celdas:

- metadata del componente `Tilemap` permanece en la entidad propietaria o en el
  manifest de tilemap.
- cada layer declara sus chunks disponibles.
- cada chunk almacena tiles de una region fija y su coordenada de chunk.

La base runtime actual de `Tilemap` ya usa chunks efimeros para render y dirty
state interno, pero esos chunks no son contrato persistente. Este diseno propone
una representacion persistente futura distinta, que debe migrar desde y hacia el
payload serializable actual de `Tilemap`.

## Metadata

`feature_metadata` sigue siendo el contenedor serializable transversal del core y
modulos oficiales. En formato chunked debe seguir reconstruyendose como
`feature_metadata` compatible con JSON actual.

El formato puede incluir metadata adicional:

- metadata global de escena
- metadata de particion
- metadata de editor
- metadata por chunk, como bounds, conteo de entidades, conteo de tiles,
  checksums o version local

La metadata auxiliar no debe introducir comportamiento publico inaccesible por
`SceneManager` o `EngineAPI`.

## Dirty chunks

Dirty chunks es estado de authoring/workspace, no estado runtime persistido sin
control. Debe respetar las invariantes actuales:

- mutaciones runtime en `PLAY` no se guardan como authoring por accidente
- `Scene` sigue siendo la fuente persistente de verdad ensamblada
- `SceneManager` coordina dirty state del workspace

Un cambio de authoring debe marcar dirty el chunk propietario y, si afecta
indices globales, tambien el manifest. Ejemplos:

- editar `Transform` de una entidad marca su chunk de entidad
- mover una entidad a otra region marca origen, destino y manifest si cambia el
  indice
- cambiar un tile marca el chunk de tilemap correspondiente
- cambiar `feature_metadata` marca el manifest

El guardado incremental debe poder escribir solo chunks dirty, pero la operacion
debe mantener consistencia entre manifest e indices. Una fase inicial puede
usar guardado atomico conservador escribiendo a temporales y reemplazando al
final.

## Migracion desde JSON actual

La migracion debe ser explicita. Cargar un JSON actual no debe convertirlo
automaticamente a `.scene/` sin una accion dedicada.

Flujo propuesto:

1. Cargar y validar el JSON actual con los migradores existentes hasta
   `schema_version = 2`.
2. Crear carpeta `Nombre.scene/` en una ruta destino.
3. Escribir `scene.json` con `rules`, `feature_metadata` e indices vacios.
4. Particionar `entities` segun politica elegida.
5. Extraer tilemaps grandes a chunks de tilemap cuando aplique.
6. Validar que la escena ensamblada desde `.scene/` equivale al JSON canonico.
7. Mantener exportacion `.scene/` -> JSON durante la fase experimental.

La migracion inicial debe ser reversible para facilitar pruebas, rollback y
comparacion con el contrato vigente.

## Compatibilidad con SceneManager

La compatibilidad inicial no debe crear una ruta paralela de authoring. La
integracion propuesta es:

- lector experimental de `.scene/` ensambla un payload canonico de escena
- `SceneManager` carga ese payload como `Scene` completa
- las mutaciones publicas siguen pasando por `SceneManager` o `EngineAPI`
- el guardado chunked se habilita solo cuando el workspace sabe que la escena
  proviene de una carpeta `.scene/`

Mientras no exista integracion dedicada, `load_scene_from_file` y
`save_scene_to_file` siguen siendo rutas JSON. No debe documentarse soporte
publico de `.scene/` en CLI ni API hasta que exista codigo y tests.

## API futura de streaming

La API publica futura debe ser aditiva y no debe reemplazar las operaciones
actuales de escena. Posibles capacidades:

- abrir una escena chunked sin cargar todos los chunks
- consultar chunks disponibles y bounds
- cargar chunks por region o por camara
- descargar chunks no usados
- consultar dirty chunks
- guardar chunks dirty
- exportar a JSON actual para compatibilidad

Esta API es tentativa. No existe todavia y no debe aparecer en `docs/api.md` ni
`docs/cli.md` como capacidad disponible.

## Plan por fases

### Fase 0: documento de diseno

Crear este documento y enlazarlo desde el portal documental como plan futuro.
No se implementa formato, API, CLI ni migrador.

### Fase 1: helpers internos experimentales

Agregar lectura/escritura interna de carpetas `.scene/` detras de helpers
privados. JSON sigue siendo el formato oficial. Los helpers deben ensamblar y
validar un payload equivalente al JSON actual.

### Fase 2: migrador reversible

Agregar migrador JSON -> `.scene/` y exportador `.scene/` -> JSON. La salida
debe roundtripear contra el payload canonico `schema_version = 2`.

### Fase 3: integracion limitada con SceneManager

Permitir que `SceneManager` cargue una `.scene/` ensamblada como `Scene`
completa. Todavia no hay streaming parcial. El authoring publico sigue usando
las rutas existentes.

### Fase 4: dirty chunks persistentes

Introducir dirty state por chunk para guardado incremental de authoring. Debe
mantenerse separado de mutaciones runtime y coordinado por el workspace.

### Fase 5: streaming publico

Disenar y exponer API aditiva en `EngineAPI` para carga y descarga parcial. La
CLI solo debe documentarse si existe implementacion real.

### Fase 6: promocion a contrato

Promover `.scene/` a contrato oficial solo cuando existan codigo, tests,
migraciones, API/CLI si aplican, y documentacion canonica actualizada.

## Riesgos

- Doble fuente de verdad entre manifest, chunks y `Scene`.
- Dirty state inconsistente entre escena, workspace y chunks.
- Migraciones parciales que pierdan jerarquia, prefabs, metadata o tilemaps.
- Atomicidad debil al guardar multiples archivos.
- Confusion documental si el diseno se presenta como feature disponible.
- Cambios prematuros que rompan `load_scene_from_file`, `save_scene_to_file` o
  scene flow.
- Mayor coste de validacion por referencias cruzadas entre chunks.
- Errores de merge cuando dos cambios actualizan manifest e indices a la vez.

## Tests necesarios

Cuando se implemente el formato, se deben cubrir al menos:

- roundtrip JSON actual -> `.scene/` -> JSON equivalente
- validacion de manifest y chunks con errores de path estables
- preservacion de entidades, componentes, jerarquia, grupos, prefabs, `rules` y
  `feature_metadata`
- tilemaps grandes particionados por chunks sin perder tiles ni metadata de
  layers
- dirty chunks: solo se escriben chunks modificados
- dirty chunks: cambios runtime tras `PLAY` no se guardan como authoring
- compatibilidad `SceneManager`: open, save, reload, close, workspace
  multi-escena y scene flow
- exportacion a JSON canonico `schema_version = 2`
- fallo explicito ante manifest que referencia chunks inexistentes
- fallo explicito ante entidades duplicadas en varios chunks propietarios

Regresiones recomendadas:

```bash
py -m unittest tests.test_repository_governance tests.test_motor_cli_contract tests.test_start_here_ai_coherence -v
py -m unittest tests.test_official_contract_regression tests.test_parser_registry_alignment tests.test_motor_interface_coherence tests.test_motor_registry_consistency -v
py -m motor --help
py -m motor doctor --project . --json
```
