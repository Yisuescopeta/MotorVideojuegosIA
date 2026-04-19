# Guia para agentes IA

Esta guia resume como orientarse sin mezclar material historico con contratos
vigentes. Para reglas operativas completas, lee [../AGENTS.md](../AGENTS.md).

## Primeros 5 minutos

1. Lee [README.md](README.md) para ubicar canon, referencia, tooling y archivo.
2. Lee [glossary.md](glossary.md) si algun termino del repo no es obvio.
3. Lee [../AGENTS.md](../AGENTS.md) antes de tocar archivos o elegir perimetro.
4. Usa [api.md](api.md) o [cli.md](cli.md) para flujos publicos.
5. Revisa [documentation_governance.md](documentation_governance.md) si el cambio
   crea, mueve o actualiza documentacion.

## Fuentes de verdad

Orden de autoridad:

1. Codigo y tests.
2. `EngineAPI` publica en `engine/api/`.
3. CLI oficial `motor` en `motor/cli.py`.
4. Docs canonicos en [README.md](README.md), [architecture.md](architecture.md),
   [TECHNICAL.md](TECHNICAL.md), [schema_serialization.md](schema_serialization.md),
   [module_taxonomy.md](module_taxonomy.md), [api.md](api.md) y [cli.md](cli.md).
5. Archivo historico en [archive/](archive/) solo como contexto.

No uses roadmaps, prompts antiguos, research ni capabilities `planned` como
prueba de funcionalidad actual.

## Invariantes que no debes romper

- `Scene` es la fuente persistente de verdad.
- `World` es una proyeccion operativa.
- Las mutaciones runtime no deben convertirse en authoring state por accidente.
- Cambios serializables compartidos deben pasar por `SceneManager` o `EngineAPI`.
- `EngineAPI` es la fachada publica para agentes, tests, CLI y automatizacion.
- `legacy_aabb` debe seguir funcionando como fallback fisico.
- Componentes publicos nuevos deben registrarse en `engine/levels/component_registry.py`.

## Como hacer cambios de authoring

Ruta recomendada:

```python
from engine.api import EngineAPI

api = EngineAPI(project_root=".")
try:
    api.load_scene("levels/main_scene.json")
    api.create_entity("Player", components={"Transform": {"x": 0, "y": 0}})
    api.add_component("Player", "Sprite", {"asset_path": "assets/player.png"})
    api.save_scene()
finally:
    api.shutdown()
```

## Agente nativo experimental

El repo incluye una base clean-room en `engine/agent/` para un agente de
asistencia integrado. Usalo como `experimental/tooling`, no como contrato core.

- Crea sesiones con `EngineAPI.create_agent_session`.
- Envia mensajes con `EngineAPI.send_agent_message`.
- Aprueba acciones pendientes con `EngineAPI.approve_agent_action`.
- Las mutaciones de escenas deben pasar por herramientas que usan `EngineAPI` o
  `AuthoringExecutionService`.
- No incluyas la carpeta local `Claude Code/` como contexto del agente.

Para CLI:

```bash
py -m motor doctor --project . --json
py -m motor scene create "Level 1" --project . --json
py -m motor entity create Player --project . --json
py -m motor component add Player Transform --data '{"x":0,"y":0}' --project . --json
```

Para UI serializable usa los helpers publicos de `EngineAPI` como
`create_canvas`, `create_ui_text`, `create_ui_button` y `create_ui_image`.

## Que evitar

- No editar `SceneManager.edit_world` directamente para flujos publicos nuevos.
- No asumir soporte de componentes no registrados.
- No documentar capacidades planificadas como implementadas.
- No ejecutar comandos listados como `planned` en `motor_ai.json` o
  `motor capabilities --json` si no existen en `motor/cli.py`.
- No reemplazar `motor` por `tools/engine_cli.py` en docs nuevas.
- No mover material desde `docs/archive/` a docs canonicas sin verificar codigo y tests.
- No tocar archivos congelados de [../AGENTS.md](../AGENTS.md) sin justificarlo.

## Documentos por necesidad

- Quiero entender el sistema: [architecture.md](architecture.md).
- Quiero entender terminos del repo: [glossary.md](glossary.md).
- Quiero saber que es core y que es experimental: [module_taxonomy.md](module_taxonomy.md).
- Quiero cambiar escenas/prefabs: [schema_serialization.md](schema_serialization.md).
- Quiero automatizar por Python: [api.md](api.md).
- Quiero automatizar por CLI: [cli.md](cli.md).
- Quiero entender `motor_ai.json`: [MOTOR_AI_JSON_CONTRACT.md](MOTOR_AI_JSON_CONTRACT.md).
- Quiero cambiar documentacion: [documentation_governance.md](documentation_governance.md).
- Quiero contexto historico: [archive/](archive/).

## Checks minimos antes de entregar docs o contratos

```bash
py -m unittest tests.test_repository_governance tests.test_motor_cli_contract tests.test_start_here_ai_coherence -v
py -m unittest tests.test_official_contract_regression tests.test_parser_registry_alignment tests.test_motor_interface_coherence tests.test_motor_registry_consistency -v
py -m motor --help
py -m motor doctor --project . --json
```

Declara solo los comandos que hayas ejecutado realmente.
