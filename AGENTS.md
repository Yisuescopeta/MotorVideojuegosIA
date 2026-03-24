# AGENTS

Reglas minimas del motor para cualquier agente que trabaje en este repo.

## Contrato Del Proyecto

- El motor es data-first e IA-first.
- La fuente de verdad vive en codigo y datos serializables del proyecto.
- La UI no es fuente de verdad y no debe introducir rutas exclusivas de mutacion.
- Runtime, editor, API y tooling deben operar sobre el mismo contrato.

## Criterios De Cambio

- No introduzcas dependencias de UI para flujos de servicio, API, CLI o tests.
- Reutiliza la CLI y tooling existentes antes de proponer comandos o pipelines nuevos.
- Mantiene `artifacts/` como salida y evidencia operativa.
- Mantiene `.motor/` como metadata local y build interno, no como fuente de verdad.

## Validacion Obligatoria

- Todo cambio debe cerrarse con validacion no visual cuando aplique.
- Para cambios de CLI, headless, scenes, datasets o runtime, usa tests, smoke o scripts reproducibles del repo.
- Si no puedes ejecutar una validacion relevante, indicalo explicitamente junto con el comando esperado.

## Documentacion Base

Lee y respeta estos documentos antes de cambios estructurales:

- `docs/architecture.md`
- `docs/cli.md`
- `docs/rl.md`
- `docs/opencode/architecture.md`
- `docs/opencode/security.md`
