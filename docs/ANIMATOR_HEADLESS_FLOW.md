# Flujo Oficial Headless de Animator

**Versión:** 2026.03  
**Fecha:** 2025-01-21  
**Estado:** ESTABLE

## Resumen

El flujo headless de animator permite a una IA completar la configuración de animaciones sin abrir el editor visual. El flujo es semánticamente limpio y sin ambigüedades.

## Flujo Oficial

```
Escena → Entidad → Asegurar Animator → Sprite Sheet → Slices → Estados → Info
```

## Comandos Oficiales

### 1. Crear Escena
```bash
motor scene create "LevelName" --project .
```

### 2. Crear Entidad
```bash
motor entity create "Player" --project .
```

### 3. Asegurar Animator
```bash
motor animator ensure Player --project .
```

**Semántica:** Crea el componente Animator si no existe. Idempotente.

### 4. Asignar Sprite Sheet
```bash
motor animator set-sheet Player assets/player.png --project .
```

### 5. Crear Slices
```bash
# Grid-based slicing
motor asset slice grid assets/player.png --cell-width 32 --cell-height 32 --project .

# O manual slicing
motor asset slice manual assets/player.png --slices '[{"name":"idle_0",...}]' --project .
```

### 6. Crear Estados

**Estado Loop (ej: idle):**
```bash
motor animator state create Player idle \
  --slices idle_0,idle_1,idle_2,idle_3 \
  --fps 8 \
  --loop \
  --set-default \
  --project .
```

**Estado No-Loop (ej: attack):**
```bash
motor animator state create Player attack \
  --slices attack_0,attack_1 \
  --fps 12 \
  --no-loop \
  --project .
```

**Semántica de Loop:**
- `--loop`: Animación se repite indefinidamente (default)
- `--no-loop`: Animación se reproduce una vez y se detiene

### 7. Consultar Info
```bash
motor animator info Player --project .
```

## Estrategia Oficial para Disponer de Animator

La estrategia oficial es **dos pasos explícitos**:

1. **`motor animator ensure <entity>`** - Garantiza que existe el componente
2. **`motor animator set-sheet <entity> <asset>`** - Asigna el sprite sheet

### Alternativa: Auto-creación con estado

Si se prefiere un solo comando, usar:

```bash
motor animator state create Player idle \
  --slices slice_0,slice_1 \
  --fps 8 \
  --loop \
  --auto-create \
  --project .
```

El flag `--auto-create` crea el Animator automáticamente si falta.

## Coherencia de Comandos

| Comando | Propósito | Semántica |
|---------|-----------|-----------|
| `animator ensure` | Garantizar existencia del componente | Idempotente, crea si falta |
| `animator set-sheet` | Asignar sprite sheet | Actualiza referencia |
| `animator state create` | Crear/actualizar estado | Upsert, puede auto-crear Animator |
| `animator state remove` | Eliminar estado | Elimina estado específico |
| `animator info` | Consultar configuración | Read-only |

## Tests E2E

Los tests validan el flujo completo:

```bash
python -m unittest tests.test_animator_headless_flow -v
```

**Tests incluidos:**

1. **`test_complete_headless_animator_flow`**
   - Crea escena y entidad
   - Asegura Animator
   - Setea sprite sheet
   - Crea slices
   - Crea estado loop (idle)
   - Crea estado no-loop (attack)
   - Verifica info final

2. **`test_animator_flow_without_editor`**
   - Valida que todas las operaciones funcionan sin editor visual

## Ejemplo Completo (Python)

```python
import subprocess
import json

def run_motor(*args):
    cmd = ["motor"] + list(args) + ["--project", ".", "--json"]
    result = subprocess.run(cmd, capture_output=True, text=True)
    output = result.stdout
    if "{" in output:
        output = output[output.index("{"):]
    return json.loads(output)

# Flujo completo
entity = "Player"

# 1. Crear escena y entidad
run_motor("scene", "create", "Level1")
run_motor("entity", "create", entity)

# 2. Asegurar Animator
run_motor("animator", "ensure", entity)

# 3. Setear sprite sheet
run_motor("animator", "set-sheet", entity, "assets/player.png")

# 4. Crear slices
run_motor("asset", "slice", "grid", "assets/player.png", 
          "--cell-width", "32", "--cell-height", "32")

# 5. Crear estados
run_motor("animator", "state", "create", entity, "idle",
          "--slices", "idle_0,idle_1,idle_2,idle_3",
          "--fps", "8", "--loop", "--set-default")

run_motor("animator", "state", "create", entity, "attack",
          "--slices", "attack_0,attack_1",
          "--fps", "12", "--no-loop")

# 6. Verificar
info = run_motor("animator", "info", entity)
print(f"States: {len(info['data']['states'])}")
```

## Referencias

- `motor/cli_core.py`: Implementaciones de comandos
- `tests/test_animator_headless_flow.py`: Tests E2E
- `examples/ai_workflows/03_create_animated_entity.py`: Ejemplo completo
- `docs/CLI_GRAMMAR.md`: Gramática oficial de comandos
