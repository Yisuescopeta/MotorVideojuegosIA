# AGENTS.md

## Proposito

Este repositorio usa un modelo de motor serializable compartido y admite trabajo
paralelo en ramas/worktrees aislados.

Este archivo es el contrato operativo por defecto para agentes de codigo que
trabajen en este repo.

Lee este archivo junto con:

- `docs/README.md`
- `docs/architecture.md`
- `docs/TECHNICAL.md`
- `docs/schema_serialization.md`
- `docs/module_taxonomy.md`
- `docs/agents.md`

Roadmaps historicos, packs de prompts, notas de investigacion y material antiguo
de orquestacion estan archivados bajo `docs/archive/`. Son contexto util, no el
contrato de producto actual.

## Invariantes centrales del repositorio

Estas reglas no son opcionales.

### 1. Fuente persistente de verdad

- `Scene` es la fuente persistente de verdad.
- `World` es una proyeccion operativa.
- Las mutaciones runtime no deben convertirse en authoring state accidental.

### 2. Ruta de authoring

- Los cambios serializables de authoring deben pasar por `SceneManager` o `EngineAPI`.
- No introduzcas rutas nuevas de edicion directa alrededor de flujos compartidos de authoring.
- La mutacion directa de `edit_world` es solo compatibilidad legacy, no la ruta preferida para trabajo nuevo.

### 3. API publica

- `EngineAPI` es la fachada publica estable para agentes, tests, CLI y automatizacion.
- No la saltes en flujos publicos salvo que la tarea requiera explicitamente wiring interno.

### 4. Contrato fisico

- Conserva el contrato comun de backends.
- Conserva el fallback `legacy_aabb`.
- No cambies el significado publico de `query_physics_ray` ni `query_physics_aabb` fuera de trabajo dedicado de fisica.

### 5. Registro de componentes

- Si agregas un componente publico nuevo, registralo en `engine/levels/component_registry.py`.
- No asumas soporte publico para componentes no registrados.

## Archivos criticos

Trata estos archivos como congelados salvo que la tarea lo autorice
explicitamente.

- `engine/scenes/scene_manager.py`
- `engine/core/game.py`
- `engine/app/runtime_controller.py`
- `engine/systems/render_system.py`
- `engine/systems/physics_system.py`
- `engine/systems/collision_system.py`
- `engine/components/tilemap.py`
- `engine/levels/component_registry.py`

Si crees que uno de estos archivos debe cambiar:

1. Detente.
2. Explica exactamente por que.
3. Declara el cambio minimo requerido.
4. No lo cambies en silencio.

## Limites documentales

- La documentacion canonica vive en la raiz de `docs/` y esta indexada por `docs/README.md`.
- La documentacion archivada vive bajo `docs/archive/` y no debe tratarse como fuente de verdad actual.
- El comportamiento publico nuevo debe actualizar docs canonicas, no solo una nota archivada o prompt.
- No promociones una capacidad como actual salvo que este respaldada por codigo, tests, API publica o la CLI oficial `motor`.

## Reglas de perimetro por rama

Cuando trabajes en una rama paralela de feature, permanece estrictamente dentro
del alcance de esa rama.

### Rama: `feature/w1-audio2d-runtime`

Permitido:

- `engine/components/audiosource.py`
- `engine/systems/audio_system.py`
- `engine/api/_runtime_api.py`
- tests de audio
- docs de audio

Prohibido:

- `engine/core/game.py`
- `engine/app/runtime_controller.py`
- `engine/systems/render_system.py`
- `engine/scenes/scene_manager.py`
- `engine/api/_authoring_api.py`

### Rama: `feature/w1-navigation-core`

Permitido:

- `engine/navigation/*`
- tests de navegacion
- docs de navegacion
- adiciones minimas de API en `engine/api/_runtime_api.py` o `engine/api/_authoring_api.py`
- `engine/levels/component_registry.py` solo si se introduce un componente publico

Prohibido:

- `engine/tilemap/*`
- `engine/components/tilemap.py`
- `engine/systems/physics_system.py`
- `engine/systems/collision_system.py`
- `engine/physics/*`
- `engine/app/runtime_controller.py`
- `engine/systems/render_system.py`
- `engine/core/game.py`

