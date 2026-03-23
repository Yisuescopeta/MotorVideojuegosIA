# Roadmap maestro para un motor 2D experimental IA-first en Python

## Mapa de funcionalidades fundamentales de un motor 2D moderno

La siguiente tabla resume **capacidades “esperables”** en un motor 2D moderno (o stack engine+framework), extraídas de documentación técnica de motores y librerías consolidadas. Se agrupan por categorías y se clasifican por **núcleo mínimo**, **nivel medio importante** y **avanzado recomendable**.  

> Nota de enfoque: esta sección existe para **justificar el roadmap**; el peso del documento recae en la planificación y en los prompts.

| Categoría | Núcleo mínimo imprescindible | Nivel medio importante | Avanzado pero recomendable | Evidencia en motores/frameworks (ejemplos) |
|---|---|---|---|---|
| Modelo de datos y serialización | Escenas/recursos serializables, edición basada en datos, guardado/carga estable | Versionado + migraciones, validación de esquemas, serialización diffeable | Subrecursos anidados, import/export optimizado (texto vs binario), auto-Inspector/edición de data | Unity usa serialización para Inspector/prefabs (y el prefab es un stream serializado). citeturn2search6turn2search33 Godot auto-serializa Resources y puede guardarlos como texto/binarizado. citeturn2search0turn2search2 |
| Asset pipeline y gestión de recursos | Cargar imágenes/audio, cachear, rutas/IDs estables | Preprocesado/offline, empaquetado, reporting de build, cache invalidation | Atlas/packing inteligente, compresión por plataforma, hot reload robusto | MonoGame describe pipeline de contenido y caching en ContentManager. citeturn1search0turn11search17 Unity Sprite Atlas (unifica texturas para reducir overhead/draw calls y controla carga en runtime). citeturn12search2turn12search33 Defold bundling + build report. citeturn2search1turn12search3 |
| Loop de simulación y tiempo | Timestep (idealmente fijo), pausa/step, orden de sistemas | Interpolación render vs sim, escalado de tiempo, scheduling determinista | Replays deterministas, rollback, multiworld/sandbox | Unity ejecuta física con conceptos de timestep y ofrece CCD con tradeoffs. citeturn13search12turn13search2 Box2D explica CCD/TOI en su simulación. citeturn9search6 |
| Render 2D | Sprites + batching básico, cámara 2D | Capas (sorting), tilemap renderer, render targets | Materiales/shaders, iluminación 2D, postprocesos, SRP-like render graph | Unity: Sprite Renderer. citeturn0search8 Unity: sorting en Tilemap Renderer. citeturn13search11 Defold: render predicates por tags/materiales. citeturn6search2turn6search10 MonoGame: SpriteBatch, render targets y shaders. citeturn11search0turn11search6turn11search2 LÖVE: SpriteBatch/shader/graphics API. citeturn8search0turn8search8 |
| Tilemaps y construcción de niveles | Representación grid + capas, stamping/painting | Colisiones desde tiles, optimizaciones por chunk/batch | Tile metadata (custom data), tile animado, isométrico/hex, streaming de chunks | Godot TileMaps. citeturn0search4turn0search9 Unity Tilemaps + transferencia a renderer/collider. citeturn13search4turn13search0 Defold Tilemap + shapes de colisión en tilesource. citeturn0search1 GameMaker tilesets/room workflow. citeturn0search33turn0search10 libGDX tile maps + herramientas de packing. citeturn3search0turn3search20 |
| Animación | Flipbook/sprite frames, timeline simple | Animación de propiedades/curvas, tracks, eventos en timeline | Rig 2D (huesos), blend, retarget, runtime baking | Godot AnimationPlayer anima propiedades/usa tracks. citeturn0search13turn0search29 GameMaker Sequences (assets en tracks + keyframes; editable también por código). citeturn2search12turn2search16 Unity 2D Animation (rig/animación; sprite swap frame-by-frame). citeturn13search32turn13search16 |
| Física/colisiones | Colisiones básicas + triggers | Rigidbody/character controller, fricción/rebote, queries (ray/shape casts) | CCD robusto, joints/constraints, depuración física | Godot RigidBody2D/CharacterBody2D/CollisionShape2D describen nodos y movimiento/collide. citeturn5search0turn5search16turn5search28 Defold: collision objects, grupos, mensajes, joints 2D. citeturn6search8turn6search4turn6search12 GameMaker: physics world (gravity), fixtures (densidad/fricción/restitución), joints. citeturn7search4turn7search0turn7search24 Box2D: módulos de dinámica y CCD. citeturn9search4turn9search6 |
| Input | Abstracción por acciones (actions), bindings | Rebinding, action maps/contexts, multi-dispositivo | Grabación/replay de input, “deterministic input stream” | Godot InputMap y actions configurables también por código. citeturn5search1turn5search5 Unity Input System: action assets/maps/bindings. citeturn4search18turn4search14 Defold input bindings y dispatch de acciones. citeturn0search27 libGDX input handling multiplataforma. citeturn3search17 |
| Audio | Reproducir SFX/música, audio 2D/posicional | Buses/grupos, control de ganancia, streaming | Efectos/mezcla avanzada + snapshots | Godot AudioStreamPlayer y audio buses. citeturn5search10turn5search18 Unity AudioSource/AudioMixer (routing + snapshots). citeturn4search4turn4search1 GameMaker audio groups (cargar/descargar, ganancia). citeturn7search26turn7search22 |
| Tooling y observabilidad | Debug overlays básicos, logs | Profiler integrado, métricas runtime, inspección de escena | Trazas, perfiles comparables, rendimiento reproducible/benchmarks | Godot profiler y monitores de rendimiento accesibles por código. citeturn12search0turn12search19 Unity Profiler y herramientas de profiling. citeturn12search7turn12search24 Defold profiling integrado con build y Remotery. citeturn12search1 |
| Build, CLI y headless | CLI para ejecutar y/o exportar | Headless real (sin GPU), export/bundle automatizable | CI “de serie”, matrix builds, reproducibilidad | Godot: export por CLI y `--headless` para entornos sin GPU/CI. citeturn5search23turn5search3 Unity: desktop headless mode con `-batchmode` y `-nographics`. citeturn10search5 Defold: bundling por CLI (Bob) y bundling desde editor. citeturn2search27turn2search1 |
| IA-first | API programática para simular/reset/step y modo headless | Especificación formal de “observaciones/acciones”, seeds, determinismo | Multiagente, dataset generation, ejecución paralela/vectorizada | Gymnasium define interfaz `reset()`/`step()` y semántica terminated/truncated. citeturn10search0turn10search6 PettingZoo define API multiagente (Parallel/AEC). citeturn10search1turn10search4 Unity ML-Agents entrena desde un paquete Python y expone una API Python LL. citeturn10search11turn10search23 |

## Roadmap óptimo y ordenado de implementación

Este roadmap está diseñado para maximizar: **solidez de datos**, **determinismo**, **extensibilidad**, **rendimiento incremental** y **compatibilidad IA-first**, evitando que el editor/UI se convierta en fuente de verdad (tu restricción clave). La idea es operar como hacen stacks consolidados: la edición es una proyección del modelo serializable (Unity serializa para Inspector/prefabs; Godot auto-serializa Resources y su Inspector edita data). citeturn2search6turn2search0

### Resumen de fases y dependencias

