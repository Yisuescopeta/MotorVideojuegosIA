# Estrategia De Integracion

Estado: referencia operativa para integrar trabajo paralelo por capas.

## Regla base

La integracion no se hace en una rama global unica. Se hace por dominios con
ramas temporales `integration/<dominio>`.

## Ramas de integracion temporales

- `integration/base-tecnica`
- `integration/runtime`
- `integration/render`
- `integration/fisica`
- `integration/tilemaps`
- `integration/animacion`
- `integration/ui`
- `integration/audio`
- `integration/navegacion`
- `integration/editor`
- `integration/tooling`

Una rama de integracion existe solo mientras agrupa cambios coherentes de un
dominio. No se convierte en nueva fuente de verdad permanente.

## Orden recomendado

1. `integration/base-tecnica` despues de Fase 0.
2. `integration/runtime`.
3. `integration/render` y `integration/fisica`.
4. `integration/tilemaps`, `integration/animacion`, `integration/ui`, `integration/audio`.
5. `integration/navegacion`.
6. `integration/editor`.
7. `integration/tooling` puede correr desde base tecnica si no invade runtime.

## Criterios para promover una rama a integracion

- alcance cerrado a un milestone pequeno
- conflictos resueltos contra su base
- documentacion actualizada si el cambio toca contrato o flujo operativo
- checks enfocados en verde
- sin refactor ajeno metido en la misma rama
- los archivos criticos, si existen, estan tocados con justificacion explicita

## Criterios para promover desde integracion a troncal

- el dominio ya no arrastra conflictos activos entre ramas hijas
- los milestones del dominio quedaron absorbidos o descartados
- la rama de integracion puede explicarse como un cambio coherente
- las validaciones del dominio y las de contrato compartido siguen en verde

## Riesgos tipicos

- ramas demasiado anchas
- drift con la rama base
- cambios transversales ocultos bajo un milestone pequeno
- colision en archivos criticos
- prompts ambiguos que permiten expansion de alcance

## Mitigacion

- dividir en milestones pequenos antes de abrir ramas
- rebasear antes de PR y antes de merge
- usar `docs/architecture/module-boundaries.md` para fijar el touch map
- registrar decisiones transversales en RFC lite antes de editar
- bloquear por defecto archivos criticos y mencionarlos de forma explicita si entran
- exigir prompts con archivos permitidos y excluidos

## Regla de cierre

Cuando una rama de integracion cumple su objetivo:

- se promueve a la rama superior correspondiente
- se cierran o rebasan las ramas hijas restantes
- no se sigue acumulando trabajo nuevo si el dominio ya esta listo para merge
