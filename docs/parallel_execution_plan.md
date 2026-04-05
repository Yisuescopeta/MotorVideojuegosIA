# Plan de ejecucion paralela para mejoras del motor

## Proposito

Este documento fija una hoja operativa para ejecutar varias mejoras del motor en paralelo sin que los cambios se pisen entre si.

La idea no es solo repartir trabajo. La idea es reducir conflictos semanticos y de merge respetando el contrato actual del proyecto:

- `Scene` sigue siendo la fuente de verdad persistente.
- `World` sigue siendo una proyeccion operativa.
- el authoring nuevo debe entrar por `SceneManager` o `EngineAPI`.
- `EngineAPI` sigue siendo la fachada publica estable.
- el contrato fisico sigue pasando por un backend comun con fallback a `legacy_aabb`.

## Contratos globales congelados

Estos contratos no deben tocarse salvo que exista una tarea especifica de core que lo autorice expresamente.

### 1. Persistencia

- `Scene` sigue siendo la fuente de verdad persistente.
- `World` no pasa a ser fuente de verdad.
- no se abren rutas nuevas de guardado al margen del flujo canonico del motor.

### 2. Authoring

- toda mutacion serializable nueva debe entrar por `SceneManager` o `EngineAPI`.
- no se introduce authoring nuevo basado en mutar `edit_world` directamente salvo compatibilidad legacy ya existente.

### 3. API publica

- `EngineAPI` sigue siendo el punto de entrada estable para CLI, automatizacion, tests y agentes.
- nuevas capacidades deben exponerse por `EngineAPI` solo cuando sea necesario y sin romper la superficie actual.

### 4. Fisica

- se mantiene el contrato comun de backend fisico.
- se mantiene el fallback a `legacy_aabb`.
- no se cambia el significado publico de `query_physics_ray` ni `query_physics_aabb` fuera del hilo de fisica.

### 5. Registro de componentes

- si se introduce un componente publico nuevo, debe registrarse en `engine/levels/component_registry.py`.
- no se asume soporte publico para componentes que no esten registrados.

### 6. Tilemap

- el schema serializable de `Tilemap` no se modifica en paralelo desde varios hilos.
- si una rama toca el modelo de `Tilemap`, las ramas de render y colisiones deben tratar ese modelo como congelado hasta cerrar la integracion.

## Convencion de ramas

Formato recomendado:

```text
feature/<wave>-<area>-<scope>
```

Reglas:

- `wave` identifica la ventana de lanzamiento.
- `area` identifica el subsistema tecnico.
- `scope` aclara si el trabajo es `runtime`, `authoring`, `core`, `render`, etc.

## Hilos de trabajo y nombres de rama sugeridos

| Hilo | Rama sugerida | Wave |
|---|---|---|
| Audio 2D runtime | `feature/w1-audio2d-runtime` | Wave 1 |
| Navegacion / pathfinding core | `feature/w1-navigation-core` | Wave 1 |
| Animator runtime + authoring | `feature/w1-animator-authoring` | Wave 1 |
| Tilemap authoring / modelo | `feature/w1-tilemap-authoring` | Wave 1 |
| Tilemap render / chunking | `feature/w2-tilemap-render` | Wave 2 |
| Tilemap collisions runtime | `feature/w3-tilemap-collision` | Wave 3 |
| Fisica core / backend | `feature/w4-physics-core` | Wave 4 |

## Orden de lanzamiento

### Fase 0 - congelacion de contratos

Antes de abrir ramas:

- publicar los contratos globales congelados
- publicar el perimetro permitido de cada hilo
- fijar que no se tocan `SceneManager`, schema de escena, bootstrap, contrato fisico ni `render_system.py` fuera de sus hilos autorizados

### Wave 1 - paralelo seguro

Lanzar a la vez:

- `feature/w1-audio2d-runtime`
- `feature/w1-navigation-core`
- `feature/w1-animator-authoring`
- `feature/w1-tilemap-authoring`

Condicion de salida de Wave 1:

- los tests del area pasan
- no hay cambios laterales
- el modelo de `Tilemap` queda congelado para las siguientes waves

### Wave 2 - render de tilemap

Lanzar solo:

- `feature/w2-tilemap-render`

Condicion de salida:

- metricas y tests de render verdes
- sin cambios del schema de `Tilemap`

### Wave 3 - colision de tilemap

Lanzar solo:

- `feature/w3-tilemap-collision`

Condicion de salida:

- bake estable
- integracion con `PLAY` sin efectos colaterales
- tests de tilemap collision verdes

### Wave 4 - fisica core

Lanzar solo:

- `feature/w4-physics-core`

Condicion de salida:

- fallback intacto
- queries fisicas intactas
- compatibilidad entre backends validada

## Perimetro operativo por hilo

### Hilo 1 - Audio 2D runtime

Objetivo:

- ampliar el soporte runtime de audio 2D sin tocar el core del motor ni el render.

Puede modificar:

- `engine/components/audiosource.py`
- `engine/systems/audio_system.py`
- `engine/api/_runtime_api.py`
- tests relacionados con audio
- documentacion especifica de audio

