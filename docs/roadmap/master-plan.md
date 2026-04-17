# Plan Maestro Del Motor 2D

Estado: planificacion operativa. Este documento coordina ejecucion por fases y
no describe capacidades actuales del motor por si mismo. La fuente de verdad
vigente sigue en codigo, tests y docs canonicas enlazadas desde `docs/README.md`.

## Objetivo

Dejar una secuencia de fases que permita abrir ramas y workspaces paralelos sin
mezclar contratos, refactors amplios ni cambios transversales opacos.

## Tipos de rama

- `chore/<scope>-<milestone>` para base operativa, estructura y mantenimiento.
- `refactor/<scope>-<milestone>` para cambios internos acotados sin feature nueva.
- `feat/<scope>-<milestone>` para capacidad nueva dentro de un subsistema.
- `test/<scope>-<milestone>` para cobertura o harnesses de regresion.
- `docs/<scope>-<milestone>` para cambios documentales puros.
- `integration/<dominio>` para integracion temporal por dominio.

## Gate antes de ramas grandes

Antes de abrir ramas de features grandes debe estar listo todo esto:

- Fase 0 mergeada.
- Estrategia de ramas publicada.
- Limites modulares publicados.
- Guia de prompts Codex publicada.
- Plantilla PR tecnica lista.
- Validacion documental y contractual en verde.

## Ready To Branch

Una fase o milestone queda lista para abrir ramas paralelas cuando:

- existe un objetivo unico y medible
- el subsistema principal esta identificado
- los archivos permitidos y excluidos estan listados
- la rama base o `integration/<dominio>` esta definida
- las validaciones minimas estan cerradas antes de empezar

## Fases

| Fase | Objetivo | Dependencias minimas | Ramas previstas |
|---|---|---|---|
| Fase 0 | Fundacion de ramas, workspaces, integracion y prompts | ninguna | `chore/repo-workspace-foundation`, `docs/*` |
| Fase 1 | Base tecnica compartida para trabajo posterior | Fase 0 | `chore/base-*`, `refactor/base-*`, `integration/base-tecnica` |
| Fase 2 | Runtime base y ciclo operativo estable | Fase 1 | `feat/runtime-*`, `test/runtime-*`, `integration/runtime` |
| Fase 3 | Render oficial del motor | Fase 1 y base runtime definida | `feat/render-*`, `refactor/render-*`, `integration/render` |
| Fase 4 | Fisica y contrato comun de backends | Fase 1 y runtime estable | `feat/physics-*`, `test/physics-*`, `integration/fisica` |
| Fase 5 | Tilemaps sobre la base serializable existente | Fase 1, render y fisica alineados si aplica | `feat/tilemap-*`, `test/tilemap-*`, `integration/tilemaps` |
| Fase 6 | Animacion y flujos relacionados | Fase 1 y render estable | `feat/animation-*`, `test/animation-*`, `integration/animacion` |
| Fase 7 | UI serializable y tooling asociado | Fase 1 y runtime estable | `feat/ui-*`, `test/ui-*`, `integration/ui` |
| Fase 8 | Audio oficial del motor | Fase 1 | `feat/audio-*`, `test/audio-*`, `integration/audio` |
| Fase 9 | Navegacion y pathing integrable | Fase 1 y dependencia tecnica explicita | `feat/navigation-*`, `test/navigation-*`, `integration/navegacion` |
| Fase 10 | Editor y authoring visual sobre contratos ya fijados | Fase 1, runtime y subsistemas base integrados | `feat/editor-*`, `refactor/editor-*`, `integration/editor` |
| Fase 11 | Tooling, automatizacion y soporte de flujo | Fase 1; puede correr en paralelo si no invade runtime | `feat/tooling-*`, `docs/tooling-*`, `integration/tooling` |

## Dependencias por capas

- Base tecnica debe cerrarse antes de ampliar runtime, render o fisica.
- Runtime, render y fisica son la base de varias fases posteriores.
- Tilemaps, animacion, UI y audio deben apoyarse en contratos ya integrados.
- Navegacion y tooling pueden avanzar en paralelo si respetan limites modulares.
- Editor debe consolidar contratos existentes, no redefinirlos tarde.

## Regla operativa

- Cada rama abre milestones pequenos y cerrables.
- Una rama grande debe apoyarse en `docs/roadmap/milestone-template.md`.
- Si aparece una decision transversal, se registra primero en
  `docs/roadmap/rfc-lite-template.md`.
- Este plan no sustituye `docs/architecture.md`, `docs/module_taxonomy.md`,
  `docs/api.md` ni `docs/cli.md`.
