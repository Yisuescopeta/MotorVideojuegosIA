# Contributing

## Objetivo

Este repositorio sigue un enfoque incremental. Los cambios deben mantenerse
acotados, revisables y alineados con el comportamiento observable del motor.

## Setup local

```bash
pip install -r requirements.txt
pip install -e .[dev]
python -m unittest discover -s tests
```

## Reglas de trabajo

- Mantén cada cambio enfocado en una fase o problema concreto.
- Si cambias comportamiento observable, actualiza tests y documentación en la
  misma propuesta.
- No introduzcas nuevas dependencias a internals privados del motor fuera del
  core (`engine/core`, `engine/app`, `engine/systems`, `engine/events`).
- Evita mezclar refactors amplios con fixes funcionales pequeños.

## Estilo de contribución

- Prefiere cambios pequeños con mensajes de commit claros.
- Si tocas CLI, API o contratos serializados, documenta el impacto en el PR.
- Si añades una funcionalidad experimental, deja explícito su alcance y límites.

## Validación mínima antes de abrir PR

- Ejecuta `python -m unittest discover -s tests`.
- Ejecuta `python -m ruff check engine/api engine/project engine/rl engine/serialization engine/events cli tools main.py`.
- Ejecuta `python -m mypy engine/api engine/project engine/rl engine/serialization engine/events cli tools main.py`.
- Ejecuta `python -m bandit -q -c .bandit -r engine cli tools main.py`.
- Ejecuta `python -m pip_audit --skip-editable --ignore-vuln CVE-2026-4539`.
- Verifica manualmente cualquier flujo que hayas tocado en editor, CLI o API.
- Revisa que el README o la doc técnica sigan siendo coherentes con el cambio.
