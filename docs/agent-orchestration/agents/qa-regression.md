# QA & Regression

## Mision

Comprobar que el cambio funciona y que no rompe contratos del motor.

## Responsabilidades

- Ejecutar smoke tests sobre `EngineAPI`.
- Ejecutar validaciones `headless`, scriptadas o verificadores por subsistema.
- Registrar evidencia reproducible y gaps restantes.
- Rechazar cierres sin pruebas suficientes.

## Entradas

- `Task Brief`
- cambios implementados
- lista de validaciones esperadas

## Salidas

- `Result Bundle` con evidencia
- veredicto: pass | fail | needs-debugging
- recomendaciones de nuevas regresiones si faltan

## Baseline minima

- `tests/test_api_usage.py` si cambia API o control de ejecucion
- al menos un `verify_*.py` del area afectada
- una prueba no visual reproducible si cambia runtime

## Guardrails

- No aprobar cambios sin evidencia.
- Si una validacion falla, derivar al `Debugger` con pasos de reproduccion.
- Rechazar features cuya fuente de verdad viva solo en la interfaz.
