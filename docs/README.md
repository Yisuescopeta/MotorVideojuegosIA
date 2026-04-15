# Portal documental

Este portal separa la documentacion vigente de la historica. Si hay conflicto
entre un documento canonico y un documento archivado, manda el documento
canonico y el codigo/tests que lo respaldan.

## Canónico vigente

- [architecture.md](architecture.md) - contrato arquitectonico del repo.
- [TECHNICAL.md](TECHNICAL.md) - referencia tecnica navegable.
- [schema_serialization.md](schema_serialization.md) - contrato de escenas y prefabs.
- [module_taxonomy.md](module_taxonomy.md) - clasificacion por subsistema.
- [api.md](api.md) - referencia publica de `EngineAPI`.
- [cli.md](cli.md) - referencia oficial de la CLI `motor`.
- [MOTOR_AI_JSON_CONTRACT.md](MOTOR_AI_JSON_CONTRACT.md) - contrato generado `motor_ai.json`.

## Agentes e IA

- [agents.md](agents.md) - guia breve para agentes trabajando en este repo.
- [../AGENTS.md](../AGENTS.md) - contrato operativo de agentes y reglas de perimetro.
- [ai_assisted_workflows.md](ai_assisted_workflows.md) - foundation experimental para workflows AI-assisted.

Los artefactos `motor_ai.json` y `START_HERE_AI.md` se generan por proyecto con:

```bash
py -m motor project bootstrap-ai --project .
```

No se tratan como documentacion canonica versionada del repo raiz mientras no se
decida explicitamente versionarlos.

## Experimental/tooling

- [navigation.md](navigation.md) - pathfinding experimental.
- [rl.md](rl.md) - wrappers RL, datasets y runners headless.
- [ai_assisted_workflows.md](ai_assisted_workflows.md) - modelos de workflow para automatizacion.

Estos documentos describen tooling real cuando el codigo existe, pero no amplian
el contrato de `core obligatorio`.

## Archivo historico

- [archive/roadmaps/](archive/roadmaps/) - roadmaps y planes de implementacion.
- [archive/research/](archive/research/) - research exploratorio.
- [archive/agent-orchestration/](archive/agent-orchestration/) - prompts y packs de agentes.
- [archive/design-notes/](archive/design-notes/) - notas de diseno y auditorias antiguas.
- [archive/audits/](archive/audits/) - analisis historicos.
- [archive/demos/](archive/demos/) - instrucciones antiguas de demos/ejecucion.

El archivo se conserva para contexto, pero no es fuente de verdad vigente.

## Auditoria documental

- [documentation_audit.md](documentation_audit.md) - clasificacion, decisiones, inconsistencias corregidas y validaciones.

## Rutas rapidas

Para empezar como desarrollador:

1. Lee [../README.md](../README.md).
2. Lee [architecture.md](architecture.md).
3. Ejecuta `py -m motor doctor --project . --json`.
4. Ejecuta los tests de contrato indicados en [../README.md](../README.md).

Para trabajar con serializacion:

1. Lee [schema_serialization.md](schema_serialization.md).
2. Revisa `engine/serialization/schema.py`.
3. Ejecuta `py -m unittest tests.test_schema_validation -v`.

Para automatizar con IA:

1. Lee [agents.md](agents.md).
2. Usa `EngineAPI` o `motor`.
3. Consulta [api.md](api.md) y [cli.md](cli.md).
4. Ignora el archivo historico salvo que busques contexto de decisiones pasadas.
