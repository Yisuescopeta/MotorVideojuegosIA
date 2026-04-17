# Gobernanza documental

Este documento define como mantener la documentacion del repo sin mezclar
contrato vigente, referencia operativa, tooling experimental y material
historico.

## Autoridad

Cuando dos fuentes discrepan, usa este orden:

1. Codigo y tests.
2. `EngineAPI` publica en `engine/api/`.
3. CLI oficial `motor` en `motor/cli.py` y `motor/cli_core.py`.
4. Docs canonicos enlazados desde [README.md](README.md).
5. Archivo historico en [archive/](archive/) solo como contexto.

No promociones una capacidad como disponible si no esta respaldada por codigo,
tests, `EngineAPI` o la CLI oficial `motor`.

## Capas documentales

| Capa | Ubicacion | Uso |
|---|---|---|
| Entrada | [../README.md](../README.md), [README.md](README.md) | Orientacion rapida y mapa de lectura. |
| Canon | `architecture.md`, `TECHNICAL.md`, `schema_serialization.md`, `module_taxonomy.md`, `api.md`, `cli.md` | Contratos vigentes del motor. |
| Planificacion/gobernanza operativa | `roadmap/`, `architecture/branch-strategy.md`, `architecture/module-boundaries.md`, `architecture/integration-strategy.md`, `ai/codex-prompt-guidelines.md` | Coordina ramas, workspaces, integracion y prompts sin redefinir contrato funcional. |
| Referencia operativa | `building`, `glossary`, guias concretas | Ayuda practica que no redefine contratos. |
| Experimental/tooling | `navigation`, `rl`, `ai_assisted_workflows` | Tooling real fuera del core obligatorio. |
| Archivo | [archive/](archive/) | Contexto historico no normativo. |

## Cuando actualizar cada documento

| Cambio | Documentos que deben revisarse |
|---|---|
| Nueva regla arquitectonica o cambio de invariante | [architecture.md](architecture.md), [TECHNICAL.md](TECHNICAL.md), [../AGENTS.md](../AGENTS.md) si afecta agentes. |
| Cambio de schema, migracion o payload serializable | [schema_serialization.md](schema_serialization.md), [TECHNICAL.md](TECHNICAL.md), tests de schema. |
| Cambio en `EngineAPI` publica | [api.md](api.md), [agents.md](agents.md), tests de contrato API. |
| Cambio en CLI `motor` | [cli.md](cli.md), [MOTOR_AI_JSON_CONTRACT.md](MOTOR_AI_JSON_CONTRACT.md) si afecta bootstrap/capabilities, tests CLI. |
| Promocion o degradacion de subsistema | [module_taxonomy.md](module_taxonomy.md), [architecture.md](architecture.md), docs del subsistema. |
| Nueva capacidad experimental | Doc propio con `Estado: experimental/tooling` o seccion en doc experimental existente. |
| Nueva regla de ramas, workspaces o integracion | `docs/README.md`, esta guia, `docs/documentation_audit.md` y la doc operativa correspondiente en `roadmap/`, `architecture/` o `ai/`. |
| Nuevo documento principal | [README.md](README.md), esta guia y, si aplica, [../README.md](../README.md). |
| Reorganizacion documental | [documentation_audit.md](documentation_audit.md) como registro de decisiones. |

## Reglas editoriales

- Mantener las docs canonicas breves y enlazar a referencias profundas.
- No duplicar listas largas de API o CLI si ya existe una referencia dedicada.
- Etiquetar explicitamente `experimental/tooling` cuando una capacidad no sea
  parte del `core obligatorio`.
- No usar documentos de [archive/](archive/) como prueba de funcionalidad actual.
- No documentar capabilities `planned` como comandos o flujos disponibles.
- No mover material historico a canon sin verificar codigo, tests e interfaz publica.
- Si un termino aparece en varios documentos y puede confundir a lectores frios,
  agregarlo o ajustarlo en [glossary.md](glossary.md).
- `docs/roadmap/` coordina trabajo futuro y no prueba capacidades implementadas.
- `docs/archive/roadmaps/` sigue siendo historico; no debe reabsorberse como
  canon ni como plan operativo vivo.

## Checklist para PRs de documentacion

- La doc nueva o modificada esta enlazada desde el portal correcto.
- Los enlaces Markdown locales funcionan.
- El documento declara si es canon, referencia operativa, experimental/tooling o historico.
- Los cambios de API, CLI, schema o taxonomia actualizan su doc canonica.
- Las capacidades planificadas siguen separadas de las implementadas.
- Las instrucciones antiguas se archivan o se etiquetan como legacy.
- Se ejecutaron tests relevantes, o se explica por que no aplican.