### Rama: `feature/w1-animator-authoring`

Permitido:

- `engine/components/animator.py`
- `engine/systems/animation_system.py`
- `engine/editor/animator_panel.py`
- partes especificas de animator en `engine/api/_authoring_api.py`
- tests de animator
- docs de animator

Prohibido:

- `engine/systems/render_system.py`
- `engine/tilemap/*`
- `engine/app/runtime_controller.py`
- `engine/scenes/scene_manager.py`
- `engine/core/game.py`
- `engine/inspector/inspector_system.py`

### Rama: `feature/w1-tilemap-authoring`

Permitido:

- `engine/components/tilemap.py`
- partes especificas de tilemap en `engine/api/_authoring_api.py`
- archivos de editor/inspector de tilemap
- tests de API tilemap
- tests de serializacion tilemap
- docs de tilemap

Prohibido:

- `engine/systems/render_system.py`
- `engine/tilemap/collision_builder.py`
- `engine/app/runtime_controller.py`
- `engine/systems/physics_system.py`
- `engine/systems/collision_system.py`
- `engine/physics/*`
- `engine/core/game.py`
- `engine/scenes/scene_manager.py`

### Rama: `feature/w2-tilemap-render`

Permitido:

- `engine/systems/render_system.py`
- `tests/test_render_graph.py`
- docs de render tilemap

Prohibido:

- `engine/components/tilemap.py`
- `engine/api/_authoring_api.py`
- `engine/tilemap/collision_builder.py`
- `engine/app/runtime_controller.py`
- `engine/systems/physics_system.py`
- `engine/core/game.py`
- `engine/editor/*`

### Rama: `feature/w3-tilemap-collision`

Permitido:

- `engine/tilemap/collision_builder.py`
- `tests/test_tilemap_collision.py`
- cambios minimos y justificados en `engine/app/runtime_controller.py`
- docs de colision tilemap

Prohibido:

- `engine/systems/physics_system.py`
- `engine/systems/collision_system.py`
- `engine/physics/*`
- `engine/systems/render_system.py`
- `engine/components/tilemap.py`
- `engine/core/game.py`
- `engine/scenes/scene_manager.py`

### Rama: `feature/w4-physics-core`

Permitido:

- `engine/systems/physics_system.py`
- `engine/systems/collision_system.py`
- `engine/components/rigidbody.py`
- `engine/physics/*`
- `engine/app/runtime_controller.py`
- tests de physics/runtime
- docs de fisica

Prohibido:

- `engine/components/tilemap.py`
- `engine/tilemap/collision_builder.py`
- `engine/systems/render_system.py`
- `engine/core/game.py`
- `engine/scenes/scene_manager.py`
- `engine/editor/*`
- `engine/api/_authoring_api.py`

## Expectativas de testing

Antes de reportar finalizacion:

- Ejecuta tests enfocados para el subsistema tocado.
- Ejecuta regresiones adicionales cuando el cambio toque contratos compartidos.
- No deshabilites tests para obtener salida verde.
- No afirmes exito de lint/typecheck/bandit si no los ejecutaste realmente.

Comandos minimos comunes en este repo:

```bash
py -m unittest discover -s tests
py -m ruff check engine cli tools main.py
py -m mypy engine cli tools main.py
```

Usa selecciones mas estrechas cuando corresponda, pero declara exactamente que
ejecutaste.

## Disciplina de merge paralelo

Cada entrega final debe incluir:

1. Resumen tecnico breve.
2. Archivos exactos cambiados.
3. Tests exactos agregados o modificados.
4. Tests exactos ejecutados.
5. Riesgos o limitaciones restantes.
6. Confirmacion de que no se tocaron archivos prohibidos.

## Condiciones de parada

Detente y pide revision antes de continuar si:

- La tarea requiere un archivo prohibido.
- La tarea requiere ampliar el perimetro de la rama.
- La tarea cambiaria un invariante central.
- La tarea crearia un contrato publico nuevo sin aprobacion explicita.

## Regla practica

Prefiere un cambio pequeno y correcto antes que uno amplio y riesgoso.
No optimices por cierre local si eso perjudica la seguridad de merge.