| Fase | Tipo (distinción explícita) | Objetivo principal | Depende de | Entregables principales |
|---|---|---|---|---|
| A | Endurecimiento de sistemas existentes | Contrato de arquitectura + pruebas + determinismo base | — | “Architecture RFC”, harness de tests de sim, trazas/logs, baseline de reproducibilidad |
| B | Core data + serialización | “Modelo primero”: schema versionado, migraciones, diffs/overrides | A | Scene/Prefab schema vNext, validación, migrator, patch/diff |
| C | Tooling/infra + nuevas capacidades core | Asset DB + pipeline + bundling reproducible | B | IDs de assets, importers, atlas pipeline, packaging, build report |
| D | Nuevas capacidades core (runtime) | Render pipeline v2: capas, batching, materiales, render targets | C | Render graph/passes, sorting, debug view, (opcional) infraestructura lighting |
| E | Nuevas capacidades core (runtime) + endurecimiento | Física v2: backend modular + Box2D opcional + queries/eventos | B (y se beneficia de D) | Physics API estable, CCD/queries, eventos, joints/character controller |
| F | Nuevas capacidades core + authoring | Tilemaps/level authoring data-first con integración render/física | B+C+D+E | Tilemap schema, renderer, colisiones por tiles, edición no-UI-first |
| G | Tooling/editor + observabilidad | Debug/profiling/inspección robusta + replay verificable | A–F | Profiler interno, overlays, métricas, replay determinista, CLI suites |
| H | Authoring orientado a IA | “IA-first suite”: Gymnasium/PettingZoo adapters + data generation | A–G | Wrapper RL, multiagente, escenarios, dataset logging, runner paralelo headless |

A continuación se detallan las fases con lo requerido: objetivo, por qué el orden, prerequisitos, funcionalidades, criterios de aceptación, riesgos e impacto por área.

### Fase A — Base verificable y determinismo mínimo

**Objetivo.** Convertir el proyecto en un sistema donde **cada cambio futuro se valida** (tests + checks), y donde la simulación en modo headless sea **repetible** bajo condiciones controladas. Esta fase existe para reducir el riesgo técnico acumulativo antes de tocar features de alto acoplamiento como física avanzada, tilemaps grandes o render graph. (En motores bien instrumentados, profiling/debug están integrados con el flujo de ejecución y no se activan “por accidente”.) citeturn12search0turn12search7

**Por qué va primero (dependencias y riesgo).**  
La física 2D moderna y determinismo se vuelven rápidamente difíciles de depurar sin herramientas: Box2D tiene CCD/TOI y asunciones de stepping; Unity advierte sobre determinismo “mismo binario/misma máquina” y variaciones entre plataformas. citeturn9search6turn9search3 La base de pruebas debe existir ya.

**Prerequisitos.** Ninguno (se apoya en lo que ya existe).

**Funcionalidades incluidas.**
- Contrato formal de módulo runtime/editor: “quién es fuente de verdad” como regla testable (p. ej. validación de escena/prefab al guardar y al cargar).
- Harness de pruebas de simulación (headless) con “golden runs” (replays) y medición de drift.
- Semilla/PRNG controlado para cualquier sistema estocástico (si existe).
- Logging estructurado + trazas mínimas para ordenar eventos (sin depender de UI).

**Criterios de aceptación.**
- Un conjunto de “escenas/escenarios canónicos” se ejecuta en headless y produce resultados estables (hash de estado / métricas) dentro de tolerancias definidas por ti. (Inferencia: tolerancia 0 si se aspira a determinismo estricto; tolerancia >0 si hay floats no controlados.)
- Al menos un “modo CI local” (script) corre: lint+tests+smoke-run headless.
- La UI puede fallar sin corromper el modelo: un “save/load roundtrip” conserva el grafo de escena.

**Riesgos.**
- Falsos positivos de tests si el estado serializado incluye campos no deterministas (timestamps, IDs aleatorios).
- Determinismo parcial si hay floats sin control o dependencia de orden de iteración (común en simulaciones). citeturn9search3turn9search6

**Impacto.**
- Runtime: instrumentación ligera y puntos de “snapshot/hash”.
- Editor: validación al editar/guardar pero sin ser fuente de verdad.
- API IA: contratos de `reset/step` internos listos para wrappers. citeturn10search0
- Serialización: base para versionado y migraciones.
- Tooling: scripts y tests como “columna vertebral”.

### Fase B — Modelo serializable vNext: schemas, versionado y overrides

**Objetivo.** Formalizar el “lenguaje” del motor: **qué es una escena/prefab/asset** y cómo evoluciona sin romper compatibilidad. Esto es la aplicación directa de tu restricción: la UI traduce, el modelo manda. (Unity y Godot sustentan gran parte de su workflow en serialización coherente: Unity para Inspector/prefabs; Godot con auto-serialización de Resources + escenas en texto TSCN.) citeturn2search6turn2search2turn2search0

**Por qué va aquí.**  
Si no existe un esquema versionado de referencia, features como tilemaps, físicas complejas o pipelines de assets acaban filtrando “estado editor” en archivos y rompiendo la compatibilidad hacia atrás. En Unity, por ejemplo, el concepto de prefab existe en tiempo de editor y termina “bakeado” al build como un stream normal, lo que refleja la importancia de separar authoring vs runtime representation. citeturn2search13turn2search33

**Prerequisitos.** Fase A completada (tests y contrato de validación).

**Funcionalidades incluidas.**
- Schema explícito para: escena, entidad, componentes, recursos, referencias a assets, prefab + overrides.
- Versionado semántico del schema y migraciones automáticas.
- Mecanismo de “diff/patch” para overrides (prefab instance → lista de modificaciones, análogo conceptual a lo que Unity describe para instancias de prefabs). citeturn2search33
- Validación offline (CLI) de todos los JSON/escenas.

**Criterios de aceptación.**
- Cualquier archivo de escena/prefab declara `schema_version`.
- Existe un migrador que convierte N-1 → N y se testea con fixtures.
- Overrides funcionan en roundtrip sin perder datos.

**Riesgos.**
- Diseñar el patch format demasiado acoplado al layout actual (coste de migración futuro).
- Romper performance si el sistema de diffs se evalúa “cada frame” en runtime (debe aplicarse al cargar/bakear). (Inferencia basada en prácticas comunes en motores con pipelines de import/bake.)

**Impacto.**
- Runtime: carga más robusta, posibilidad de “bake” de instancias.
- Editor: inspector/hierarchy debe consumir el schema (no escribir estructuras ad-hoc).
- API IA: puede construir escenas/prefabs por datos con validación.
- Tooling: CLI `validate/migrate`.

### Fase C — Asset DB + pipeline de importación/atlas + bundling reproducible

**Objetivo.** Convertir assets en **recursos gestionados**: IDs estables, importers, cache, atlases, reporting y bundling. Esto se inspira en pipelines establecidos: MonoGame precompila assets vía MGCB, luego los carga con ContentManager (con caching); Unity consolida texturas en Sprite Atlas y controla carga overhead; Defold integra bundling y build report y ofrece herramienta CLI (Bob). citeturn1search0turn11search17turn12search2turn2search1turn2search27

**Por qué va antes del render pipeline v2/tilemaps.**  
Tilemaps y render batching dependen críticamente de atlas/packing (menos draw calls y menos cambios de textura), y de import estable (sprites/tile sources). Unity expresa que el atlas reduce overhead porque permite una sola llamada/texture en vez de múltiples; libGDX ofrece herramientas offline para optimizar tilemaps en un atlas. citeturn12search2turn3search20

**Prerequisitos.** Modelo vNext (Fase B) para referenciar assets por ID, no por rutas frágiles.

