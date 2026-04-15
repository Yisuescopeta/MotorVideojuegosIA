# Diseño Técnico: motor doctor Read-Only

**Versión:** 2026.03  
**Fecha:** 2025-01-21  
**Estado:** IMPLEMENTADO

## Problema

El comando `motor doctor` inicializaba `EngineAPI`, que a su vez inicializaba `ProjectService` con `auto_ensure=True` (valor por defecto). Esto causaba efectos secundarios no deseados:

1. **Creación de directorios** - `ensure_project()` creaba directorios faltantes
2. **Generación de bootstrap** - Creaba `motor_ai.json` y `START_HERE_AI.md`
3. **Registro de recientes** - Agregaba el proyecto a la lista de recientes
4. **Modificación de archivos** - Creaba/sobrescribía archivos de configuración

Esto violaba el principio de que un diagnóstico debe ser **read-only**.

## Solución

### Arquitectura Read-Only

Se implementó una ruta de inicialización explícitamente read-only mediante el parámetro `auto_ensure_project`:

```
motor doctor
  └─> cmd_doctor(project_path, auto_ensure_project=False)
        └─> _init_engine(project_path, auto_ensure_project=False)
              └─> EngineAPI(auto_ensure_project=False)
                    └─> ProjectService(auto_ensure=False)
```

### Cambios Realizados

#### 1. EngineAPI (`engine/api/engine_api.py`)

```python
def __init__(
    self,
    project_root: str | None = None,
    global_state_dir: str | None = None,
    sandbox_paths: bool = False,
    auto_ensure_project: bool = True,  # NUEVO
) -> None:
    # ...
    self.project_service = ProjectService(
        self._project_root,
        global_state_dir=self._global_state_dir,
        auto_ensure=self._auto_ensure_project  # NUEVO
    )
```

#### 2. cli_core.py (`motor/cli_core.py`)

```python
def _init_engine(project_path: Path, auto_ensure_project: bool = True) -> EngineAPI:
    return EngineAPI(
        project_root=str(project_path),
        sandbox_paths=False,
        auto_ensure_project=auto_ensure_project,  # NUEVO
    )

def cmd_doctor(project_path: Path, json_output: bool) -> int:
    # ...
    # Check 6: Try to init engine (read-only mode - no side effects)
    api = _init_engine(project_path, auto_ensure_project=False)  # CAMBIO
```

## Comportamiento

### Antes (con side effects)

```bash
$ motor doctor --project .
# Silenciosamente:
# - Crea directorios faltantes
# - Genera motor_ai.json
# - Genera START_HERE_AI.md
# - Registra proyecto en recientes
```

### Después (read-only)

```bash
$ motor doctor --project .
# Solo diagnostica:
# - Valida project.json
# - Verifica existencia de motor_ai.json (sin crearlo)
# - Verifica estructura canónica
# - Reporta recomendaciones (ej: "Run 'motor project bootstrap-ai'")
```

## Tests de Verificación

**`tests/test_doctor_read_only.py`** - 6 tests críticos:

| Test | Verificación |
|------|--------------|
| `test_doctor_does_not_create_directories` | No crea directorios |
| `test_doctor_does_not_create_motor_ai_json` | No crea motor_ai.json |
| `test_doctor_does_not_create_start_here_md` | No crea START_HERE_AI.md |
| `test_doctor_does_not_modify_existing_files` | No modifica archivos |
| `test_doctor_reports_missing_bootstrap_correctly` | Reporta sin crear |
| `test_doctor_multiple_runs_idempotent` | Múltiples ejecuciones son idempotentes |

### Ejemplo de Test

```python
def test_doctor_does_not_create_motor_ai_json(self):
    # Setup: Proyecto sin motor_ai.json
    project = create_minimal_project()
    assert not (project / "motor_ai.json").exists()
    
    # Action: Ejecutar doctor
    run_motor("doctor", "--project", str(project))
    
    # Assert: motor_ai.json NO debe existir
    assert not (project / "motor_ai.json").exists(), \
        "doctor must NOT create motor_ai.json"
```

## Diagnóstico Mantenido

A pesar de ser read-only, `motor doctor` mantiene su valor diagnóstico:

### Checks Realizados

1. **project.json** - Existencia y validez JSON
2. **motor_ai.json** - Existencia y esquema (sin crear)
3. **START_HERE_AI.md** - Existencia (sin crear)
4. **Estructura canónica** - Directorios requeridos (sin crear)
5. **Entrypoints** - Disponibilidad de rutas clave
6. **Engine** - Capacidad de inicialización (sin side effects)
7. **Escenas** - Capacidad de listar escenas
8. **Assets** - Capacidad de listar assets
9. **Registry** - Consistencia del capability registry

### Recomendaciones Accionables

Cuando detecta problemas, recomienda comandos específicos:

```json
{
  "warnings": ["motor_ai.json not found"],
  "recommendations": [
    "Run 'motor project bootstrap-ai --project .' to generate AI bootstrap files"
  ]
}
```

## Backward Compatibility

Otros comandos mantienen el comportamiento anterior:

- `motor scene create` - Usa `auto_ensure_project=True` (default)
- `motor entity create` - Usa `auto_ensure_project=True` (default)
- `motor project bootstrap-ai` - Usa `auto_ensure_project=True` explícitamente

Solo `motor doctor` usa `auto_ensure_project=False`.

## Referencias

- `engine/api/engine_api.py` - Parámetro `auto_ensure_project`
- `motor/cli_core.py` - `_init_engine()` y `cmd_doctor()`
- `engine/project/project_service.py` - `auto_ensure` parameter
- `tests/test_doctor_read_only.py` - Tests de verificación
