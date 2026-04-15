# Contributing

## Objetivo

Este repositorio sigue un enfoque incremental. Los cambios deben mantenerse
acotados, revisables y alineados con el comportamiento observable del motor.

## Setup local

```bash
py -m pip install -r requirements.txt
py -m pip install -e .[dev]
py -m unittest discover -s tests
```

En plataformas sin launcher `py`, usa el ejecutable activo de Python 3.11.

## Reglas de trabajo

- Manten cada cambio enfocado en una fase o problema concreto.
- Si cambias comportamiento observable, actualiza tests y documentacion en la
  misma propuesta.
- No introduzcas nuevas dependencias a internals privados del motor fuera del
  core (`engine/core`, `engine/app`, `engine/systems`, `engine/events`).
- Evita mezclar refactors amplios con fixes funcionales pequenos.

## Estilo de contribucion

- Prefiere cambios pequenos con mensajes de commit claros.
- Si tocas CLI, API o contratos serializados, documenta el impacto en el PR.
- Si anades una funcionalidad experimental, deja explicito su alcance y limites.

## Cambios de documentacion

- Usa [docs/README.md](docs/README.md) como portal maestro y
  [docs/documentation_governance.md](docs/documentation_governance.md) como
  checklist editorial.
- Si cambias `EngineAPI`, actualiza [docs/api.md](docs/api.md).
- Si cambias la CLI `motor`, actualiza [docs/cli.md](docs/cli.md).
- Si cambias schemas, migraciones o payloads serializables, actualiza
  [docs/schema_serialization.md](docs/schema_serialization.md).
- Si cambias clasificacion de subsistemas, actualiza
  [docs/module_taxonomy.md](docs/module_taxonomy.md).
- Si cambias invariantes o arquitectura, actualiza
  [docs/architecture.md](docs/architecture.md) y [docs/TECHNICAL.md](docs/TECHNICAL.md).
- No documentes capabilities `planned` como disponibles.
- El material historico debe ir bajo [docs/archive/](docs/archive/) o quedar
  claramente etiquetado como legacy/no canonico.

## Validacion minima antes de abrir PR

- Ejecuta `py -m unittest discover -s tests`.
- Ejecuta `py -m ruff check engine/api engine/project engine/rl engine/serialization engine/events cli tools main.py`.
- Ejecuta `py -m mypy engine/api engine/project engine/rl engine/serialization engine/events cli tools main.py`.
- Ejecuta `py -m bandit -q -c .bandit -r engine cli tools main.py`.
- Ejecuta `py -m pip_audit --skip-editable --ignore-vuln CVE-2026-4539`.
- Verifica manualmente cualquier flujo que hayas tocado en editor, CLI o API.
- Revisa que el README o la doc tecnica sigan siendo coherentes con el cambio.