**Funcionalidades incluidas.**
- Asset DB: IDs (content-addressed o GUID) + metadatos (tipo, dependencia, hash, import settings).
- Importers: imagen (sprites), audio; y (si procede) tilemap sources.
- Atlas pipeline:
  - Packing de sprites/tile atlases (inspiración: Unity Sprite Atlas; libGDX TiledMapPacker). citeturn12search33turn3search20
  - Reglas por “grupo de uso” (escena) para evitar cargar atlases gigantes si no toca (Unity advierte sobre overhead si cargas un atlas con texturas grandes no usadas). citeturn12search17
- Bundling reproducible y build report (análogo a Defold bundling/build reports). citeturn2search1turn12search3
- CLI de build: `build-assets`, `bundle`, `validate-assets`.

**Criterios de aceptación.**
- Un asset se referencia por ID en escenas/prefabs (no por path absoluto).
- Cambiar un asset invalida cache y reimporta determinísticamente.
- “Bundle” genera un artefacto reproducible (misma entrada → mismo output) dentro de lo razonable (Inferencia: si timestamps se neutralizan).

**Riesgos.**
- Coste de implementación de atlas/packing.
- Duplicación de assets si no se define bien dependencia y sharing (Godot y MonoGame destacan load-once/caching como patrón útil). citeturn2search7turn11search17

**Impacto.**
- Runtime: carga más rápida, menos draw calls (base).
- Editor: browser + drag&drop pasan a hablar con Asset DB.
- API IA: puede “materializar” escenas referenciando assets por ID.
- Serialización: referencias estables + settings de import versionables.

### Fase D — Render pipeline v2: capas, batching, materiales, render targets y (opcional) iluminación 2D

**Objetivo.** Evolucionar render a una arquitectura escalable: ordenación por capas, batching agresivo, “pases” de render (world, overlay, UI, debug), materiales/shaders y soporte de render targets (para postprocesos o compositing). Motores y frameworks lo reflejan de distintas maneras: Defold usa tags/materiales y render predicates para decidir qué dibujar y cómo; MonoGame ofrece SpriteBatch + render targets y pipeline de shaders; Unity URP 2D habilita 2D lighting con componentes y renderer data. citeturn6search2turn11search6turn11search2turn4search2

**Por qué va aquí.**  
Sin un render v2, tilemaps grandes y debug overlays (colisiones, navegación, selección) se vuelven caros y difíciles de mantener. Además, Unity y MonoGame muestran que batching/orden es parte central del pipeline (SpriteBatch begin/draw/end; Tilemap renderer sorting). citeturn11search0turn13search11

**Prerequisitos.** Asset pipeline (Fase C) para atlases y materiales; y schema (Fase B) para declarar render components.

**Funcionalidades incluidas.**
- Sistema de “Render Layers” + orden (similar en espíritu a Sorting Layer / order-in-layer en tilemaps). citeturn13search11
- Batching:
  - batch por atlas/material/shader (similar a SpriteBatch y SpriteBatch begin/end discipline; LÖVE SpriteBatch). citeturn11search0turn8search8
  - batch para tilemaps por chunks (Unity tilemap renderer chunking/batching). citeturn13search30
- Material/shader abstraction:
  - “material tags/predicates” (análogamente a Defold). citeturn6search10turn6search2
  - Shaders/passes (análogamente a MonoGame shaders). citeturn11search2
- Render targets:
  - offscreen rendering para minimap, post FX, selección (MonoGame describe patrón set render target, dibujar, volver a back buffer). citeturn11search6turn11search28
- (Opcional, avanzada) Infraestructura de iluminación 2D:
  - si se aborda más tarde: inspiración en URP 2D lighting y Tilemap Renderer con 2D lighting. citeturn4search2turn13search1

**Criterios de aceptación.**
- Escenas similares renderizan igual en editor y runtime con mismos datos (sin “UI states” ocultos).
- Debug overlays (colisiones, bounds, seleccionados) se dibujan como un pass independiente (no mezclado con lógica UI).
- Batching verificable: métricas de draw calls / batches expuestas (inspiración: Godot ofrece monitores de draw calls y rendimiento por API). citeturn12search19

**Riesgos.**
- Si se usa Python + backend GPU, el coste de calls puede ser dominante (inferido por naturaleza de bindings). Batching es crítico.
- Orden de render y transparencia compleja (tilemaps isométricos, etc.) requiere reglas claras (Unity trata transparencia y sort modes en Tilemap Renderer/URP 2D). citeturn13search1turn13search11

**Impacto.**
- Runtime: render graph/passes y estadísticas.
- Editor: viewport usa el mismo render pipeline que runtime.
- API IA: puede renderizar (o no) según modo headless/perf.
- Tooling: frame capture / metrics base.

### Fase E — Física v2: backend modular (Box2D opcional), queries, contactos y joints

**Objetivo.** Consolidar colisiones/física en una API estable y extensible: desde AABB básico a un backend más completo (p. ej. Box2D). Aquí interesa especialmente **determinismo**, queries (ray/shape casts), eventos de contacto, materiales físicos (fricción/rebote) y joints/constraints.

Los motores investigados muestran “paquetes de expectativas”:
- Godot separa `RigidBody2D` (fuerzas, simulación) de `CharacterBody2D` (movimiento controlado por código con `move_and_collide/move_and_slide`). citeturn5search0turn5search16turn5search4
- Defold define collision objects, grupos/filtrado, mensajes de colisión y joints para física 2D. citeturn6search8turn6search4turn6search12
- GameMaker opera con physics world (gravity), fixtures (densidad/fricción/restitución) y joints. citeturn7search4turn7search0turn7search24
- Box2D documenta módulos (fixtures, bodies, world, joints, listeners) y su simulación usa CCD para evitar tunneling. citeturn9search4turn9search6
- Unity integra Box2D para 2D physics y discute determinismo/limitaciones cross-machine. citeturn9search14turn9search3

**Por qué va antes de tilemaps avanzados.**  
Tilemaps “serios” casi siempre requieren colisiones de tiles (Unity Tilemap Collider; Defold tilemaps con collision shapes; Godot tilemap + físicas). citeturn13search0turn0search1turn0search4

**Prerequisitos.**  
- Schema versionado (Fase B) para declarar colliders/bodies.
- Base de determinismo/test (Fase A).  
- Render v2 ayuda para debug de físicas (Fase D) pero no es estrictamente obligatorio.

**Funcionalidades incluidas.**
- API unificada de física:
  - `PhysicsWorld.step(dt)` (timestep fijo) + queries.
  - Contact events con filtros/layers.
- Material físico (fricción/restitución) siguiendo conceptos de fixtures (GameMaker) y colliders. citeturn7search0turn7search10
- CCD y “fast movers”:
  - Box2D explica CCD/TOI; Unity expone CCD como safety net con coste de performance. citeturn9search6turn13search12
- Joints/constraints (subset inicial):
  - Defold soporta joints 2D y expone API de creación/destrucción. citeturn6search12turn6search0
- Character controller (controlado por código) diferenciado de rigidbody (inspiración: Godot `CharacterBody2D`). citeturn5search16turn5search4
- (Opcional) Backend Box2D:
  - Box2D 3.0 es rewrite con cambios importantes en API (handles, multithreading, etc.) — útil para evaluar integración futura. citeturn9search1turn9search5