No puede modificar:

- `engine/core/game.py`
- `engine/app/runtime_controller.py`
- `engine/systems/render_system.py`
- `engine/scenes/scene_manager.py`
- `engine/api/_authoring_api.py`

Riesgo:

- bajo

### Hilo 2 - Navegacion / pathfinding core

Objetivo:

- crear una base de navegacion desacoplada de fisica y tilemaps.

Puede modificar:

- `engine/navigation/*`
- tests nuevos de navegacion
- documentacion nueva de navegacion
- `engine/api/_runtime_api.py` o `engine/api/_authoring_api.py` solo si hace falta una API minima
- `engine/levels/component_registry.py` solo si introduce un componente publico nuevo

No puede modificar:

- `engine/tilemap/*`
- `engine/components/tilemap.py`
- `engine/systems/physics_system.py`
- `engine/systems/collision_system.py`
- `engine/physics/*`
- `engine/app/runtime_controller.py`
- `engine/systems/render_system.py`
- `engine/core/game.py`

Riesgo:

- bajo

### Hilo 3 - Animator runtime + authoring

Objetivo:

- mejorar la capacidad de animacion y su editor dedicado sin tocar el render general del motor.

Puede modificar:

- `engine/components/animator.py`
- `engine/systems/animation_system.py`
- `engine/editor/animator_panel.py`
- partes relacionadas con Animator en `engine/api/_authoring_api.py`
- tests de animator y animator panel
- documentacion especifica de Animator

No puede modificar:

- `engine/systems/render_system.py`
- `engine/tilemap/*`
- `engine/app/runtime_controller.py`
- `engine/scenes/scene_manager.py`
- `engine/core/game.py`
- `engine/inspector/inspector_system.py`

Riesgo:

- bajo a medio

### Hilo 4 - Tilemap authoring / modelo

Objetivo:

- mejorar el modelo serializable y el authoring de Tilemap sin tocar render ni colisiones runtime.

Puede modificar:

- `engine/components/tilemap.py`
- partes de Tilemap dentro de `engine/api/_authoring_api.py`
- editor o inspector especifico de tilemap
- tests de tilemap API
- tests de serializacion de tilemap
- documentacion de Tilemap

No puede modificar:

- `engine/systems/render_system.py`
- `engine/tilemap/collision_builder.py`
- `engine/app/runtime_controller.py`
- `engine/systems/physics_system.py`
- `engine/systems/collision_system.py`
- `engine/physics/*`
- `engine/core/game.py`
- `engine/scenes/scene_manager.py`

Riesgo:

- medio

### Hilo 5 - Tilemap render / chunking / profiling

Objetivo:

- mejorar el render de tilemaps dentro de `RenderSystem` sin tocar el modelo serializable ni el runtime fisico.

Puede modificar:

- `engine/systems/render_system.py`
- `tests/test_render_graph.py`
- documentacion tecnica de render tilemap

No puede modificar:

- `engine/components/tilemap.py`
- `engine/api/_authoring_api.py`
- `engine/tilemap/collision_builder.py`
- `engine/app/runtime_controller.py`
- `engine/systems/physics_system.py`
- `engine/core/game.py`
- `engine/editor/*`

Riesgo:

- medio a alto

### Hilo 6 - Tilemap collisions runtime

Objetivo:

- mejorar el baking de colisiones desde Tilemap sin refactorizar la fisica base.

Puede modificar:

- `engine/tilemap/collision_builder.py`
- `tests/test_tilemap_collision.py`
- `engine/app/runtime_controller.py` solo si el ajuste es minimo y estrictamente necesario
- documentacion tecnica de tilemap collision

No puede modificar:

- `engine/systems/physics_system.py`
- `engine/systems/collision_system.py`
- `engine/physics/*`
- `engine/systems/render_system.py`
- `engine/components/tilemap.py`
- `engine/core/game.py`
- `engine/scenes/scene_manager.py`

Riesgo:

- medio si se mantiene aislado
- alto si se mezcla con cambios de fisica

### Hilo 7 - Fisica core / backend contract

Objetivo:

- mejorar la fisica base del motor preservando el contrato publico de backends y el fallback existente.

Puede modificar:

- `engine/systems/physics_system.py`
- `engine/systems/collision_system.py`
- `engine/components/rigidbody.py`
- `engine/physics/*`
- `engine/app/runtime_controller.py`
- tests de fisica/runtime
- documentacion tecnica de fisica

No puede modificar:

- `engine/components/tilemap.py`
- `engine/tilemap/collision_builder.py`
- `engine/systems/render_system.py`
- `engine/core/game.py`
- `engine/scenes/scene_manager.py`
- `engine/editor/*`
- `engine/api/_authoring_api.py`

Riesgo:

- muy alto
- este hilo debe ir solo

## Criterio de aceptacion por PR

Un PR se acepta solo si cumple todo lo siguiente.

### 1. Identidad clara

El PR debe declarar:

- hilo al que pertenece
- rama desde la que sale
- objetivo en una frase
- perimetro permitido aplicado

### 2. Perimetro respetado

