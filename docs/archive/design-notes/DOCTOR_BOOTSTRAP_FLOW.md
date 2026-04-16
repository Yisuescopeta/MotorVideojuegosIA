# Flujo Oficial: Diagnóstico y Bootstrap AI

**Versión:** 2026.03  
**Fecha:** 2025-01-21  
**Estado:** ESTABLE

## Resumen

MotorVideojuegosIA proporciona dos comandos oficiales para diagnóstico y configuración AI-facing:

1. **`motor doctor`** - Diagnóstico read-only del proyecto
2. **`motor project bootstrap-ai`** - Generación/regeneración de archivos AI

## Flujo de Trabajo Oficial

### Paso 1: Diagnóstico Inicial

Cuando una IA (o desarrollador) abre un proyecto por primera vez:

```bash
$ motor doctor --project . --json
{
  "success": true,
  "message": "Project is degraded (2 warnings)",
  "data": {
    "healthy": false,
    "status": "degraded",
    "checks": {
      "project_manifest_exists": true,
      "project_manifest_valid": true,
      "motor_ai_exists": false,
      "start_here_exists": false,
      ...
    },
    "warnings": [
      "motor_ai.json not found (run project migration)",
      "START_HERE_AI.md not found (run project migration)"
    ],
    "recommendations": [
      "Run 'motor project bootstrap-ai --project .' to generate AI bootstrap files"
    ]
  }
}
```

**Características de `doctor`:**
- ✅ **Read-only**: No modifica archivos del proyecto
- ✅ **No muta estado**: No crea estructuras ni registra proyectos
- ✅ **Diagnóstico completo**: Verifica manifiesto, archivos AI, directorios, engine
- ✅ **Recomendaciones accionables**: Sugiere comandos reales y ejecutables

### Paso 2: Generar Bootstrap AI

Siguiendo la recomendación de `doctor`:

```bash
$ motor project bootstrap-ai --project . --json
{
  "success": true,
  "message": "AI bootstrap files generated:\n  - motor_ai.json\n  - START_HERE_AI.md",
  "data": {
    "motor_ai_json": "motor_ai.json",
    "start_here_md": "START_HERE_AI.md",
    "registry_capabilities_count": 42
  }
}
```

**Características de `bootstrap-ai`:**
- ✅ **Genera archivos portables**: Usa rutas relativas, commit-friendly
- ✅ **Idempotente**: Puede ejecutarse múltiples veces
- ✅ **Lee project.json**: Extrae nombre, versión, rutas canónicas
- ✅ **Usa MotorAIBootstrapBuilder**: Consistente con el registry

### Paso 3: Verificación

Ejecutar `doctor` nuevamente confirma que todo está correcto:

```bash
$ motor doctor --project . --json
{
  "success": true,
  "message": "Project is healthy",
  "data": {
    "healthy": true,
    "status": "healthy",
    "checks": {
      "motor_ai_exists": true,
      "start_here_exists": true,
      "motor_ai_valid": true,
      ...
    },
    "warnings": [],
    "recommendations": []
  }
}
```

## Comandos Oficiales

### `motor doctor`

```
usage: motor doctor [-h] [--project PROJECT_ROOT] [--json]

Validate project structure, bootstrap files, and engine availability.

options:
  -h, --help            show this help message and exit
  --project PROJECT_ROOT
                        Path to project directory (default: current directory)
  --json                Output in JSON format
```

**Checks realizados:**
1. `project.json` existe y es JSON válido
2. `motor_ai.json` existe y es válido
3. `START_HERE_AI.md` existe
4. Directorios requeridos (`assets/`, `levels/`, `scripts/`, `settings/`)
5. Entrypoints disponibles
6. Engine puede inicializarse
7. Puede listar escenas y assets
8. Capability registry carga correctamente

**Recomendaciones automáticas:**
- Faltan archivos AI → "Run 'motor project bootstrap-ai --project .'..."
- Proyecto funcional con warnings → "Project is functional but has minor configuration issues"

### `motor project bootstrap-ai`