**Criterios de aceptación.**
- Tests deterministas de stepping (mismo input stream → mismo estado/hashes en una máquina) y especificación clara de lo garantizado (Unity: determinismo general en misma máquina, no necesariamente cross-machine). citeturn9search3
- Eventos de contacto reproducibles + debug draw.
- Soporte mínimo de joints probado con escenas canónicas.

**Riesgos.**
- Integración Box2D: la transición v2→v3 implica diferencias relevantes (C vs C++, handles, menos callbacks). citeturn9search1turn9search5
- Rendimiento: CCD cuesta; Unity advierte de overhead. citeturn13search31turn13search12
- Debugging: sin overlay/inspector físico, el coste de iterar se dispara.

**Impacto.**
- Runtime: nuevo subsistema de física y eventos.
- Editor: gizmos de colliders/joints y propiedades (pero siempre derivadas del modelo).
- API IA: step/reset consistente, control de seeds, y capacidad de queries para agentes.

### Fase F — Tilemaps y authoring de niveles data-first (render + colisiones + metadatos)

**Objetivo.** Construir un sistema de tilemaps que no sea sólo “una herramienta del editor”, sino un **modelo serializable** consumible por runtime, CLI y agentes IA. La evidencia muestra patrones maduros:
- Unity Tilemap system define el mapa y transfiere datos a Tilemap Renderer y Tilemap Collider 2D. citeturn13search4turn13search0  
- Defold tilemaps se construyen desde Tile Source; además se pueden usar collision shapes del tilesource para colisiones/física. citeturn0search1turn0search11  
- Godot tilemaps están optimizados para pintar layouts grandes y evitar instanciar miles de sprites uno a uno. citeturn0search4

**Por qué va después de C/D/E.**  
Un tilemap “de motor” requiere:
- assets/atlases (C),
- un render pipeline que soporte chunk/batching y sorting (D),
- y colisiones por tile (E).  
Unity incluso detalla colisionadores en tilemaps y optimización con composite colliders (conceptualmente: merge de colliders adyacentes). citeturn13search10turn13search7

**Prerequisitos.** Fase B+C+D+E.

**Funcionalidades incluidas.**
- Modelo de tilemap:
  - grid config (iso/hex opcional), layers, tileset/tilesource refs, metadata por tile.
- Renderer de tilemap:
  - chunking, batching por atlas/material (alineado con D).
- Colisión por tile:
  - generación incremental; opción de “merge”/composición de shapes adyacentes (inspiración en composición/optimización en Unity tilemap colliders). citeturn13search10turn13search0
- Tiles animados / secuencias:
  - Unity tiene AnimatedTile; GameMaker tiene tiles animados y sequences; Defold sprite flipbook. citeturn0search14turn2search12turn0search5
- Integración con eventos/reglas:
  - triggers desde tile metadata (p. ej. “zona agua” → audio/physics), inspirable por ejemplos de audio bus redirection por áreas en Godot (concepto de áreas afectando buses). citeturn5search2turn5search18 (Inferencia: tu motor no tiene “Area2D”, pero el patrón de “zonas” data-driven es transferible.)

**Criterios de aceptación.**
- Tilemap editable en editor **y** modificable por API/CLI y serializable.
- Render de mapas grandes sin degradación catastrófica (métricas de batches/draw calls disponibles). citeturn12search19
- Colisiones consistentes con backend físico.

**Riesgos.**
- Complejidad de edge cases: iso/hex, sorting/transparencias, colisiones “finas”.
- Coste de migrar datos si el tileset/tile metadata no se versiona desde el inicio.

**Impacto.**
- Runtime: nuevo componente Tilemap + sistemas.
- Editor: herramientas de pintura (como UI) pero el modelo vive fuera.
- API IA: generación procedural de niveles y modificación de tiles en runtime.

### Fase G — Debugging, profiling, replay y observabilidad “de motor”

**Objetivo.** Crear un conjunto de herramientas internas para validar rendimiento, simulación y reproducción; y hacerlo sin acoplarse a UI. Motores maduros exponen profiling de diferentes formas:
- Godot: profiler en debugger y monitores accesibles por código (memoria, draw calls, FPS). citeturn12search0turn12search19
- Unity: Profiler y módulos/herramientas de profiling. citeturn12search7turn12search24
- Defold: profiling integrado con engine/build pipeline. citeturn12search1

**Por qué no va antes.**  
Es mejor instrumentar cuando ya existen los sistemas principales (render v2, física v2, tilemaps) para perfilar “lo real”. Aun así, una base mínima ya existe desde Fase A.

**Prerequisitos.** A–F.

**Funcionalidades incluidas.**
- Profiler interno (CPU time por sistema, draw calls/batches, step time).
- Debug overlays:
  - colliders, joints, contactos, tile chunks, bounding boxes.
- Trazas/replay:
  - input stream + decisiones/rng seeds + snapshots (expandir tu timeline).
- CLI de benchmark/perf:
  - “run scene N frames headless → reporte”.

**Criterios de aceptación.**
- Un reporte reproducible por escena: min/avg/max frame time, memoria, batches.
- Replays “pasan” en CI local (mismo output hash/metrics).

**Riesgos.**
- Instrumentación invasiva que degrade performance.
- APIs de debug que se conviertan en dependencia de gameplay (deben ser opcionales).

**Impacto.**
- Runtime: instrumentation hooks.
- Editor: paneles pueden consumir métricas pero no generarlas.
- API IA: acceso a trazas/datasets.

### Fase H — Suite IA-first: wrappers RL, multiagente, generación de datos y ejecución paralela

**Objetivo.** Convertir el motor en un “simulador” consumible por tooling de IA estándar, sin sacrificar la filosofía serializable. Aquí conviene apoyarse en APIs existentes:
- Gymnasium define contrato `reset()`/`step()` y semántica terminated/truncated. citeturn10search0turn10search6
- PettingZoo define API multiagente (Parallel/AEC). citeturn10search1turn10search4
- Unity ML-Agents entrena usando un paquete Python y expone API low-level para interactuar con entornos. citeturn10search11turn10search23

**Por qué va al final.**  
Necesitas determinismo (A), schema estable (B), ejecución y recursos robustos (C–F) y observabilidad (G) para que el entrenamiento y generación de datasets sea medible y fiable.

**Prerequisitos.** A–G.

**Funcionalidades incluidas.**
- Wrapper Gymnasium:
  - `Env.reset(seed=...) -> (obs, info)`; `step(action) -> (obs, reward, terminated, truncated, info)`. citeturn10search0turn10search13
- Wrapper PettingZoo:
  - ParallelEnv para acciones simultáneas o AEC para turn-based. citeturn10search1turn10search4
- Definición formal de espacios de acción/observación (schema de spec):
  - (Inferencia) usar shapes/espacios compatibles con Gymnasium.
- Scenario runner + vectorización:
  - multi-instancia headless (subprocess) para generar experiencia/datasets.
  - inspiración conceptual: Unity permite headless (batchmode/nographics) para ejecutar sin GPU; Godot permite `--headless` y export/CLI para CI. citeturn10search5turn5search3turn5search23
- Dataset logging:
  - episodios, seeds, acciones, métricas, snapshots.

**Criterios de aceptación.**
- Se puede entrenar un agente “toy” (random policy) y generar rollouts sin UI.
- Multiagente funciona con un ejemplo mínimo (2 agentes) con API PettingZoo.
- Los rollouts incluyen metadatos reproducibles.

**Riesgos.**
- Desalineación entre modelo del motor y el wrapper RL (observaciones no estables o demasiado costosas).
- Overhead de IPC si la vectorización se hace mal (inferido por patrones comunes en runners RL).

