# OpenCode prompt

Trabaja sobre una rama derivada de `feature/demo-platformer-vertical-slice` o continúa en esa misma rama si no necesitas aislar más cambios.

## Objetivo

Implementar un mini juego de plataformas 2D muy simple dentro de `MotorVideojuegosIA` usando el paquete preparado en `demo/platformer_demo_package/`.

## Antes de tocar código

Lee primero:

- `AGENTS.md`
- `docs/TECHNICAL.md`
- `docs/module_taxonomy.md`
- los componentes y sistemas relevantes para tilemap, animator, audio, character controller y escenas

## Restricciones clave

- `Scene` es la fuente de verdad persistente
- usa `SceneManager` o `EngineAPI` para authoring serializable
- no dependas de navegación/pathfinding para el slice base
- no hagas refactors grandes del motor
- evita tocar archivos críticos salvo necesidad real y justificada

## Alcance del demo

Implementa:

- 1 nivel corto jugable
- jugador con izquierda/derecha
- salto
- colisión con suelo/plataformas usando tilemap
- animaciones: idle, run y jump/fall
- 1 coleccionable
- 1 hazard simple
- 1 meta simple
- audio básico: salto, coleccionable, victoria, derrota

## Assets a usar

Usa los assets descargados o generados por `demo/platformer_demo_package/fetch_selected_assets.py`.

## Validación esperada

El resultado debe validar preferentemente:

- tilemap/modelo de authoring
- animación runtime + authoring
- audio runtime
- física/gameplay 2D básica
- integración correcta de assets serializables
- flujo de escena/entidades compatible con el motor

## Entregable final

Devuelve al final:

- archivos tocados
- tests o comandos ejecutados
- limitaciones restantes
- supuestos adoptados
