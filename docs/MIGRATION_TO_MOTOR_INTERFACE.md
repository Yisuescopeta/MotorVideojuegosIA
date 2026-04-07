# Migración a Interfaz Oficial `motor`

**Fecha:** 2025-01-21  
**Estado:** COMPLETADA

## Resumen

Todos los ejemplos y documentación AI-facing han sido migrados para usar la interfaz oficial `motor` en lugar de la interfaz legacy `python -m tools.engine_cli`.

## Cambios Realizados

### 1. Ejemplos Actualizados

| Archivo | Cambios |
|---------|---------|
| `01_query_capabilities.py` | Ya usaba `motor` ✓ |
| `02_slice_spritesheet.py` | Actualizado `upsert-state` → `state create` |
| `03_create_animated_entity.py` | Ya usaba `animator state create` ✓ |
| `README.md` | Actualizado `upsert-state` → `state create` en todos los ejemplos |

### 2. Tests Anti-Regresión

Se creó `tests/test_examples_interface.py` con tests que fallarán si:
- Se usa `tools.engine_cli` fuera de contexto de deprecación
- Se usan comandos legacy como `animator upsert-state` en ejemplos
- Los ejemplos no configuran PYTHONPATH apropiadamente

## Interfaz Oficial

### Comando
```bash
motor <comando> [opciones]
```

### Ejemplos
```bash
# Diagnóstico
motor doctor --project .

# Capabilities
motor capabilities

# Escenas
motor scene create "Level 1" --project .
motor entity create Player --project .

# Assets
motor asset slice grid assets/player.png --cell-width 32 --cell-height 32 --project .

# Animator (gramática oficial)
motor animator state create Player idle --slices idle_0,idle_1 --fps 8 --loop --project .
motor animator state create Player attack --slices atk_0,atk_1 --fps 12 --no-loop --project .
```

## Compatibilidad Legacy

### ¿Qué se mantiene?

La interfaz `python -m tools.engine_cli` **sigue funcionando** por compatibilidad, pero:

1. **Muestra warning de deprecación** al ejecutarse
2. **No se documenta** como camino principal
3. **No aparece en ejemplos** como recomendación
4. **Solo se menciona** en notas de compatibilidad

### Uso de Legacy (Solo para Referencia)

```bash
# Esto funciona pero muestra warning
python -m tools.engine_cli doctor --project .
# [DEPRECATED] Using python -m tools.engine_cli is deprecated.
# [DEPRECATED] Please use: motor doctor --project .
```

## Nota de Compatibilidad

Si tienes scripts antiguos usando `tools.engine_cli`, debes migrarlos:

### Antes (Legacy)
```python
import subprocess
result = subprocess.run(
    ["python", "-m", "tools.engine_cli", "doctor", "--project", "."],
    capture_output=True,
    text=True
)
```

### Después (Oficial)
```python
import subprocess
import os

# Configurar PYTHONPATH si es necesario
env = os.environ.copy()
env["PYTHONPATH"] = "/path/to/MotorVideojuegosIA"

result = subprocess.run(
    ["motor", "doctor", "--project", "."],
    capture_output=True,
    text=True,
    env=env
)
```

## Validación

Los tests aseguran que no haya regresiones:

```bash
# Ejecutar tests de interfaz
python -m unittest tests.test_examples_interface -v

# Resultado esperado: OK
```

Tests incluidos:
- `test_examples_use_motor_not_legacy_cli` - Verifica uso de `motor`
- `test_examples_use_official_grammar` - Verifica comandos como `state create`
- `test_readme_uses_official_interface` - Verifica README enseña interfaz correcta
- `test_no_hardcoded_tools_engine_cli_in_examples` - Blindaje contra regresiones

## Referencias

- `examples/ai_workflows/` - Ejemplos migrados
- `tests/test_examples_interface.py` - Tests anti-regresión
- `motor/cli.py` - Implementación CLI oficial
- `docs/CLI_GRAMMAR.md` - Especificación gramatical
