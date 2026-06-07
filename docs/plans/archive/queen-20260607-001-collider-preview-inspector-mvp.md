# Queen Execution Plan: Collider Preview desde Inspector

Status: completed
Authority: operational-plan
Task ID: queen-20260607-001
Created at: 2026-06-07T00:00:00+02:00
Updated at: 2026-06-07T00:00:00+02:00
Mode: long-task-plan

## Objective

Conectar el Collider del Inspector con un overlay efimero en Scene View que muestre el collider efectivo de la entidad seleccionada.

## Non-goals

- No modificar fisicas runtime.
- No cambiar serializacion, schema ni escenas.
- No implementar edicion de colliders en AnimatorPanel.
- No aplicar escala o rotacion de Transform al contrato legacy del collider.

## Implementation

1. Mantener el toggle y la entidad objetivo como estado efimero de `InspectorSystem`.
2. Construir el payload efectivo usando el Collider base y el override del frame actual de Animator.
3. Sincronizar el snapshot mediante `EditorInteractionController`.
4. Dibujar box, circle, capsule y polygon desde `GizmoSystem`.
5. Apagar la preview cuando cambie o desaparezca la seleccion.

## Validation

- Tests enfocados de authoring de colisiones, Inspector, interaccion del editor y Gizmo.
- Confirmar que no se modifican componentes, Scene, schema ni sistemas fisicos.

## Risks

- El overlay global de debug puede coincidir visualmente; la preview usa verde para colliders y naranja para triggers.
- `collision_frames` sigue siendo authoring visual y no altera las fisicas runtime.
