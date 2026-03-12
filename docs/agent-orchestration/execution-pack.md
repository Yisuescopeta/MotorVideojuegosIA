# Execution Pack para GPT-5.4 Medium

Este paquete pone la orquestacion en marcha de forma practica usando una sesion
de `GPT-5.4 medium` desde tu lado.

## Limitacion importante

Codex no puede quedarse ejecutando en segundo plano durante media hora despues
de cerrar este turno ni puede forzar el modelo exacto de la sesion activa.
Por eso este paquete deja todo listo para lanzar una sesion larga y bastante
autonoma, pero el disparo real de esa sesion lo haces tu.

## Objetivo de la sesion

Consumir una ventana larga de trabajo enfocada en `Unity 2D core` sin perder la
regla IA-first:

- el estado real vive en codigo o datos serializables
- la UI solo traduce ese modelo
- toda accion del usuario debe existir tambien por API o datos accesibles por IA

## Orden recomendado de ejecucion

1. Abrir una sesion con `GPT-5.4 medium`.
2. Pegar el prompt de `prompts/orchestrator-gpt5-medium.md`.
3. Indicarle que use los briefs del backlog en orden.
4. Dejarle ejecutar primero:
   - `001-entity-activation.md`
   - `002-tags-and-layers.md`
   - `003-camera-2d.md`
5. Cuando termine ese lote, pedirle que regenere backlog con `Feature Scout`.

## Briefs iniciales

- `backlog/001-entity-activation.md`
- `backlog/002-tags-and-layers.md`
- `backlog/003-camera-2d.md`

## Prompt base

- `prompts/orchestrator-gpt5-medium.md`
- `prompts/feature-scout-gpt5-medium.md`

## Criterio de corte para una sesion larga

La sesion debe parar si ocurre una de estas condiciones:

- aparecen 2 fallos seguidos en validacion del mismo subsistema
- hay riesgo de romper la regla IA-first
- el backlog entra en una dependencia bloqueante no resuelta
- se agota el tiempo o el presupuesto de la sesion

## Instruccion de autonomia

La sesion puede encadenar briefs del backlog mientras:

- el siguiente brief dependa de uno ya completado
- exista prueba no visual para validar
- no toque arquitectura mayor fuera del lote previsto

## Comandos utiles durante la sesion

```bash
py -3 tools/agent_workflow.py list-gaps --status parcial
py -3 -m unittest tests.test_agent_workflow tests.test_unity_core_authoring
py -3 tests/test_api_usage.py
```