```
usage: motor project bootstrap-ai [-h] [--project PROJECT_ROOT] [--json]

Generate or regenerate AI-facing bootstrap files for the project.

options:
  -h, --help            show this help message and exit
  --project PROJECT_ROOT
                        Path to project directory (default: current directory)
  --json                Output in JSON format
```

**Archivos generados:**
- `motor_ai.json` - Capability registry completo con metadatos del proyecto
- `START_HERE_AI.md` - Guía de inicio rápido para IA

**Formato portable:**
- `project.root`: "." (relativo)
- `entrypoints.*`: Rutas relativas al proyecto
- Sin rutas absolutas del sistema
- Commit-friendly

## Tests del Flujo

La suite de tests valida el flujo completo:

```bash
# Ejecutar tests del flujo doctor → bootstrap-ai
python -m unittest tests.test_doctor_bootstrap_flow -v
```

**Tests incluidos:**

1. **`test_doctor_detects_missing_bootstrap_files`**
   - Doctor detecta ausencia de motor_ai.json y START_HERE_AI.md
   - Recomienda `motor project bootstrap-ai`

2. **`test_bootstrap_ai_generates_files`**
   - Bootstrap-ai crea ambos archivos
   - motor_ai.json usa rutas relativas

3. **`test_doctor_recognizes_bootstrap_after_generation`**
   - Doctor posterior encuentra los archivos
   - No hay warnings sobre bootstrap faltante

4. **`test_bootstrap_ai_is_idempotent`**
   - Ejecutar bootstrap-ai dos veces funciona
   - Archivos se regeneran correctamente

5. **`test_doctor_is_read_only`**
   - Doctor no modifica project.json
   - Doctor no crea archivos AI
   - Doctor es estrictamente diagnóstico

6. **`test_bootstrap_ai_fails_without_project`**
   - Bootstrap-ai falla gracefulmente sin project.json
   - Reporta error apropiado

## Ejemplo Completo

```bash
# 1. Crear nuevo proyecto (o abrir existente)
cd MyGame

# 2. Verificar estado
$ motor doctor --project .
Project is degraded (2 warnings)
Warnings:
  - motor_ai.json not found (run project migration)
  - START_HERE_AI.md not found (run project migration)
Recommendation:
  Run 'motor project bootstrap-ai --project .' to generate AI bootstrap files

# 3. Generar bootstrap AI
$ motor project bootstrap-ai --project .
AI bootstrap files generated:
  - motor_ai.json
  - START_HERE_AI.md

# 4. Verificar que todo está correcto
$ motor doctor --project .
Project is healthy

# 5. AI puede ahora usar motor_ai.json para descubrir capabilities
$ cat motor_ai.json | jq '.capabilities.capabilities | length'
42
```

## Para Desarrolladores IA

### Descubrimiento del Proyecto

```python
import json
import subprocess

# 1. Diagnóstico
result = subprocess.run(
    ["motor", "doctor", "--project", ".", "--json"],
    capture_output=True, text=True
)
doctor_report = json.loads(result.stdout)

if not doctor_report["data"]["healthy"]:
    if not doctor_report["data"]["checks"]["motor_ai_exists"]:
        # 2. Generar bootstrap
        subprocess.run(["motor", "project", "bootstrap-ai", "--project", "."])

# 3. Cargar capabilities
motor_ai = json.loads(open("motor_ai.json").read())
capabilities = motor_ai["capabilities"]["capabilities"]
```

### Uso Programático

```python
from motor.cli import run_motor_command

# Diagnóstico
exit_code = run_motor_command(["doctor", "--project", ".", "--json"])

# Bootstrap
exit_code = run_motor_command(["project", "bootstrap-ai", "--project", "."])
```

## Referencias

- `motor/cli_core.py`: Implementaciones de `cmd_doctor` y `cmd_project_bootstrap_ai`
- `tests/test_doctor_bootstrap_flow.py`: Tests de integración del flujo
- `docs/MOTOR_AI_JSON_CONTRACT.md`: Especificación de motor_ai.json
- `engine/project/project_service.py`: Integración con ProjectService
