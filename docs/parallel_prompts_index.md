# Indice de prompts paralelos para mejoras del motor

## Proposito

Este documento sirve como indice operativo de los prompts finales listos para usar en los distintos hilos de trabajo paralelos.

Cada hilo incluye:

- objetivo del hilo
- rama sugerida
- wave recomendada
- criterio de cierre
- prompt final listo para pegar

Este documento complementa a `docs/parallel_execution_plan.md`.

## Vista rapida

| Hilo | Rama sugerida | Wave | Criterio de cierre |
|---|---|---|---|
| [Audio 2D runtime](#hilo-1---audio-2d-runtime) | `feature/w1-audio2d-runtime` | Wave 1 | tests de audio verdes, sin tocar core ni render |
| [Navegacion / pathfinding core](#hilo-2---navegacion--pathfinding-core) | `feature/w1-navigation-core` | Wave 1 | modulo util, tests verdes, sin tocar tilemap ni fisica |
| [Animator runtime + authoring](#hilo-3---animator-runtime--authoring) | `feature/w1-animator-authoring` | Wave 1 | animator y panel estables, serializacion compatible |
| [Tilemap authoring / modelo](#hilo-4---tilemap-authoring--modelo) | `feature/w1-tilemap-authoring` | Wave 1 | roundtrip verde y schema congelado |
| [Tilemap render / chunking](#hilo-5---tilemap-render--chunking) | `feature/w2-tilemap-render` | Wave 2 | metricas y tests de render verdes |
| [Tilemap collisions runtime](#hilo-6---tilemap-collisions-runtime) | `feature/w3-tilemap-collision` | Wave 3 | bake estable en PLAY y tests verdes |
| [Fisica core / backend](#hilo-7---fisica-core--backend) | `feature/w4-physics-core` | Wave 4 | fallback intacto y contrato fisico estable |

---

## Hilo 1 - Audio 2D runtime

### Rama sugerida

`feature/w1-audio2d-runtime`

### Wave

`Wave 1`

### Criterio de cierre

Se considera cerrado cuando:

- los tests de audio añadidos o modificados pasan
- `play_audio`, `stop_audio` y `get_audio_state` siguen funcionando
- no se toca `game.py`, `runtime_controller.py`, `render_system.py` ni `scene_manager.py`
- no se introducen dependencias obligatorias nuevas

### Prompt final

```text
Trabaja únicamente en la línea "Audio 2D runtime" del repositorio MotorVideojuegosIA.

CONTEXTO
El motor ya tiene:
- componente AudioSource
- sistema AudioSystem
- endpoints runtime para play_audio, stop_audio y get_audio_state

OBJETIVO
Mejorar la capacidad runtime de audio 2D sin tocar el core del motor ni el render.
El trabajo debe quedarse dentro del dominio audio.

ALCANCE PERMITIDO
Puedes modificar solo:
- engine/components/audiosource.py
- engine/systems/audio_system.py
- engine/api/_runtime_api.py
- tests relacionados con audio
- documentación específica del módulo de audio

ALCANCE PROHIBIDO
No puedes modificar:
- engine/core/game.py
- engine/app/runtime_controller.py
- engine/systems/render_system.py
- engine/scenes/scene_manager.py
- engine/api/_authoring_api.py

OBJETIVOS FUNCIONALES
Implementa una mejora realista y acotada de audio 2D. Prioriza:
- mejor estado runtime de reproducción
- control más claro del componente AudioSource
- soporte compatible para parámetros de espacialidad 2D si es viable dentro del perímetro
- robustez en play/stop/update
- mejor trazabilidad del estado para inspección runtime

RESTRICCIONES TÉCNICAS
- No cambies el orden global de update del motor.
- No metas dependencias obligatorias nuevas.
- No rompas la serialización actual de AudioSource; si amplías el payload, debe ser compatible hacia atrás.
- No implementes una falsa solución solo de UI.
- No toques render, gameplay general, SceneManager ni bootstrap.

VALIDACIÓN OBLIGATORIA
Debes:
- añadir tests unitarios o de integración de audio
- mantener funcionando:
  - get_audio_state(entity_name)
  - play_audio(entity_name)
  - stop_audio(entity_name)
- cubrir con tests el comportamiento nuevo que introduzcas

CRITERIO DE PARADA
Si para hacer bien la tarea necesitas tocar runtime_controller, game.py o render_system.py:
- no los toques
- explica exactamente por qué sería necesario
- deja la implementación cerrada hasta el máximo posible sin invadir esos archivos

FORMATO DE ENTREGA
Devuelve:
1. resumen técnico breve
2. lista exacta de archivos modificados
3. lista exacta de tests añadidos o modificados
4. posibles limitaciones restantes
```

---

## Hilo 2 - Navegacion / pathfinding core

### Rama sugerida

`feature/w1-navigation-core`

### Wave

`Wave 1`

### Criterio de cierre

Se considera cerrado cuando:

- existe un modulo base usable de navegacion
- los tests unitarios del algoritmo o infraestructura pasan
- no se toca tilemap, fisica, render ni runtime_controller
- si se añade componente publico, queda registrado correctamente

### Prompt final

```text
Trabaja únicamente en la línea "Navegación / Pathfinding core" del repositorio MotorVideojuegosIA.

CONTEXTO
Actualmente no existe un módulo de navegación/pathfinding consolidado.
La tarea debe crear una base nueva, desacoplada de física y tilemaps.

OBJETIVO
Crear una infraestructura inicial de navegación/pathfinding 2D orientada a uso por IA y scripts,
sin integrarla todavía con colisiones runtime ni con Tilemap.

ALCANCE PERMITIDO
Puedes modificar solo:
- engine/navigation/* (nuevo módulo)
- tests nuevos de navegación
- documentación nueva de navegación
- engine/api/_runtime_api.py solo si necesitas exponer una API mínima de consulta
- engine/api/_authoring_api.py solo si necesitas una API mínima de authoring
- engine/levels/component_registry.py solo si introduces un componente público nuevo

ALCANCE PROHIBIDO
No puedes modificar:
- engine/tilemap/*
- engine/components/tilemap.py
- engine/systems/physics_system.py
- engine/systems/collision_system.py
- engine/physics/*
- engine/app/runtime_controller.py
- engine/systems/render_system.py
- engine/core/game.py

OBJETIVOS FUNCIONALES
Prioriza:
- estructura base del módulo
- algoritmo o infraestructura de pathfinding usable
- API mínima y clara
- posibilidad de crecer después hacia integración con tilemaps
- tests puros y deterministas

RESTRICCIONES TÉCNICAS
- No acoples esta primera versión a Tilemap.
- No dependas del backend físico.
- No alteres el loop global del motor.
- No metas visualización ni overlays en esta fase.
- Si introduces componente público, regístralo correctamente y deja su serialización clara.

VALIDACIÓN OBLIGATORIA
Debes:
- añadir tests unitarios de la lógica de pathfinding
- añadir tests de serialización si existe componente o recurso serializable
- añadir tests de API si expones métodos nuevos por EngineAPI

CRITERIO DE PARADA
Si descubres que para completar la tarea necesitas tocar física, tilemaps o runtime_controller:
- no lo hagas
- documenta exactamente la dependencia
- deja una base cerrada y útil sin esa integración

FORMATO DE ENTREGA
Devuelve:
1. resumen técnico breve
2. lista exacta de archivos modificados
3. lista exacta de tests añadidos o modificados
4. cómo crecería este módulo en una segunda fase
```

---

## Hilo 3 - Animator runtime + authoring

### Rama sugerida

`feature/w1-animator-authoring`

### Wave

`Wave 1`

### Criterio de cierre

Se considera cerrado cuando:

- animator y AnimatorPanel siguen funcionando
- la serializacion de Animator sigue siendo compatible
- los tests del panel y del runtime pasan
- no se toca render general, tilemap ni core runtime

### Prompt final

```text
Trabaja únicamente en la línea "Animator runtime + authoring" del repositorio MotorVideojuegosIA.

CONTEXTO
El motor ya dispone de:
- componente Animator
- AnimationSystem
- AnimatorPanel
- endpoints de authoring para crear, actualizar y eliminar estados de Animator

OBJETIVO
Mejorar la capacidad de animación y su authoring dedicado sin tocar el render general del motor.

ALCANCE PERMITIDO
Puedes modificar solo:
- engine/components/animator.py
- engine/systems/animation_system.py
- engine/editor/animator_panel.py
- secciones relacionadas con Animator dentro de engine/api/_authoring_api.py
- tests de animator
- tests de animator panel
- documentación específica de Animator

ALCANCE PROHIBIDO
No puedes modificar:
- engine/systems/render_system.py
- engine/tilemap/*
- engine/app/runtime_controller.py
- engine/scenes/scene_manager.py
- engine/core/game.py
- engine/inspector/inspector_system.py

OBJETIVOS FUNCIONALES
Prioriza mejoras reales dentro del dominio Animator:
- estados más robustos
- mejor control de transiciones
- mejor edición de frames o slices
- mejoras del AnimatorPanel
- mejoras de serialización compatibles
- mejoras de eventos o finalización si encajan en el sistema existente

RESTRICCIONES TÉCNICAS
- No conviertas este trabajo en un refactor del render.
- No toques tilemaps ni gameplay general.
- Mantén compatibilidad con escenas y payloads existentes.
- No abras rutas de authoring paralelas fuera de SceneManager / EngineAPI.
- No metas dependencias nuevas.

VALIDACIÓN OBLIGATORIA
Debes:
- mantener y ampliar tests de animator/panel
- cubrir con tests el comportamiento nuevo
- verificar que la serialización sigue siendo compatible
- no romper el flujo actual de edición del AnimatorPanel

CRITERIO DE PARADA
Si detectas que una mejora requiere tocar render_system o runtime_controller:
- no lo hagas
- deja la parte interna de Animator resuelta hasta donde sea posible
- documenta la dependencia pendiente

FORMATO DE ENTREGA
Devuelve:
1. resumen técnico breve
2. lista exacta de archivos modificados
3. lista exacta de tests añadidos o modificados
4. limitaciones o mejoras futuras razonables
```

---

## Hilo 4 - Tilemap authoring / modelo

### Rama sugerida

`feature/w1-tilemap-authoring`

### Wave

`Wave 1`

### Criterio de cierre

Se considera cerrado cuando:

- el roundtrip `load -> edit -> save -> load` sigue verde
- el modelo serializable queda mas fuerte o mas claro
- el schema queda congelado al cerrar la rama
- no se toca render ni colisiones runtime

### Prompt final

```text
Trabaja únicamente en la línea "Tilemap authoring / modelo de datos" del repositorio MotorVideojuegosIA.

CONTEXTO
El motor ya dispone de:
- componente Tilemap serializable
- operaciones de EngineAPI para create_tilemap, set_tilemap_tile, clear_tilemap_tile y get_tilemap
- tests de roundtrip y persistencia para Tilemap

OBJETIVO
Mejorar el modelo y authoring de Tilemap sin tocar render ni colisiones runtime.

ALCANCE PERMITIDO
Puedes modificar solo:
- engine/components/tilemap.py
- partes de Tilemap dentro de engine/api/_authoring_api.py
- editor o inspector específico de tilemap si decides crearlo
- tests de tilemap API
- tests de serialización de tilemap
- documentación de Tilemap

ALCANCE PROHIBIDO
No puedes modificar:
- engine/systems/render_system.py
- engine/tilemap/collision_builder.py
- engine/app/runtime_controller.py
- engine/systems/physics_system.py
- engine/systems/collision_system.py
- engine/physics/*
- engine/core/game.py
- engine/scenes/scene_manager.py

OBJETIVOS FUNCIONALES
Prioriza:
- enriquecer el modelo serializable
- mejorar edición por API
- reforzar metadata por tile, layers o tileset si aporta valor
- mantener roundtrip sólido
- preparar el modelo para evoluciones futuras sin invadir render o física

RESTRICCIONES TÉCNICAS
- No hagas una solución que solo funcione por UI.
- La API debe seguir pudiendo crear y modificar tilemaps sin interfaz.
- Cualquier cambio de schema debe ser backward compatible o migrable.
- No toques chunking, batching ni baking de colisiones.
- No metas lógica runtime de gameplay aquí.

VALIDACIÓN OBLIGATORIA
Debes:
- mantener y ampliar tests de roundtrip
- cubrir con tests modificaciones de tiles, layers o metadata nuevas
- verificar save/load tras modificaciones por API
- no romper el payload serializable existente sin migración clara

CRITERIO DE PARADA
Si una mejora requiere tocar render_system o collision_builder:
- no lo hagas
- documenta esa dependencia
- deja el modelo y el authoring cerrados dentro del perímetro

FORMATO DE ENTREGA
Devuelve:
1. resumen técnico breve
2. lista exacta de archivos modificados
3. lista exacta de tests añadidos o modificados
4. nota de compatibilidad del schema
```

---

## Hilo 5 - Tilemap render / chunking

### Rama sugerida

`feature/w2-tilemap-render`

### Wave

`Wave 2`

### Criterio de cierre

Se considera cerrado cuando:

- mejoran o se refuerzan metricas, chunking o rebuild incremental
- `tests/test_render_graph.py` sigue verde
- no se cambia el schema de Tilemap
- no se invade authoring, runtime fisico ni editor

### Prompt final

```text
Trabaja únicamente en la línea "Tilemap render / chunking / profiling" del repositorio MotorVideojuegosIA.

CONTEXTO
RenderSystem ya soporta:
- render graph
- sorting layers
- batching
- tilemaps por chunks con cache y rebuild incremental
- métricas de profiling y debug geometry

OBJETIVO
Mejorar el render de tilemaps dentro de RenderSystem sin tocar el modelo serializable ni el runtime físico.

ALCANCE PERMITIDO
Puedes modificar solo:
- engine/systems/render_system.py
- tests/test_render_graph.py
- documentación técnica de render tilemap

ALCANCE PROHIBIDO
No puedes modificar:
- engine/components/tilemap.py
- engine/api/_authoring_api.py
- engine/tilemap/collision_builder.py
- engine/app/runtime_controller.py
- engine/systems/physics_system.py
- engine/core/game.py
- engine/editor/*

OBJETIVOS FUNCIONALES
Prioriza una mejora acotada y verificable en uno o varios de estos puntos:
- cache de chunks
- rebuild incremental
- métricas
- batching de tilemap
- profiling
- debug de tile chunks

RESTRICCIONES TÉCNICAS
- No cambies el schema de Tilemap.
- No conviertas la tarea en un refactor general de sprites o render global.
- No metas authoring ni cambios de UI.
- No toques gameplay ni colisiones.
- Mantén compatibilidad con las métricas y tests existentes.

VALIDACIÓN OBLIGATORIA
Debes:
- mantener y ampliar tests de render graph
- cubrir explícitamente tilemap chunk rebuilds o métricas afectadas
- no romper el comportamiento headless de profile si está cubierto por tests

CRITERIO DE PARADA
Si para implementar la mejora necesitas tocar Tilemap, collision_builder o runtime_controller:
- no lo hagas
- explica la dependencia exacta
- entrega una mejora cerrada dentro de RenderSystem

FORMATO DE ENTREGA
Devuelve:
1. resumen técnico breve
2. lista exacta de archivos modificados
3. lista exacta de tests añadidos o modificados
4. nota concreta sobre el impacto en rendimiento o mantenibilidad
```

---

## Hilo 6 - Tilemap collisions runtime

### Rama sugerida

`feature/w3-tilemap-collision`

### Wave

`Wave 3`

### Criterio de cierre

Se considera cerrado cuando:

- el bake de colisiones es estable
- el flujo de `PLAY` sigue funcionando
- los tests de `test_tilemap_collision.py` pasan
- no se invade el backend fisico ni el collision system general

### Prompt final

```text
Trabaja únicamente en la línea "Tilemap collisions runtime" del repositorio MotorVideojuegosIA.

CONTEXTO
El motor ya genera colisiones desde Tilemap en runtime.
Actualmente existe:
- engine/tilemap/collision_builder.py
- integración del bake al entrar en PLAY
- tests de tilemap collision

OBJETIVO
Mejorar el baking de colisiones desde Tilemap sin refactorizar la física base del motor.

ALCANCE PERMITIDO
Puedes modificar solo:
- engine/tilemap/collision_builder.py
- tests/test_tilemap_collision.py
- engine/app/runtime_controller.py solo si el cambio es mínimo y estrictamente necesario
- documentación técnica de tilemap collision

ALCANCE PROHIBIDO
No puedes modificar:
- engine/systems/physics_system.py
- engine/systems/collision_system.py
- engine/physics/*
- engine/systems/render_system.py
- engine/components/tilemap.py
- engine/core/game.py
- engine/scenes/scene_manager.py

OBJETIVOS FUNCIONALES
Prioriza:
- mejor generación de regiones sólidas
- mejor merge de shapes
- métricas claras de bake
- robustez del flujo al entrar en PLAY
- compatibilidad con el comportamiento actual del CharacterController2D si aplica

RESTRICCIONES TÉCNICAS
- No cambies el backend físico.
- No alteres el contrato público de física.
- No conviertas esta tarea en una revisión del solver o del collision system.
- No metas cambios en render ni en authoring.
- El ajuste en runtime_controller, si existe, debe ser mínimo.

VALIDACIÓN OBLIGATORIA
Debes:
- mantener y ampliar tests de tilemap collision
- cubrir el bake y sus métricas
- cubrir comportamiento en PLAY
- no romper la interacción actual con gameplay básico

CRITERIO DE PARADA
Si para continuar necesitas tocar physics_system, collision_system o engine/physics:
- no lo hagas
- documenta exactamente el bloqueo
- deja la mejora cerrada dentro de collision_builder y su integración mínima

FORMATO DE ENTREGA
Devuelve:
1. resumen técnico breve
2. lista exacta de archivos modificados
3. lista exacta de tests añadidos o modificados
4. nota sobre cualquier dependencia futura con la física base
```

---

## Hilo 7 - Fisica core / backend

### Rama sugerida

`feature/w4-physics-core`

### Wave

`Wave 4`

### Criterio de cierre

Se considera cerrado cuando:

- el contrato de backend sigue estable
- el fallback a `legacy_aabb` sigue intacto
- `query_physics_ray` y `query_physics_aabb` no se rompen
- las suites de fisica y runtime pasan

### Prompt final

```text
Trabaja únicamente en la línea "Física core / backend contract" del repositorio MotorVideojuegosIA.

CONTEXTO
La física del motor se apoya en:
- un contrato común de backend
- fallback obligatorio a legacy_aabb
- backend box2d opcional
- selección efectiva de backend en runtime
- query_physics_ray y query_physics_aabb como superficie pública relevante

OBJETIVO
Mejorar la física base del motor preservando el contrato público de backends y el fallback existente.

ALCANCE PERMITIDO
Puedes modificar solo:
- engine/systems/physics_system.py
- engine/systems/collision_system.py
- engine/components/rigidbody.py
- engine/physics/*
- engine/app/runtime_controller.py
- tests de física/runtime
- documentación técnica de física

ALCANCE PROHIBIDO
No puedes modificar:
- engine/components/tilemap.py
- engine/tilemap/collision_builder.py
- engine/systems/render_system.py
- engine/core/game.py
- engine/scenes/scene_manager.py
- engine/editor/*
- engine/api/_authoring_api.py

OBJETIVOS FUNCIONALES
Prioriza:
- solidez del contrato de backends
- coherencia del fallback
- mejoras razonables del backend legacy o integración con box2d
- robustez de queries físicas
- consistencia del comportamiento runtime

RESTRICCIONES TÉCNICAS
- Debes mantener el contrato común de backend.
- No rompas:
  - query_physics_ray
  - query_physics_aabb
  - fallback a legacy_aabb
- No metas authoring serializable ni cambios de editor.
- No toques tilemaps ni su baking de colisiones.
- No conviertas esta tarea en un refactor general del motor.

VALIDACIÓN OBLIGATORIA
Debes:
- añadir o ampliar tests de física/runtime
- cubrir selección de backend
- cubrir fallback
- cubrir comportamiento comparable entre backends cuando aplique
- justificar cualquier cambio de comportamiento observable

CRITERIO DE PARADA
Si descubres que la mejora exige tocar tilemaps, render o editor:
- no lo hagas
- documenta el bloqueo
- deja el trabajo encerrado en el dominio físico

FORMATO DE ENTREGA
Devuelve:
1. resumen técnico breve
2. lista exacta de archivos modificados
3. lista exacta de tests añadidos o modificados
4. nota de compatibilidad del contrato físico
```

---

## Regla de uso

Orden recomendado de uso:

1. Audio 2D runtime
2. Navegacion / pathfinding core
3. Animator runtime + authoring
4. Tilemap authoring / modelo
5. Tilemap render / chunking
6. Tilemap collisions runtime
7. Fisica core / backend

Regla operativa:

- si un prompt necesita ampliar perimetro, no se amplía de forma unilateral
- primero se documenta el bloqueo
- luego se revisa si el cambio corresponde a otro hilo

El objetivo de este indice no es solo almacenar prompts. Es usarlos como contratos de trabajo cerrados para minimizar choques de integracion.
