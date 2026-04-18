## Objetivo

- Cambio principal:
- Resultado esperado:

## Milestone y decision previa

- Rama objetivo:
- Milestone:
- RFC lite:

## Subsistemas tocados

- Subsistema principal:
- Subsistemas secundarios justificados:

## Archivos criticos

- [ ] No toque archivos criticos listados en `AGENTS.md`
- [ ] Si toque archivos criticos y dejo justificacion abajo

Justificacion si aplica:

## Validaciones ejecutadas

- [ ] `py -m unittest tests.test_repository_governance tests.test_motor_cli_contract tests.test_start_here_ai_coherence -v`
- [ ] `py -m unittest tests.test_official_contract_regression tests.test_parser_registry_alignment tests.test_motor_interface_coherence tests.test_motor_registry_consistency -v`
- [ ] `py -m motor --help`
- [ ] `py -m motor doctor --project . --json`
- [ ] Otra validacion enfocada del subsistema

Detalle de validaciones ejecutadas:

## Riesgos restantes

- Riesgo tecnico:
- Alcance no cubierto:

## Checklist de documentacion

- [ ] Revise si el cambio toca contrato publico, schema, CLI o taxonomia
- [ ] Actualice la doc canonica correspondiente si aplicaba
- [ ] Enlace cualquier doc nueva desde `docs/README.md`
- [ ] No promuevo capacidades planificadas como implementadas
- [ ] Mantengo `docs/archive/` como historico, no como fuente de verdad

## Checklist de tests y merge

- [ ] El alcance queda cerrado a un subsistema principal
- [ ] No mezcle refactor amplio con feature no relacionada
- [ ] Rebasee o sincronice la rama contra su base antes de abrir PR
- [ ] Si la rama iba a una `integration/<dominio>`, valide contra esa base
- [ ] Documente warnings, skips o deuda previa del repo si aparecieron