**Impacto.**
- Runtime: soporte “sim-only”.
- Tooling: nuevos comandos CLI “rollout/generate-dataset”.
- Serialización: specs de obs/action versionados.

## Prompts de implementación ordenados por fases

Los siguientes prompts están diseñados para ejecutarse **en orden**, con una IA de programación, y cumplen tus restricciones: primero análisis del código, no reimplementar lo existente, respetar IA-first + serializable, y evitar UI como fuente de verdad. Cada prompt incluye objetivo, alcance, restricciones y validación.

> Formato recomendado: copia/pega el prompt tal cual. Si el agente necesita nombres de carpetas, debe inferirlos inspeccionando el repo.

### Fase A — Prompts

**A.1 — “Inventario técnico + contrato de arquitectura verificable”**
```text
Actúa como arquitecto de software. Antes de cambiar nada:
1) Explora el repositorio y produce un inventario preciso: módulos principales, carpetas, runtime vs editor, serialización de escenas/prefabs, ECS, timeline/snapshots, CLI/headless y API programática para IA.
2) Identifica explícitamente dónde vive la “fuente de verdad” de los datos hoy (archivos JSON, objetos en memoria, etc.). No asumas: cita rutas/archivos concretos.

Objetivo:
- Crear un documento ARCHITECTURE.md (o /docs/architecture.md) que fije el contrato: “la UI traduce el modelo; el modelo serializable es la fuente de verdad”, definiendo invariantes testables.

Restricciones:
- PROHIBIDO reimplementar sistemas ya existentes (ECS, escenas JSON, timeline, etc.) sin justificar con evidencia del repo.
- No añadir dependencias pesadas.
- No introducir estado persistente que exista solo en UI.

Entrega:
- Documento de arquitectura con:
  - invariantes (ej. load->edit->save->load roundtrip)
  - responsabilidades (runtime/editor/API/serialización/tooling)
  - lista de “puntos de integración” para futuras fases.
- Una propuesta de “test matrix” (qué se testea, cómo, dónde).

Validación:
- El documento debe permitir a otro dev entender cómo añadir features sin violar el contrato de datos.
```

**A.2 — “Harness de pruebas headless + golden runs de simulación”**
```text
Antes de cambiar nada:
1) Localiza cómo se ejecuta el motor en modo CLI/headless y cómo se carga/ejecuta una escena.
2) Localiza el loop de simulación (EDIT/PLAY/PAUSED/STEPPING) y cómo se avanza el tiempo.

Objetivo:
- Añadir un “harness” de pruebas que ejecute escenas en headless durante N frames y produzca:
  a) métricas (fps/tiempo por frame/contadores),
  b) un hash del estado serializable (o un resumen determinista),
  c) logs estructurados por frame (mínimo: frame index, dt, eventos críticos).

Alcance:
- No cambiar gameplay; solo instrumentación y test harness.
- Añadir al menos 2 escenas/escenarios canónicos de test (pueden ser JSON ya existentes o copias mínimas).

Restricciones:
- PROHIBIDO depender de UI o de input humano.
- Si ya existe timeline/snapshots, reutilízalo; no lo reescribas.
- Si existe un sistema de serialización, úsalo para el estado/hashes.

Validación:
- Un comando (script) o test automatizado que:
  1) corre la escena canónica 200 frames,
  2) genera un reporte,
  3) falla si el resultado cambia sin actualizar el “golden”.
- Incluye documentación de cómo regenerar golden de forma explícita.
```

**A.3 — “Determinismo mínimo: seed, orden y ‘state hash’”**
```text
Antes de cambiar nada:
1) Busca cualquier uso de aleatoriedad (random, time, uuid, etc.) y cualquier ID generado en runtime.
2) Identifica si el orden de iteración de entidades/componentes puede variar (p. ej. uso de dict no ordenado, sets, etc.).

Objetivo:
- Introducir un “Determinism Layer” mínimo que:
  - permita fijar una seed global para runs headless,
  - evite que IDs no deterministas contaminen el estado serializable,
  - provea una función estándar: compute_state_fingerprint(world) -> str,
    que sea estable en la misma máquina/versión.

Restricciones:
- No prometas determinismo cross-platform si el motor usa floats no controlados; documenta el alcance real.
- PROHIBIDO modificar UI para “arreglar determinismo”; debe ser runtime+data.

Validación:
- Extiende el harness (A.2) para ejecutar 2 runs con misma seed y verificar fingerprint idéntico.
- Añade 1 run con seed distinta y demuestra fingerprint distinto (si aplica).
```

### Fase B — Prompts

**B.1 — “Especificación de schema vNext (escenas/prefabs/assets)”**
```text
Antes de cambiar nada:
1) Abre ejemplos reales de escenas JSON y prefabs actuales.
2) Documenta campos, relaciones (jerarquía), referencias a assets y behaviours serializables.

Objetivo:
- Diseñar (NO implementar todavía en profundidad) un schema vNext:
  - Scene, Entity, Component, ResourceRef/AssetRef, Prefab, PrefabInstance + Overrides.
- Añadir un documento /docs/schema_vNext.md que defina:
  - campos obligatorios,
  - versionado (schema_version),
  - reglas de compatibilidad,
  - restricciones (no UI-state),
  - ejemplos JSON concisos.

Restricciones:
- No inventar un “estándar” nuevo si ya existe uno útil: usa JSON convencional y define reglas claras del proyecto.
- Debe ser compatible con la filosofía: runtime/editor/API consumen el MISMO modelo.

Validación:
- Incluye al menos 3 ejemplos: escena simple, prefab con overrides, escena con referencias a assets por ID.
```

**B.2 — “Validación offline y migraciones (N-1 → N)”**
```text
Antes de cambiar nada:
1) Identifica dónde se parsean/cargan escenas/prefabs.
2) Identifica cómo se reportan errores (exceptions/logs).

Objetivo:
- Implementar un validador de escenas/prefabs:
  - Ejecutable por CLI: `validate_scene <path>` y `validate_all`.
  - Debe fallar con errores accionables (ruta del campo, expected vs actual).
- Implementar un sistema de migraciones:
  - Cada cambio de schema_version debe tener un migrator `migrate_vX_to_vY(data)` determinista y testeado.

Restricciones:
- PROHIBIDO introducir migraciones que dependan de la UI.
- No romper compatibilidad: si un archivo viejo se abre, debe migrarse y/o avisar claramente.

Validación:
- Tests unitarios: (a) un JSON vOld migra a vNew y pasa validación, (b) un JSON inválido produce error con path.
```

**B.3 — “Prefab overrides como diff/patch (aplicación al cargar)”**
```text
Antes de cambiar nada:
1) Identifica cómo funcionan hoy los prefabs y cómo se instancian en escena/runtime.
2) Comprueba si ya existe algún concepto de “override” o “modificaciones”.

Objetivo:
- Definir e implementar un formato de overrides tipo patch:
  - add/remove component
  - set field value (incluyendo nested)
  - reorder children (si existe jerarquía)
- Aplicar overrides al cargar/bakear la escena (no cada frame).

Restricciones:
- PROHIBIDO duplicar toda la data del prefab en cada instancia.
- PROHIBIDO hacer que el editor guarde “copias completas” por comodidad.
- Debe ser serializable y aplicable por API IA sin editor.

Validación:
- Caso de test: prefab base + 2 instancias con overrides distintos → runtime produce entidades distintas.
- Roundtrip: save/load conserva override semantics.
```

