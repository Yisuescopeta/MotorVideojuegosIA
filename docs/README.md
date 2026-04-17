# Portal documental

Este portal separa documentacion vigente, referencia operativa, tooling
experimental y archivo historico. Si hay conflicto, manda este orden:

1. Codigo y tests.
2. `EngineAPI` publica y CLI oficial `motor`.
3. Documentacion canonica listada aqui.
4. Archivo historico solo como contexto.

## Lee esto primero

| Perfil | Ruta recomendada |
|---|---|
| Nuevo desarrollador | [../README.md](../README.md), luego [architecture.md](architecture.md), [glossary.md](glossary.md) y [CONTRIBUTING.md](../CONTRIBUTING.md). |
| Colaborador ocasional | [../CONTRIBUTING.md](../CONTRIBUTING.md), [documentation_governance.md](documentation_governance.md) y la referencia del area tocada. |
| Mantenedor | [architecture.md](architecture.md), [TECHNICAL.md](TECHNICAL.md), [module_taxonomy.md](module_taxonomy.md), [documentation_governance.md](documentation_governance.md). |
| Agente IA | [agents.md](agents.md), [../AGENTS.md](../AGENTS.md), [api.md](api.md), [cli.md](cli.md) y [MOTOR_AI_JSON_CONTRACT.md](MOTOR_AI_JSON_CONTRACT.md). |

## Si quieres saber...

| Pregunta | Lee |
|---|---|
| Que es el proyecto | [../README.md](../README.md) |
| Cual es la fuente canonica | [architecture.md](architecture.md) y [documentation_governance.md](documentation_governance.md) |
| Que leer primero | Esta pagina y [glossary.md](glossary.md) |
| Como contribuir | [../CONTRIBUTING.md](../CONTRIBUTING.md) |
| Que es experimental | [module_taxonomy.md](module_taxonomy.md) |
| Que interfaz publica existe | [api.md](api.md) y [cli.md](cli.md) |
| Donde mirar arquitectura | [architecture.md](architecture.md) y [TECHNICAL.md](TECHNICAL.md) |
| Donde mirar automatizacion o IA | [agents.md](agents.md), [ai_assisted_workflows.md](ai_assisted_workflows.md) y [MOTOR_AI_JSON_CONTRACT.md](MOTOR_AI_JSON_CONTRACT.md) |
| Donde poner o cambiar docs | [documentation_governance.md](documentation_governance.md) |

## Canon del motor

Estos documentos describen contratos vigentes. No uses material archivado para
contradecirlos.

- [architecture.md](architecture.md) - contrato arquitectonico del repo.
- [TECHNICAL.md](TECHNICAL.md) - referencia tecnica navegable.
- [schema_serialization.md](schema_serialization.md) - contrato de escenas y prefabs.
- [module_taxonomy.md](module_taxonomy.md) - clasificacion por subsistema.
- [api.md](api.md) - referencia publica de `EngineAPI`.
- [cli.md](cli.md) - referencia oficial de la CLI `motor`.
- [MOTOR_AI_JSON_CONTRACT.md](MOTOR_AI_JSON_CONTRACT.md) - contrato del artefacto generado `motor_ai.json`.

## Referencia operativa

- [glossary.md](glossary.md) - conceptos clave para lectores frios.
- [building.md](building.md) - build y distribucion Windows.

## Agentes e IA

- [agents.md](agents.md) - guia breve para agentes trabajando en este repo.
- [../AGENTS.md](../AGENTS.md) - contrato operativo de agentes y reglas de perimetro.
- [ai_assisted_workflows.md](ai_assisted_workflows.md) - base experimental para flujos asistidos por IA.

Los artefactos `motor_ai.json` y `START_HERE_AI.md` se generan por proyecto con:

```bash
py -m motor project bootstrap-ai --project .
```

No son documentacion canonica versionada del repo raiz mientras no se decida
explicitamente versionarlos.

## Experimental/tooling

Estos documentos describen tooling real cuando el codigo existe, pero no amplian
el contrato de `core obligatorio`.

- [navigation.md](navigation.md) - busqueda de rutas experimental.
- [rl.md](rl.md) - wrappers RL, datasets y runners headless.
- [ai_assisted_workflows.md](ai_assisted_workflows.md) - modelos de flujo para automatizacion.
- [tooling_foundation.md](tooling_foundation.md) - tooling local para checks enfocados, audit del registry y soporte read-only de worktrees.

## Gobernanza

- [documentation_governance.md](documentation_governance.md) - reglas para crear, mover y mantener documentacion.
- [documentation_audit.md](documentation_audit.md) - registro de auditoria y decisiones de reorganizacion; no es contrato funcional principal.
- [../CONTRIBUTING.md](../CONTRIBUTING.md) - contribucion tecnica y documental.
- [../SECURITY.md](../SECURITY.md) - reporte de vulnerabilidades.
- [../LICENSE](../LICENSE) - licencia.

## Archivo historico

- [archive/roadmaps/](archive/roadmaps/) - roadmaps y planes de implementacion.
- [archive/research/](archive/research/) - research exploratorio.
- [archive/agent-orchestration/](archive/agent-orchestration/) - prompts y packs de agentes.
- [archive/design-notes/](archive/design-notes/) - notas de diseno y auditorias antiguas.
- [archive/audits/](archive/audits/) - analisis historicos.
- [archive/demos/](archive/demos/) - instrucciones antiguas de demos/ejecucion.

El archivo se conserva para contexto. Puede contener comandos, rutas o claims
obsoletos; verifica siempre contra codigo, tests y docs canonicas.

## Rutas rapidas

Para empezar como desarrollador:

1. Lee [../README.md](../README.md).
2. Lee [architecture.md](architecture.md) y [glossary.md](glossary.md).
3. Ejecuta `py -m motor doctor --project . --json`.
4. Ejecuta los tests de contrato indicados en [../README.md](../README.md).

Para trabajar con serializacion:

1. Lee [schema_serialization.md](schema_serialization.md).
2. Revisa `engine/serialization/schema.py`.
3. Ejecuta `py -m unittest tests.test_schema_validation -v`.

Para automatizar con IA:

1. Lee [agents.md](agents.md).
2. Usa `EngineAPI` o `motor`.
3. Consulta [api.md](api.md), [cli.md](cli.md) y [MOTOR_AI_JSON_CONTRACT.md](MOTOR_AI_JSON_CONTRACT.md).
4. Ignora el archivo historico salvo que busques contexto de decisiones pasadas.
