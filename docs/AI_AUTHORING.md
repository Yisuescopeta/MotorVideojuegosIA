# IA integrada para authoring

El motor ahora incluye una base operativa en `engine.ai` para planificar y ejecutar cambios desde lenguaje natural sin tocar internals.

## Superficie pública

La entrada principal vive en `EngineAPI`:

```python
from engine.api import EngineAPI

api = EngineAPI()
api.load_level("levels/demo_level.json")

plan = api.handle_ai_request("Crea un juego de plataformas", mode="plan")
proposal = api.handle_ai_request(
    "Crea un juego de plataformas",
    answers={
        "enemies": "slime",
        "obstacles": "pinchos",
        "asset_strategy": "placeholders",
        "camera_style": "follow_platformer",
        "hud": "basic_hud",
    },
)
result = api.handle_ai_request(
    "Crea un juego de plataformas",
    answers={
        "enemies": "slime",
        "obstacles": "pinchos",
        "asset_strategy": "placeholders",
        "camera_style": "follow_platformer",
        "hud": "basic_hud",
    },
    confirmed=True,
)
```

## Qué incluye esta base

- Orquestador embebido con políticas de proveedor y mutación.
- Registro de capacidades del motor derivado de componentes, sistemas y proyecto activo.
- Skills versionadas en `engine/ai/skill_manifests/`.
- Memoria persistente del proyecto en `.motor/meta/ai_project_memory.json`.
- Modo plan especializado para plataformas.
- Propuestas de ejecución con confirmación previa.
- Validación estructural y ciclo `PLAY -> STOP`.
- Panel de asistente integrado en el editor, a la derecha del Inspector.
- Conector local real para Ollama con fallback al planificador determinista.

## Métodos nuevos en `EngineAPI`

- `handle_ai_request(...)`
- `get_ai_project_memory()`
- `update_ai_project_memory(...)`
- `list_ai_skills()`
- `list_ai_providers()`
- `get_engine_capabilities()`
- `get_ai_context(prompt)`
- `set_ai_provider_policy(...)`
- `get_ai_provider_diagnostics()`

## Cómo conectar una IA local al editor

La integración local de esta fase está preparada para `Ollama`.

### Opción 1: desde el editor

1. Abre el editor.
2. Mira el panel `AI Assistant` a la derecha del Inspector.
3. Pulsa `Ollama`.
4. Si Ollama está levantado en `http://127.0.0.1:11434`, el panel mostrará el proveedor seleccionado y los modelos detectados.
5. Escribe tu prompt y usa `Plan` o `Send`.

### Opción 2: desde código

```python
from engine.api import EngineAPI

api = EngineAPI()
api.set_ai_provider_policy(
    mode="local",
    preferred_provider="ollama_local",
    model_name="llama3.1:8b",
    endpoint="http://127.0.0.1:11434",
)
print(api.get_ai_provider_diagnostics())
```

### Comprobar que Ollama está listo

En PowerShell:

```powershell
ollama list
ollama serve
```

Si `ollama serve` ya está corriendo en segundo plano, no hace falta relanzarlo. Si tu modelo tiene otro nombre, úsalo en `model_name`.

### Dónde se guarda la configuración

La política activa queda persistida en:

- `.motor/meta/ai_project_memory.json`

Ahí puedes ajustar manualmente:

- `provider_policy.mode`
- `provider_policy.preferred_provider`
- `provider_policy.model_name`
- `provider_policy.endpoint`

## Limitaciones actuales

- El proveedor local usable hoy es `Ollama`; los demás conectores siguen como puertos preparados.
- Los cambios Python tienen guardarraíl y scaffold, pero todavía no un generador automático de scripts.