- no toca archivos vetados
- no introduce refactors laterales
- no mezcla dos lineas de trabajo distintas

### 3. Contratos intactos

- no rompe `Scene` como fuente persistente
- no abre una ruta nueva de authoring fuera de `SceneManager` o `EngineAPI`
- no introduce componentes publicos sin registry
- no rompe contrato fisico ni fallback si no es el hilo de fisica

### 4. Validacion tecnica

- añade tests o amplia tests existentes
- mantiene verdes las suites del area
- justifica cualquier cambio de comportamiento observable

### 5. Entrega limpia

El PR debe incluir:

- resumen tecnico breve
- lista exacta de archivos modificados
- lista exacta de tests añadidos o modificados
- limitaciones pendientes
- confirmacion explicita de que no tocó archivos prohibidos

### 6. Rechazo automatico

Se rechaza el PR si ocurre cualquiera de estas situaciones:

- toca `engine/scenes/scene_manager.py` sin ser un trabajo de core autorizado
- toca `engine/systems/render_system.py` desde un hilo no autorizado
- toca fisica desde tilemap collision
- toca el schema de `Tilemap` desde tilemap render
- mete cambios de bootstrap en `engine/core/game.py` o cambios estructurales en `engine/app/runtime_controller.py` fuera del hilo autorizado

## Checklist de revision para merges paralelos

### Checklist corto del reviewer

- [ ] El PR indica hilo y rama
- [ ] El objetivo del PR coincide con el prompt del hilo
- [ ] Los archivos cambiados estan dentro del perimetro permitido
- [ ] No hay cambios en archivos vetados
- [ ] No hay refactor lateral
- [ ] No rompe authoring compartido
- [ ] No rompe serializacion existente sin migracion clara
- [ ] No rompe `EngineAPI`
- [ ] Si hay componente publico nuevo, esta registrado
- [ ] Hay tests nuevos o ajustados para lo añadido
- [ ] La suite del area pasa
- [ ] No hay tests deshabilitados
- [ ] No invade un archivo critico que otro hilo ya esta tocando
- [ ] El PR esta rebaseado sobre `main`
- [ ] El changelog tecnico del PR es suficiente

### Checklist reforzado para archivos criticos

Si un PR toca cualquiera de estos archivos, requiere revision extra:

- `engine/scenes/scene_manager.py`
- `engine/core/game.py`
- `engine/app/runtime_controller.py`
- `engine/systems/render_system.py`
- `engine/systems/physics_system.py`
- `engine/systems/collision_system.py`
- `engine/components/tilemap.py`
- `engine/levels/component_registry.py`

En estos casos el reviewer debe comprobar ademas:

- que el archivo pertenece al perimetro del hilo
- que no hay otra rama activa tocando la misma zona critica
- que no se han ampliado contratos sin autorizacion explicita

## Politica de merge por wave

### Merge de Wave 1

Orden recomendado:

1. `feature/w1-navigation-core`
2. `feature/w1-audio2d-runtime`
3. `feature/w1-animator-authoring`
4. `feature/w1-tilemap-authoring`

Motivo:

- navegacion y audio son los hilos mas aislados
- Animator ya tiene buen modulo propio
- Tilemap authoring conviene cerrarlo el ultimo para congelar schema

### Merge de Wave 2

Merge unico de:

- `feature/w2-tilemap-render`

### Merge de Wave 3

Merge unico de:

- `feature/w3-tilemap-collision`

### Merge de Wave 4

Merge unico de:

- `feature/w4-physics-core`

## Regla practica para evitar choques

Si dos ramas cambian cualquiera de estas zonas al mismo tiempo, no se revisan ni se integran en paralelo. Se serializan:

- `engine/systems/render_system.py`
- `engine/app/runtime_controller.py`
- `engine/systems/physics_system.py`
- `engine/systems/collision_system.py`
- `engine/scenes/scene_manager.py`
- `engine/components/tilemap.py`

## Plantilla para abrir cada PR

```text
Hilo: <nombre del hilo>
Rama: <nombre de rama>
Objetivo: <una frase>
Perimetro permitido: <lista>
Archivos vetados confirmados: <lista>
Tests añadidos/modificados: <lista>
Contratos revisados: <lista>
Riesgos pendientes: <lista corta>
```

## Plantilla para revision rapida

```text
Revision de PR paralela

1. Hilo correcto: OK / NO
2. Rama correcta: OK / NO
3. Perimetro respetado: OK / NO
4. Archivos vetados intactos: OK / NO
5. Contratos intactos: OK / NO
6. Tests suficientes: OK / NO
7. Sin refactor lateral: OK / NO
8. Listo para merge: SI / NO

Observaciones:
- ...
```

## Regla final

En caso de duda entre:

- aceptar un pequeño retraso
- o aceptar una ampliacion de perimetro

la regla es esta:

- se acepta primero el pequeño retraso
- no se acepta ampliar perimetro sin documentarlo y revisarlo

El objetivo de este plan no es maximizar velocidad bruta. Es maximizar velocidad neta de integracion sin romper el contrato del motor.
