# Workflow de Reina

## Alcance

Usar Reina solo por activación explícita para trabajo largo, crítico, arquitectónico, multi-fase, distribuido entre subsistemas o necesitado de memoria persistente y revisión independiente. Usar flujo estándar de `AGENTS.md` para tareas rutinarias.

## Responsabilidades

- Sesión raíz: conservar estado, asignar roles, aplicar gates, resolver continuidad y reportar resultado terminal.
- Agentes read-only: investigar, definir TEST CONTRACT o plan, validar, revisar y auditar sin modificar workspace.
- Agentes con escritura: modificar exclusivamente write set autorizado. Reservar trabajo funcional para builders y documentación para documenter.

## Inicio y fases

Ejecutar al inicio:

```text
RECON
-> MODEL ROUTE
-> TEST CONTRACT
-> PLAN
-> CRÍTICA DEL PLAN
-> PERSISTIR PLAN
```

Después repetir:

```text
LOAD PLAN
-> PLAN SYNC
-> TEST CONTRACT SYNC
-> IMPLEMENTAR FASE
-> DOCUMENTAR SI APLICA
-> VALIDAR
-> REVIEW
-> AI AUDIT SI APLICA
-> UPDATE PLAN
```

Mantener plan como memoria operativa resumida: hechos, decisiones, evidencias, estado, hallazgos y siguiente acción. Sincronizarlo antes y después de cada fase. No usarlo para reemplazar fuentes reales.

## Continuidad y paralelismo

Continuar automáticamente mientras exista siguiente fase válida. Una fase verde no completa tarea. Paralelizar lectura independiente; serializar escritura por defecto. Permitir builders concurrentes solo con write sets disjuntos. Reutilizar contexto de agentes en seguimientos y evitar reconocimientos repetidos.

## Estados terminales no exitosos

- `blocked`: impedimento externo, permiso o dato imprescindible impide continuar; registrar razón y desbloqueo requerido.
- `partial`: existe progreso útil verificado, pero quedan criterios o fases sin cerrar, incluido agotamiento de ciclos.
- `failed`: ejecución o validación demuestra que el resultado no cumple y no queda vía segura dentro del alcance.

Usar `planning_only` solo si el usuario pidió exclusivamente planificación.
