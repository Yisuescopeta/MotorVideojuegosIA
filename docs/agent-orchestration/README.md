# Orquestacion Multiagente

Esta carpeta define la primera capa operativa para trabajar con varios agentes
sobre el motor 2D IA-First.

## Objetivo

Convertir ideas o incidencias en trabajo ejecutable, verificable y trazable
sin depender de contexto informal entre agentes.

## Modelo de trabajo

- Un unico `Agente Orquestador` recibe la tarea, decide el flujo y valida los
  handoffs.
- Cinco agentes operativos trabajan bajo contrato:
  - `Feature Scout`
  - `Core Architect`
  - `Core Implementer`
  - `QA & Regression`
  - `Debugger`
  - `Docs & Contracts`
- Las entradas tecnicas oficiales del sistema son:
  - `engine.api.EngineAPI`
  - `cli/runner.py` y `cli/headless_game.py`
  - `cli/script_executor.py`
  - `tests/test_api_usage.py`
  - scripts `verify_*.py`

## Artefactos principales

- `task-brief-template.md`: contrato minimo que el orquestador entrega.
- `result-bundle-template.md`: salida estandar que cualquier agente devuelve.
- `definition-of-done.md`: criterio comun de cierre.
- `agents/`: especificacion operativa de cada agente.
- `unity-2d-core-matrix.md`: matriz base de gaps para el scout.
- `registro-automatizacion-unity.md`: memoria editable para sesiones
  automatizadas recurrentes.

## Regla global IA-first

Ningun agente puede introducir funcionalidades cuya fuente de verdad viva solo
en la interfaz o en estado no serializable; toda accion posible en la UI debe
existir tambien como codigo o datos accesibles por IA mediante API.

## Flujo recomendado

1. El orquestador crea un `Task Brief`.
2. `Feature Scout` detecta gaps y propone briefs listos para el orquestador.
3. `Core Architect` revisa alcance y riesgos si la tarea toca arquitectura,
   API, serializacion, runtime o escenas.
4. `Core Implementer` ejecuta la tarea con validaciones ya definidas.
5. `QA & Regression` ejecuta checks no visuales y regresiones del subsistema.
6. `Debugger` entra si aparece un fallo o una regresion.
7. `Docs & Contracts` registra cambios en contratos, limites o capacidades.
8. El orquestador valida la evidencia y declara cierre.

## Modos de ejecucion

- `Secuencial`: por defecto para cambios de runtime, ECS, escenas o API.
- `Paralelo`: solo si las tareas no comparten archivos criticos, contrato
  publico o superficie de validacion.

## Automatizacion inicial

La utilidad `tools/agent_workflow.py` ayuda a:

- generar un `Task Brief` inicial
- recomendar agentes implicados
- sugerir validaciones segun subsistemas afectados

Ejemplo:

```bash
python tools/agent_workflow.py create-brief ^
  --title "Corregir restauracion al hacer stop" ^
  --goal "Asegurar que STOP restaure el World original tras PLAY" ^
  --subsystems scenes core api ^
  --files engine/scenes/scene_manager.py engine/core/game.py engine/api/engine_api.py
```

## Automatizacion horaria orientada a Unity

Si quieres usar siempre el mismo prompt en una automatizacion recurrente:

- usa `prompts/hourly-unity-automation.md` como prompt base
- usa `registro-automatizacion-unity.md` como memoria editable de trabajo

La idea es que el prompt permanezca estable y que el control fino del flujo se
haga editando el registro.