**B.4 — “Contrato ‘UI traduce modelo’: API de edición transaccional”**
```text
Antes de cambiar nada:
1) Localiza cómo el editor modifica el modelo: inspector, drag&drop, jerarquía, etc.
2) Identifica si existe ya un sistema de comandos/undo/redo o timeline.

Objetivo:
- Implementar una API de edición transaccional (editor agnóstica):
  - begin_transaction()
  - apply_change(change)
  - commit() / rollback()
- Diseñar `Change` como dato serializable (para undo/redo, timeline y para IA).
- La UI solo emite `Change`; el modelo aplica.

Restricciones:
- PROHIBIDO que la UI mutile directamente el estado runtime sin pasar por Change.
- Debe funcionar tanto en editor como por API IA.

Validación:
- Demo mínima: cambiar un valor desde UI y desde API IA genera el mismo Change serializado.
- Undo/redo funciona sin UI (por CLI/test).
```

### Fase C — Prompts

**C.1 — “Asset DB con IDs estables y dependencias”**
```text
Antes de cambiar nada:
1) Analiza cómo se referencian assets hoy (paths, handles, etc.).
2) Identifica hot-reload actual y cómo invalida/carga recursos.

Objetivo:
- Crear un Asset Database:
  - asigna IDs estables a cada asset (GUID o content-hash; decide y justifica).
  - guarda metadatos: tipo, hash, dependencias, import_settings (versionados).
  - expone API: resolve(id) -> runtime asset, get_meta(id).

Restricciones:
- PROHIBIDO depender de rutas absolutas.
- Debe funcionar en headless/CLI.
- No romper el sistema actual: crea una capa de compatibilidad si es necesario.

Validación:
- Test: mover/renombrar un fichero de asset no rompe la referencia si el ID es estable (si el diseño lo permite).
- Reporte: listar assets y dependencias.
```

**C.2 — “Importers + cache determinista + invalidación”**
```text
Antes de cambiar nada:
1) Identifica formatos soportados hoy (imágenes, audio).
2) Revisa si hay caching o conversión previa.

Objetivo:
- Implementar importers (mínimo: sprites e audio) con cache determinista:
  - input file + import_settings -> artifact (cache key)
  - invalidación por hash
- Definir artifacts como datos (p. ej. atlas pages, decoded audio, etc.) listos para runtime.

Restricciones:
- PROHIBIDO hacer que el runtime haga trabajo pesado que puede hacerse offline.
- Mantén el pipeline extensible (añadir tile sources/tilemaps después).

Validación:
- Test: cambiar un import_setting re-genera artifact; no cambiar input no reimporta.
- CLI: `build-assets` genera artifacts sin editor.
```

**C.3 — “Atlas pipeline y bundling reproducible con build report”**
```text
Antes de cambiar nada:
1) Busca si ya existe atlas/packing o batching por textura.
2) Identifica cómo se empaqueta/distribuye hoy (si existe algo).

Objetivo:
- Añadir un pipeline de atlas:
  - agrupa sprites por “grupo de uso” y genera atlas pages.
  - produce metadatos de UVs y rects por sprite.
- Implementar bundling:
  - empaqueta artifacts + scenes/prefabs en un formato de bundle del motor.
  - genera un build report (tamaño por asset + totales).

Restricciones:
- PROHIBIDO que el editor sea el único modo de generar un build.
- El build report debe ser reproducible en headless.

Validación:
- Comparar un escenario antes/después: número de binds/draw-batches disminuye o se monitoriza.
- Build report existe y lista top-N assets por tamaño.
```

### Fase D — Prompts

**D.1 — “Render layers + render passes (render graph mínimo)”**
```text
Antes de cambiar nada:
1) Inspecciona el renderer 2D actual: cómo dibuja sprites, cómo ordena, cómo maneja cámara.
2) Identifica si existe ya noción de layers/sorting.

Objetivo:
- Diseñar e implementar un RenderGraph mínimo:
  - define passes: World, Overlay, Debug.
  - define RenderLayer/SortKey en el modelo serializable.
- El runtime ejecuta el RenderGraph; el editor viewport lo reutiliza.

Restricciones:
- PROHIBIDO introducir ordenación dentro de UI; debe ser modelo.
- Mantén compatibilidad con lo existente (puede haber defaults).

Validación:
- Escena con 3 layers y solapes: orden correcto y reproducible.
- Métricas: batches/draw calls expuestas al profiler/monitor.
```

**D.2 — “Batching por material/atlas y disciplina tipo SpriteBatch”**
```text
Antes de cambiar nada:
1) Identifica dónde se producen “draw calls” o equivalentes.
2) Identifica cambios de textura/material.

Objetivo:
- Introducir un sistema de batching:
  - agrupa por (atlas_id, material_id, shader_id, blend_mode, layer).
  - minimiza cambios de estado.
- Si existe ya batching, endurecerlo: añade métricas y tests de regresión.

Restricciones:
- PROHIBIDO hacer “sort cada frame” si no es imprescindible; documenta la estrategia.
- No introducir dependencias UI.

Validación:
- Benchmark headless de una escena con 5k sprites: reporta batches/draws.
- Golden de métricas (dentro de tolerancias) para evitar regresiones.
```

**D.3 — “Render targets y composición”**
```text
Antes de cambiar nada:
1) Verifica si hay soporte de render-to-texture o framebuffer en el backend actual.
2) Identifica cómo se renderiza el viewport del editor.

Objetivo:
- Implementar RenderTarget API:
  - crear, set, clear, draw-to-target, luego componer al back buffer.
- Añadir al menos 2 usos:
  1) minimap (o preview) simple
  2) selección/highlight (mask / outline) o debug overlay compositado

Restricciones:
- PROHIBIDO acoplarlo a UI: la UI solo muestra el resultado.
- Debe funcionar en runtime y, si hay backend, en editor viewport.

Validación:
- Tests de “no-crash” + ejemplo reproducible.
- Métricas: coste del pass adicional reportado.
```

**D.4 — “Infraestructura de materiales/shaders (sin construir un editor de shaders aún)”**
```text
Antes de cambiar nada:
1) Analiza cómo se definen hoy materiales/efectos (si existen).
2) Identifica si hay un concepto análogo a tags/predicates.

Objetivo:
- Crear un modelo serializable Material:
  - referencias a shader/programa, parámetros, blend mode, tags.
- Runtime: aplicar materiales en batching sin romper compatibilidad.

Restricciones:
- PROHIBIDO hacer que el material exista solo como “config UI”.
- No intentes un editor visual de shaders en esta fase.

Validación:
- 2 materiales distintos en una escena (p. ej. normal vs additive) se renderizan correctamente.
- Serialización: material se guarda/carga sin perder parámetros.
```

### Fase E — Prompts

**E.1 — “API de física estable y backend pluggable”**
```text
Antes de cambiar nada:
1) Inspecciona el sistema actual de colisiones AABB + rigidbody simple.
2) Identifica cómo se reportan colisiones (eventos, reglas declarativas).

Objetivo:
- Definir una interfaz PhysicsBackend:
  - create_body, destroy_body
  - create_shape/collider
  - step(dt)
  - query_ray / query_aabb / (opcional) query_shape
  - contact events
- Implementar un backend “LegacyAABB” que adapte lo existente a la interfaz (sin reescribirlo).

Restricciones:
- PROHIBIDO romper el gameplay existente.
- Los cuerpos/colisionadores deben ser parte del modelo serializable (componentes).

Validación:
- El runtime puede alternar backend (config) y los tests base siguen pasando.
- Contact events alimentan el sistema de reglas existente.
```

