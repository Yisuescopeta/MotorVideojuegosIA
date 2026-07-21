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

Presupuesto operativo: maximo dos readers y un writer simultaneos. Builders son
seriales salvo write sets disjuntos, explicitos y verificados.

## Fallback Codex/OpenCode

Politica native first: usar subagente nativo siempre que la tool exista y conozca
el `agent_type`. El fallback OpenCode solo aplica si falta la tool nativa o el
rol es desconocido para esa tool. No enmascarar fallos de un child nativo ya
existente: timeout, permisos, salida invalida/no JSON o fallo de proceso bloquean
la fase y no activan fallback.

En la condicion elegible (tool nativa ausente o `agent_type` desconocido), Queen
debe intentar automaticamente el fallback antes de `missing_required_agent`. Un
rol esta disponible con native OR mapped OpenCode fallback usable. Bloquear con
`missing_required_agent` solo si ningun backend puede crear el rol. Los errores
del fallback conservan su razon precisa y no se reescriben como agente nativo
ausente; esta prohibido reportar `No ejecuto fallback` si habia fallback mapeado
y no se intento.

Cuando se use fallback, registrar evidencia de backend: `backend`, rol,
`parent_session`, `child_session` y `model`. El runner debe devolver en `stdout`
solo el JSON contractual compacto del child validado; metadata y errores van a
`stderr`.

## Estados terminales no exitosos

- `blocked`: impedimento externo, permiso o dato imprescindible impide continuar; registrar razón y desbloqueo requerido.
- `partial`: existe progreso útil verificado, pero quedan criterios o fases sin cerrar, incluido agotamiento de ciclos.
- `failed`: ejecución o validación demuestra que el resultado no cumple y no queda vía segura dentro del alcance.

Usar `planning_only` solo si el usuario pidió exclusivamente planificación.
