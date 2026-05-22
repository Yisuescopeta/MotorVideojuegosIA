# Planes operativos de Queen

Authority: operational-plan

Este directorio contiene planes de ejecucion del sistema Queen.
**No son documentacion canonica del producto** ni fuente de verdad del motor.

## Capa documental

Los planes son artefactos operativos, no documentacion canonica.
El orden de autoridad del repo sigue siendo:

1. Codigo y tests.
2. `EngineAPI` publica en `engine/api/`.
3. CLI oficial `motor` en `motor/cli.py` y `motor/cli_core.py`.
4. Documentacion canonica enlazada desde `docs/README.md`.
5. Archivo historico en `docs/archive/`.

Los planes operativos Queen estan **por debajo** de estas fuentes.
Si un plan contradice codigo, tests o docs canonicas, el plan debe corregirse.

## Estructura

```
docs/plans/
├── README.md          ← este archivo
├── active/             ← planes en ejecucion (versionados en git)
│   └── <task_id>-<slug>.md
└── archive/            ← planes terminados o cancelados
    └── <task_id>-<slug>.md
```

## Ciclo de vida de un plan

1. **Creacion**: Queen detecta que la tarea requiere Long Task Plan Mode.
   Genera un plan en `docs/plans/active/<task_id>-<slug>.md` usando el
   template definido en `docs/queen_long_task_mode.md`.

2. **Ejecucion**: Queen sincroniza el plan antes de cada fase (lee secciones
   relevantes) y lo actualiza despues de cada fase (estado, progreso, riesgos).

3. **Finalizacion**: Al terminar (completed, partial, blocked o failed),
   el plan se mueve a `docs/plans/archive/`.

## Formato obligatorio

Todo plan debe comenzar con:

```md
# Queen Execution Plan: <nombre>

Status: active|completed|blocked|failed
Authority: operational-plan
Task ID: queen-YYYYMMDD-NNN
Created at: <ISO timestamp>
Updated at: <ISO timestamp>
Mode: long-task-plan
```

## Ver tambien

- `docs/queen_long_task_mode.md` — documentacion completa del modo.
- `AGENTS.md` — contrato operativo de agentes.
- `.opencode/agents/queen.md` — prompt del agente Queen.
