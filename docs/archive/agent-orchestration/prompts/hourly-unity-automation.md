# Prompt Base para Automatizacion Horaria Unity

Actua sobre el proyecto `MotorVideojuegosIA` como agente autonomo de mejora
incremental.

## Mision

Usa la skill `unity-feature-adapter` para investigar funcionalidades de Unity y
adaptarlas al motor manteniendo su caracteristica principal, pero siempre
siguiendo el estado del archivo
`docs/agent-orchestration/registro-automatizacion-unity.md`.

## Flujo obligatorio en cada ejecucion

1. Leer `docs/agent-orchestration/registro-automatizacion-unity.md`.
2. Leer `docs/agent-orchestration/README.md`.
3. Identificar la tarea prioritaria segun el propio registro:
   - primero `[!]`
   - despues `[~]`
   - despues `[ ]`
   - si no existe ninguna, investigar una nueva feature de Unity y anadir una
     propuesta resumida al registro
4. Si la tarea elegida implica adaptar una feature de Unity, usar la skill
   `unity-feature-adapter`.
5. Implementar el cambio minimo completo que mantenga la regla IA-first.
6. Actualizar el registro:
   - estado
   - archivos tocados
   - pasos de verificacion manual
   - notas de riesgos o limites
7. Validar con pruebas no visuales siempre que sea posible.
8. No marcar tareas como verificadas por humano.

## Regla inviolable

Ninguna funcionalidad puede tener su fuente de verdad solo en la interfaz o en
estado no serializable. Toda accion editable por el usuario debe representarse
como codigo o datos accesibles por IA mediante API. La UI solo traduce ese
modelo.

## Restricciones

- No repetir tareas ya marcadas como `[v]`, salvo que el registro indique una
  incidencia nueva.
- No abrir trabajo grande paralelo si hay una tarea ya empezada.
- Si una implementacion falla o queda a medias, dejar la tarea en `[~]` o `[!]`
  con nota breve y accion siguiente recomendada.
- Mantener el registro corto, concreto y util para la siguiente ejecucion.
