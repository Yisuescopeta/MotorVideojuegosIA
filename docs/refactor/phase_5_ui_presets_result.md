# Resultado de fase

## Objetivo

Agregar presets UI serializables a la CLI oficial `motor` y a `UIAPI` sin
escribir JSON manual ni tocar internals de `World` o `Scene`.

## Estado inicial

- Rama base remota detectada: `origin/main`
- Branch de trabajo observado: `codex/runtime-input-picking`
- Suites de contrato/coherencia/registry para `motor` verificadas antes del cambio
- `mobile controls add` ya existia como patron oficial para `--scene`,
  `--replace`, uso de `EngineAPI` y guardado condicional

## Archivos inspeccionados

- `motor/cli.py`
- `motor/cli_core.py`
- `engine/api/_ui_api.py`
- `engine/ai/registry_builder.py`
- `tests/test_motor_cli_contract.py`
- `tests/test_motor_interface_coherence.py`
- `tests/test_motor_registry_consistency.py`
- `tests/test_mobile_controls.py`
- `tests/test_ui_canvas_system.py`

## Cambios realizados

- Se creo `engine/ui/presets.py` con cinco presets puros y deterministas:
  `hud-platformer`, `main-menu`, `pause-menu`, `game-over` y `dialog-box`.
- Se extendio `UIAPI` con `list_ui_presets()` y `create_ui_preset()`.
- `create_ui_preset()` usa transaccion publica y en modo `replace` elimina el
  arbol previo por API publica, de hojas a raiz, para evitar hijos huerfanos.
- Se anadieron comandos oficiales:
  - `motor ui preset list`
  - `motor ui preset add <preset_id>`
- Se registraron capabilities:
  - `ui:preset:list`
  - `ui:preset:add`
- Se actualizaron `README.md`, `docs/cli.md` y `docs/api.md`.
- Se anadieron tests especificos de modulo puro, API y CLI.

## Cambios descartados

- No se toco `tools/engine_cli.py`.
- No se escribio JSON de escena manualmente desde CLI.
- No se modifico `engine/api/engine_api.py`; la delegacion dinamica actual fue suficiente.
- No se anadieron assets UI ni runtime paralelo para los presets MVP.

## Tests ejecutados

- `py -m unittest tests.test_ui_presets tests.test_ui_preset_api tests.test_motor_cli_ui_presets -v`
  - Resultado: passed.
- `py -m unittest tests.test_ui_canvas_system tests.test_mobile_controls tests.test_engine_api_facade_smoke tests.test_authoring_transactions -v`
  - Resultado: passed.
- `py -m unittest tests.test_motor_cli_contract tests.test_motor_interface_coherence tests.test_motor_registry_consistency -v`
  - Resultado: passed.

## Benchmarks ejecutados

- No aplica benchmark nuevo: cambio de authoring/CLI y contrato API, no hotspot de rendimiento.
- Se reutilizo validacion funcional y de contrato en lugar de optimizacion.

## Riesgos detectados

- `replace` depende de nombres raiz estables por preset; si se cambia ese
  contrato, hay que ajustar deteccion y regeneracion.
- Los presets MVP son estructurales; no incluyen skin visual ni assets.
- `dialog-box`, `pause-menu` y `game-over` nacen desactivados; requieren wiring
  de gameplay/UI por proyecto para mostrarse en runtime.

## Rollback

Revertir:

- `engine/ui/presets.py`
- cambios en `engine/api/_ui_api.py`
- cambios en `motor/cli.py`
- cambios en `motor/cli_core.py`
- cambios en `engine/ai/registry_builder.py`
- tests y docs asociados

Si aparecen regresiones, volver a comandos UI atomicos previos (`create-canvas`,
`create-text`, `create-button`, `create-image`) y retirar las dos capabilities nuevas.

## Decisión

Mantener. Contrato CLI/API nuevo validado y alineado con parser, registry y serializacion existente.

## Siguiente recomendación

Si la siguiente fase quiere presets mas ricos, anadir assets opcionales o un
builder declarativo comun sin romper el contrato de nombres estables y
transaccion publica.
