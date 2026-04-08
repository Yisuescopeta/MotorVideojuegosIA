# Discrepancias Parser-Registry Corregidas

**Fecha:** 2025-01-21  
**Estado:** CORREGIDO

## Resumen

Se auditó capability por capability para alinear exactamente el capability registry con la CLI oficial `motor`. Se corrigieron discrepancias en firmas, flags y semántica.

## Discrepancias Corregidas

### 1. scene:save

**Antes (Registry):**
```
cli_command="motor scene save [path]"
```

**Problema:** El parser no acepta argumento `path`, solo guarda la escena activa.

**Después (Registry):**
```
cli_command="motor scene save [--project <path>]"
```

**Cambios:**
- Eliminado `[path]` que no existe en el parser
- Añadido `[--project <path>]` que sí existe
- Actualizada la nota: "Saves the currently active scene"

### 2. entity:create

**Antes (Registry):**
```
cli_command="motor entity create <name> [--component <name>]*"
```

**Problema:** El parser usa `--components` (con 's') que acepta JSON, no múltiples flags `--component`.

**Después (Registry):**
```
cli_command="motor entity create <name> [--components <json>]"
```

**Cambios:**
- `--component <name>*` → `--components <json>`
- Nota actualizada explicando formato JSON

### 3. animator:state:create

**Antes (Registry):**
```
cli_command="motor animator state create <entity> <state> --slices <slices...>"
notes="Creates Animator component if needed..."
```

**Problema:** 
1. Faltaban flags opcionales en la firma
2. La nota implicaba auto-creación siempre, pero el parser tiene `--auto-create` opcional

**Después (Registry):**
```
cli_command="motor animator state create <entity> <state> --slices <slices...> [--fps <n>] [--loop|--no-loop] [--set-default] [--auto-create]"
notes="Upserts: creates if not exists... Use --auto-create to create Animator component if missing..."
```

**Cambios:**
- Firma completa con todos los flags: `--fps`, `--loop`, `--no-loop`, `--set-default`, `--auto-create`
- Nota corregida para explicar que `--auto-create` es opcional
- Clarificación sobre semántica de loop/no-loop

## Tests Añadidos

**`tests/test_parser_registry_alignment.py`** - 6 tests estrictos:

| Test | Propósito |
|------|-----------|
| `test_scene_commands_alignment` | Verifica scene:* comandos existen en parser |
| `test_entity_create_signature_matches` | Valida `--components` (con 's') |
| `test_animator_state_create_signature_matches` | Valida todos los flags opcionales |
| `test_no_registry_uses_legacy_upsert_state` | Prohíbe documentar comandos legacy |
| `test_cli_command_is_copyable` | Estructura siempre válida |
| `test_all_implemented_capabilities_match_parser` | FAIL ante cualquier divergencia |

## Validación

```bash
python -m unittest tests.test_parser_registry_alignment -v
# Result: 6 tests OK

python -m unittest tests.test_parser_registry_alignment tests.test_motor_interface_coherence tests.test_motor_registry_consistency tests.test_ai_capability_registry
# Result: 70 tests OK
```

## Criterios de Aceptación Cumplidos

| Criterio | Estado |
|----------|--------|
| Parser y registry coinciden 1:1 | ✅ Firmas exactas |
| Tests fallan ante divergencia | ✅ `test_all_implemented_capabilities_match_parser` |
| Firmas documentadas son copiables | ✅ Todas las cli_command válidas |

## Notas para Mantenimiento Futuro

Al añadir nuevas capabilities:
1. Verificar que la firma CLI coincida exactamente con el parser
2. Documentar todos los flags opcionales
3. Usar `<arg>` para argumentos requeridos, `[--flag]` para opcionales
4. Ejecutar `test_parser_registry_alignment` para validar
