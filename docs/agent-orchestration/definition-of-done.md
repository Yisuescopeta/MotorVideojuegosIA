# Definition of Done

Una tarea multiagente solo puede cerrarse cuando cumple todos los puntos:

- El comportamiento solicitado ha sido implementado o investigado de forma
  verificable.
- Existe al menos una evidencia reproducible no visual cuando la tarea afecta
  runtime, API, escenas o automatizacion.
- No se rompen los checks base del proyecto aplicables al subsistema tocado.
- Los riesgos, limites y follow-ups quedan registrados en el `Result Bundle`.
- Si cambia una interfaz publica, flujo operativo o restriccion importante, la
  documentacion minima queda actualizada.
- La funcionalidad respeta la regla IA-first:
  - no existe estado funcional exclusivo de UI
  - la misma accion puede ejecutarse por API o datos serializables
- El orquestador valida que el handoff final incluye:
  - resumen
  - evidencia
  - riesgos
  - siguiente paso o cierre

## Baseline de validacion actual

- `python tests/test_api_usage.py`
- `python verify_scene_manager.py`
- `python verify_serialization.py`
- `python verify_prefabs.py`
- verificadores `verify_*.py` adicionales segun el area tocada
- ejecucion `headless` o `ScriptExecutor` si la tarea cambia control o flujo de
  simulacion

## Reglas de cierre

- `Core Implementer` nunca declara cierre definitivo.
- `QA & Regression` solo aprueba cuando hay evidencia reproducible.
- `Debugger` solo sale del flujo cuando la causa raiz ha sido identificada.
- `Docs & Contracts` no sustituye pruebas; solo consolida el conocimiento.
