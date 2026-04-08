# Contrato Portable de motor_ai.json

**Versión:** 2026.03  
**Fecha:** 2025-01-21  
**Estado:** ESTABLE

## Resumen

El archivo `motor_ai.json` es el contrato AI-facing del proyecto MotorVideojuegosIA. Este documento especifica el formato portable que permite a una IA descubrir y operar sobre el proyecto sin información dependiente de la máquina.

## Principios de Portabilidad

1. **Rutas relativas**: Todas las rutas son relativas al root del proyecto
2. **Sin rutas absolutas**: No Windows (`C:\`), no Unix (`/home/`), no network (`\\`)
3. **Commit-friendly**: El archivo puede ser versionado sin contaminar con datos locales
4. **AI-discoverable**: Contiene toda la información necesaria para IA

## Estructura del Archivo

```json
{
  "schema_version": 2,
  "engine": {
    "name": "MotorVideojuegosIA",
    "version": "2026.03",
    "api_version": "1",
    "capabilities_schema_version": 1
  },
  "project": {
    "name": "MyGame",
    "root": ".",
    "engine_version": "2026.03",
    "template": "empty",
    "paths": {
      "assets": "assets",
      "levels": "levels",
      "prefabs": "prefabs",
      "scripts": "scripts",
      "settings": "settings",
      "meta": ".motor/meta",
      "build": ".motor/build"
    }
  },
  "entrypoints": {
    "manifest": "project.json",
    "settings": "settings/project_settings.json",
    "startup_scene": "levels/main_scene.json",
    "scripts_dir": "scripts",
    "assets_dir": "assets",
    "levels_dir": "levels",
    "prefabs_dir": "prefabs"
  },
  "important_files": [
    "project.json",
    "motor_ai.json",
    "START_HERE_AI.md"
  ],
  "capabilities": {
    "schema_version": 1,
    "engine": {
      "name": "MotorVideojuegosIA",
      "version": "2026.03"
    },
    "capabilities": [...]
  }
}
```

## Secciones

### `schema_version`
Versión del formato de motor_ai.json. Actualmente `2`.

### `engine`
Información del motor:
- `name`: Nombre del motor ("MotorVideojuegosIA")
- `version`: Versión del motor ("2026.03")
- `api_version`: Versión de la API ("1")
- `capabilities_schema_version`: Versión del schema de capabilities

### `project`
Información del proyecto:
- `name`: Nombre del proyecto
- `root`: Siempre `"."` (relativo al directorio del proyecto)
- `engine_version`: Versión del motor usada por el proyecto
- `template`: Template usado para crear el proyecto
- `paths`: Rutas canónicas de carpetas del proyecto (todas relativas)

### `entrypoints`
Puntos de entrada clave para la IA:
- `manifest`: Archivo de manifiesto del proyecto ("project.json")
- `settings`: Archivo de configuración ("settings/project_settings.json")
- `startup_scene`: Escena de inicio ("levels/main_scene.json")
- `scripts_dir`: Directorio de scripts ("scripts")
- `assets_dir`: Directorio de assets ("assets")
- `levels_dir`: Directorio de niveles ("levels")
- `prefabs_dir`: Directorio de prefabs ("prefabs")

Todas las rutas son **relativas al root del proyecto**.

### `important_files`
Lista de archivos importantes que la IA debe conocer:
- `project.json`: Manifiesto del proyecto
- `motor_ai.json`: Este archivo (capability registry)
- `START_HERE_AI.md`: Guía de inicio rápido

### `capabilities`
Registry completo de capabilities del motor. Ver documentación de capabilities.

## Para Desarrolladores IA

### Descubrimiento del Proyecto

Al abrir una carpeta de proyecto, la IA debe:

1. Verificar que existe `motor_ai.json`
2. Leer `project.name` para identificar el proyecto
3. Usar `entrypoints` para localizar archivos clave
4. Usar `project.paths` para navegar la estructura

### Ejemplo de Uso

```python
import json
from pathlib import Path

# IA abre la carpeta del proyecto
project_root = Path("./MyGame")

# Carga motor_ai.json
motor_ai = json.loads((project_root / "motor_ai.json").read_text())

# Descubre estructura
project_name = motor_ai["project"]["name"]
assets_dir = project_root / motor_ai["entrypoints"]["assets_dir"]
manifest_path = project_root / motor_ai["entrypoints"]["manifest"]

# Lista capabilities disponibles
for cap in motor_ai["capabilities"]["capabilities"]:
    print(f"- {cap['id']}: {cap['summary']}")
```

## Reglas de Generación

### Código de Generación

El archivo se genera mediante `MotorAIBootstrapBuilder`:

```python
from engine.ai import get_default_registry, MotorAIBootstrapBuilder
from engine.project.project_service import ProjectService

registry = get_default_registry()
builder = MotorAIBootstrapBuilder(registry)

project_data = {
    "project": {
        "name": "MyGame",
        "root": ".",  # SIEMPRE relativo
        "paths": {...},  # Rutas canónicas
    },
    "entrypoints": {
        "manifest": "project.json",  # Relativo
        "assets_dir": "assets",  # Relativo
        # ... etc
    },
    "important_files": [
        "project.json",
        "motor_ai.json",
        "START_HERE_AI.md",
    ],
}

builder.write_to_project(project_root, project_data)
```

### Verificación de Portabilidad

Ejecutar tests antes de commits:

```bash
python -m unittest tests.test_bootstrap_portability -v
```

Tests que verifican:
- ❌ No rutas absolutas Windows (`C:\`)
- ❌ No rutas absolutas Unix (`/home/`, `/Users/`)
- ❌ No rutas de red (`\\server\`)
- ✅ Todas las rutas relativas al proyecto
- ✅ AI-discoverable

## Historial de Cambios

### v2 (2025-01-21)
- **Cambio**: Eliminadas rutas absolutas del sistema
- **Cambio**: `project.root` ahora es `"."` en lugar de ruta absoluta
- **Cambio**: `entrypoints.*` ahora son rutas relativas
- **Añadido**: Sección `important_files`
- **Añadido**: Campo `project.paths` con rutas canónicas
- **Motivación**: Portabilidad y commit-friendly

### v1 (Versión anterior)
- Contenía rutas absolutas del sistema de archivos
- No era portable entre máquinas
- No era adecuado para versionado

## Referencias

- `engine/ai/registry_builder.py`: Generador del archivo
- `engine/project/project_service.py`: Integración con proyecto
- `tests/test_bootstrap_portability.py`: Tests de portabilidad