**E.2 — “Integración Box2D opcional (scope mínimo)”**
```text
Antes de cambiar nada:
1) Evalúa dependencias viables en Python (bindings) y cómo se distribuirían en bundling.
2) Revisa la interfaz PhysicsBackend definida en E.1 y ajusta sólo si es imprescindible.

Objetivo:
- Añadir un backend Box2D con alcance mínimo:
  - dynamic/static bodies
  - shapes básicas (box/circle/polygon simple)
  - fricción/restitución y gravedad
  - step fijo y contact callbacks -> eventos del motor

Restricciones:
- PROHIBIDO exigir Box2D como dependencia obligatoria del motor.
- Debe existir una ruta “sin Box2D” (legacy backend).
- No depender de UI.

Validación:
- Escena canónica: stack de cajas y una bola -> resultados reproducibles (misma máquina).
- Benchmark: coste por step reportado.
```

**E.3 — “CCD y fast movers: política explícita + tests”**
```text
Antes de cambiar nada:
1) Identifica el timestep del motor y cómo se calcula dt.
2) Determina si hay objetos rápidos (“bullets”) y cómo colisionan hoy.

Objetivo:
- Definir una política de CCD:
  - qué componentes la activan,
  - qué coste/perf implica (documentado),
  - fallback si el backend no soporta CCD real.
- Añadir test de “no tunneling” (escenario bala vs pared).

Restricciones:
- No hacer promesas falsas: si no hay CCD real, documenta límites.
- PROHIBIDO que la solución sea “subir fps en UI”: debe ser runtime + datos.

Validación:
- Test automatizado donde un objeto rápido no atraviesa un collider.
- Métricas del coste adicional visibles.
```

**E.4 — “Joints/constraints + CharacterController data-driven”**
```text
Antes de cambiar nada:
1) Revisa si hay lógica ad-hoc de “personaje” (gravedad, suelo) y cómo se implementa.
2) Revisa si el motor ya distingue entre rigidbody y controlador de personaje.

Objetivo:
- Implementar el “CharacterController2D” como componente data-driven:
  - move_and_collide / move_and_slide semantics (si aplican) o equivalente documentado.
- Implementar joints mínimos (fixed + distance o equivalente) si el backend lo soporta.

Restricciones:
- PROHIBIDO mezclar lógica de personaje dentro del editor.
- Todo debe ser serializable y ejecutable en headless.

Validación:
- 2 escenas: (a) plataforma con personaje, (b) péndulo con joint.
- Debug overlay muestra shapes y joints.
```

### Fase F — Prompts

**F.1 — “Tilemap como modelo serializable (layers, tileset, metadata)”**
```text
Antes de cambiar nada:
1) Verifica si ya existe algo parecido a tilemaps (aunque sea parcial) o si hoy se hace con sprites sueltos.
2) Revisa el Asset DB: cómo referenciar tilesets/atlases.

Objetivo:
- Definir e implementar un componente Tilemap serializable:
  - grid config (cell size, orientación; iso/hex opcional pero no obligatorio)
  - múltiples layers
  - refs a tileset/tilesource por asset ID
  - metadata por tile (flags, tags, custom int/str)

Restricciones:
- PROHIBIDO que el tilemap exista solo “porque el editor lo pinta”.
- La API IA debe poder crear/modificar tilemaps sin UI.

Validación:
- Roundtrip: cargar tilemap, modificar un tile por API, guardar, recargar.
- Validación de schema y migración cubren tilemaps.
```

**F.2 — “Tilemap renderer: chunking + batching + sorting”**
```text
Antes de cambiar nada:
1) Inspecciona el RenderGraph/passes y el batching implementado.
2) Decide la estrategia de chunking (tamaño de chunk, invalidación parcial).

Objetivo:
- Implementar rendering eficiente de tilemaps:
  - reconstrucción incremental al cambiar tiles
  - batches por atlas/material y por chunk
  - sorting por layer/order

Restricciones:
- PROHIBIDO recomponer todo el mapa por cada cambio pequeño.
- No uses UI como caché: el runtime debe recomponer chunks por datos.

Validación:
- Escena de stress: tilemap grande (p. ej. 256x256) con 3 layers.
- Métricas muestran batches y coste de rebuild incremental.
```

**F.3 — “Colisiones por tile + composición/merge de shapes”**
```text
Antes de cambiar nada:
1) Revisa el backend de física y si soporta múltiples shapes por body.
2) Decide cómo se mapeará tile metadata -> collider.

Objetivo:
- Generar colliders desde tilemap:
  - por tile (simple) y/o por regiones mergeadas (optimización).
- Mantener datos serializables: el tile dice “colisiona” + tipo de forma (grid/sprite shape).
- Integrar con eventos/reglas declarativas actuales.

Restricciones:
- PROHIBIDO dependencia del editor para generar colliders: debe pasar en runtime y en CLI build-assets.
- Mantén un modo determinista y testeable.

Validación:
- Test: un personaje colisiona con paredes en tilemap.
- Benchmark: coste de generar colliders por mapa.
```

### Fase G — Prompts

**G.1 — “Profiler interno + métricas públicas (API y headless)”**
```text
Antes de cambiar nada:
1) Identifica qué métricas ya existen (si hay contadores/drawcalls/logs).
2) Analiza el impacto de instrumentación actual.

Objetivo:
- Implementar un profiler interno:
  - tiempos por sistema (ECS systems)
  - render: batches/draw calls
  - física: step time, contactos, islands (si aplica)
  - memoria aproximada (si es posible)
- Exponer métricas por API y CLI (export JSON).

Restricciones:
- PROHIBIDO que el profiler sólo viva en el editor.
- No introducir dependencias pesadas; prioriza simplicidad.

Validación:
- CLI: `profile_run scene.json --frames 600 --out report.json`.
- Tests: report JSON tiene esquema estable (versionado).
```

**G.2 — “Debug overlays como RenderPass y ‘debug primitives’”**
```text
Antes de cambiar nada:
1) Revisa el RenderGraph y dónde insertar un Debug pass.
2) Identifica qué datos quieres dibujar: AABB, colliders, joints, tile chunks, cámara, selección.

Objetivo:
- Un sistema de debug draw:
  - primitives (line/rect/circle) data-driven
  - un RenderPass “DebugOverlay”
- Debe poder activarse por CLI/flag y por API IA.

Restricciones:
- PROHIBIDO dibujar debug desde la UI directamente.
- No mezclar gameplay logic con debug.

Validación:
- Escena canónica muestra overlays correctos.
- Headless puede emitir “debug dump” (p. ej. SVG/PNG opcional) o al menos logs de geometría.
```

**G.3 — “Suite CLI/CI local: validate, migrate, build-assets, run, profile, rollout”**
```text
Antes de cambiar nada:
1) Identifica herramientas CLI ya existentes y cómo se invocan.
2) Identifica configuración de proyecto (paths, settings).

Objetivo:
- Consolidar un CLI único (subcomandos):
  - validate (scenes/assets)
  - migrate
  - build-assets
  - run-headless
  - profile_run
- Añadir documentación /docs/cli.md con ejemplos reproducibles.

Restricciones:
- PROHIBIDO scripts “solo funcionan en tu máquina”; parametriza.
- No dependas de UI.

Validación:
- Un comando “smoke” que ejecute todo en orden y falle de forma clara.
```

### Fase H — Prompts

**H.1 — “Wrapper Gymnasium: Env(reset/step) sobre tu runtime headless”**
```text
Antes de cambiar nada:
1) Revisa tu API programática para IA y el loop de simulación.
2) Identifica cómo se hace reset de mundo/escena y cómo se avanza un step.

Objetivo:
- Implementar una clase que siga el contrato Gymnasium:
  - reset(seed=..., options=...) -> (obs, info)
  - step(action) -> (obs, reward, terminated, truncated, info)
- Definir “action spec” y “observation spec” versionados (documento + código).
- Soportar modo headless por defecto.

Restricciones:
- PROHIBIDO que obs/action dependan de UI o de assets cargados solo en editor.
- No asumas un único agente: diseña para extender a multiagente (sin implementarlo aún).

Validación:
- Un script de prueba que haga random rollouts 10 episodios y guarde un dataset JSONL/NPZ (elige, justifica).
- Reproducibilidad: misma seed -> mismos resultados (según alcance definido en Fase A).
```

**H.2 — “Wrapper PettingZoo (ParallelEnv o AEC) para multiagente”**
```text
Antes de cambiar nada:
1) Revisa el wrapper Gymnasium y la definición de specs.
2) Decide si tu motor necesita acciones simultáneas (Parallel) o turn-based (AEC); justifica.

Objetivo:
- Implementar un wrapper PettingZoo:
  - API mínima coherente (reset/step/agents/terminations/truncations/infos)
  - mapping agent_id -> entidad/actor en tu mundo
- Soportar al menos 2 agentes simultáneos.

Restricciones:
- PROHIBIDO duplicar el mundo por agente; comparten RuntimeWorld (con aislamiento por IDs).
- No dependas de UI.

Validación:
- Un ejemplo “toy” de 2 agentes (p. ej. empujarse, recoger goals, etc.) que corra headless.
- Dataset de rollouts multiagente generado.
```

**H.3 — “Scenario generator + dataset logging (replays + metadatos)”**
```text
Antes de cambiar nada:
1) Identifica cómo hoy se crean escenas por API y cómo se guardan.
2) Identifica timeline/snapshots actuales.

Objetivo:
- Implementar un generador de escenarios data-driven:
  - toma una plantilla (prefab/scene) y aplica randomizaciones controladas por seed.
  - guarda: escena generada + seed + specs + métricas.
- Implementar logging de episodios:
  - acciones, observaciones (o referencias), rewards, eventos, fingerprint por step.

Restricciones:
- PROHIBIDO “random” sin seed.
- Dataset debe ser reproducible y versionado.

Validación:
- Generar 100 escenarios y correr 100 episodios headless, con reporte agregado.
- Poder re-ejecutar un episodio por ID y reproducir sus resultados.
```

**H.4 — “Runner paralelo headless (vectorización simple) + límites de recursos”**
```text
Antes de cambiar nada:
1) Revisa CLI y headless run.
2) Decide estrategia: subprocess por entorno vs múltiples mundos en un proceso (justifica).

Objetivo:
- Implementar un runner paralelo:
  - ejecuta N entornos en paralelo para generar experiencia rápidamente.
  - controla CPU/memoria y timeouts.
- Añadir modos:
  - “fast sim” sin render
  - “render occasionally” (si aplica) para debugging.

Restricciones:
- PROHIBIDO que el runner requiera GPU o UI.
- Debe integrarse con el dataset logging de H.3.

Validación:
- Benchmark: N=8 entornos durante 10k steps y reporte de throughput.
- Manejo de fallos: si un worker crashea, el runner reporta y continúa (o aborta) según configuración.
```

## Orden recomendado de ejecución de prompts

1. A.1 — Inventario técnico + contrato de arquitectura verificable  
2. A.2 — Harness de pruebas headless + golden runs de simulación  
3. A.3 — Determinismo mínimo: seed, orden y state hash  
4. B.1 — Especificación de schema vNext (escenas/prefabs/assets)  
5. B.2 — Validación offline y migraciones (N-1 → N)  
6. B.3 — Prefab overrides como diff/patch (aplicación al cargar)  
7. B.4 — Contrato UI traduce modelo: API de edición transaccional  
8. C.1 — Asset DB con IDs estables y dependencias  
9. C.2 — Importers + cache determinista + invalidación  
10. C.3 — Atlas pipeline y bundling reproducible con build report  
11. D.1 — Render layers + render passes (render graph mínimo)  
12. D.2 — Batching por material/atlas y disciplina tipo SpriteBatch  
13. D.3 — Render targets y composición  
14. D.4 — Infraestructura de materiales/shaders (sin editor de shaders aún)  
15. E.1 — API de física estable y backend pluggable  
16. E.2 — Integración Box2D opcional (scope mínimo)  
17. E.3 — CCD y fast movers: política explícita + tests  
18. E.4 — Joints/constraints + CharacterController data-driven  
19. F.1 — Tilemap como modelo serializable (layers, tileset, metadata)  
20. F.2 — Tilemap renderer: chunking + batching + sorting  
21. F.3 — Colisiones por tile + composición/merge de shapes  
22. G.1 — Profiler interno + métricas públicas (API y headless)  
23. G.2 — Debug overlays como RenderPass y debug primitives  
24. G.3 — Suite CLI/CI local: validate, migrate, build-assets, run, profile, rollout  
25. H.1 — Wrapper Gymnasium: Env(reset/step) sobre runtime headless  
26. H.2 — Wrapper PettingZoo (ParallelEnv o AEC) para multiagente  
27. H.3 — Scenario generator + dataset logging (replays + metadatos)  
28. H.4 — Runner paralelo headless (vectorización simple) + límites de recursos  

## Supuestos y decisiones de priorización

Este roadmap prioriza primero **verificabilidad y construcción sobre roca**, y después features “visibles”, porque los motores investigados muestran que las features de alto nivel (tilemaps complejos, física avanzada, iluminación, authoring) dependen de pilares como **serialización estable**, **pipeline de assets**, **render/batching**, **profiling** y **headless tooling**. citeturn1search0turn12search7turn5search23turn2search0

Supuestos explícitos (marcados donde son inferencias):
- **Inferencia:** tu motor quiere ser “usable como simulador” (IA-first real), por lo que conviene adoptar contratos estándar del ecosistema RL en Python (Gymnasium/PettingZoo) en lugar de inventar una API nueva. citeturn10search0turn10search1
- **Inferencia:** hay una base suficiente de runtime/headless como para convertirla en harness reproducible sin rehacer arquitectura, por eso Fase A se centra en tests/contratos y no en refactors masivos.
- **Inferencia:** el coste de calls de render y de física crecerá; por eso batching, atlas y profiling forman un “bloque” temprano (C+D+G), alineado con prácticas como atlas de sprites en Unity y pipelines/preprocesado en MonoGame/libGDX. citeturn12search2turn1search0turn3search20

Decisiones de “qué se deja para más adelante” (por dependencia y retorno):
- Iluminación 2D completa (estilo URP 2D) se plantea como **opcional** dentro de D, porque requiere materiales/shaders bien definidos y añade complejidad. citeturn4search2turn13search1
- Un editor avanzado (shaders visuales, graph tools complejos) se pospone deliberadamente: primero debe existir el **modelo serializable** y la **API de edición transaccional** (B.4), para evitar UI como fuente de verdad. citeturn2search6turn2search0
- Determinismo cross-platform estricto no se promete: incluso Unity indica límites prácticos para física 2D entre máquinas, pese a usar Box2D. citeturn9search3