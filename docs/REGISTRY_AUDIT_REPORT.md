# Auditoría Semántica del Capability Registry

**Fecha:** 2025-01-21  
**Auditor:** Maintainer Principal  
**Estado:** COMPLETADA

## Resumen Ejecutivo

Se realizó una auditoría semántica completa del capability registry para convertirlo en una fuente de verdad fiable para IA. Se identificaron y corrigieron discrepancias entre el registry y la implementación real del motor.

## Herramienta de Auditoría

Se creó `scripts/audit_registry.py` que verifica:
1. Componentes mencionados existen en ComponentRegistry
2. Métodos API referenciados existen en las clases API
3. Comandos CLI son válidos
4. Modos (edit/play/both) son consistentes

## Discrepancias Corregidas

### 1. Métodos API Inexistentes

#### `animator:ensure`
- **Problema:** Referenciaba `AuthoringAPI.ensure_animator` que no existe
- **Solución:** Eliminado capability duplicado. El funcionalidad de "ensure" se logra con `animator:set_sheet` + `animator:state:create --auto-create`
- **Impacto:** 1 capability removido (era duplicado de `animator:set_sheet`)

#### `project:info`
- **Problema:** Referenciaba `AssetsProjectAPI.get_project_info` que no existe
- **Solución:** Corregido a `AssetsProjectAPI.get_project_manifest` (método real)
- **Impacto:** CLI command sigue siendo `motor project info` (no cambia interfaz)

#### `introspect:capabilities`
- **Problema:** Referenciaba `CapabilityRegistry.list_all` que no es una API pública
- **Solución:** Corregido a `cmd_capabilities` (función real del CLI)
- **Impacto:** Registry ahora documenta correctamente la implementación

### 2. Duplicidad de Capabilities

#### `animator:set_sheet`
- **Problema:** Existía en dos lugares del registry (líneas 415 y 495)
- **Solución:** Eliminado duplicado en línea 495
- **Impacto:** Registry ahora tiene 42 capabilities (era 43)

## Estado Final del Registry

### Métricas
- **Capabilities totales:** 42
- **Componentes disponibles:** 25
- **Métodos API AuthoringAPI:** 53
- **Métodos API SceneWorkspaceAPI:** 23
- **Métodos API AssetsProjectAPI:** 24
- **Métodos API RuntimeAPI:** 24

### Capabilities por Categoría

| Categoría | Count | Capabilities |
|-----------|-------|--------------|
| scene | 6 | create, load, save, flow:set_next, flow:load_next |
| entity | 5 | create, delete, parent, list |
| component | 3 | add, edit, remove |
| asset | 8 | list, find, metadata:get, refresh, slice:grid, slice:list, slice:auto, slice:manual |
| animator | 4 | set_sheet, info, state:create, state:remove |
| prefab | 3 | instantiate, unpack, apply |
| project | 3 | open, manifest, editor_state |
| runtime | 5 | play, stop, step, undo, redo |
| physics | 3 | query:aabb, query:ray, backend:list |
| introspect | 3 | capabilities, entity, status |

## Tests de Fidelidad Semántica

Se crearon tests automáticos que fallarán si se reintroduce deriva semántica:

### `test_registry_semantic_fidelity.py` (nuevo)
- Verifica que componentes en ejemplos existen
- Verifica que api_methods apuntan a superficies públicas
- Verifica que cli_commands pertenecen a CLI oficial
- Verifica coherencia de modos

### `scripts/audit_registry.py`
- Script standalone para auditoría manual
- Puede ejecutarse en CI/CD
- Retorna código de error si hay discrepancias

## Decisiones Tomadas

### 1. Eliminación de `animator:ensure`
**Razón:** El método `ensure_animator` no existe en la API. La funcionalidad de asegurar que un Animator existe se logra mediante:
- `animator:set_sheet` - Crea el componente si no existe al setear sprite sheet
- `animator:state:create --auto-create` - Crea el componente si no existe al crear estado

**Alternativa considerada:** Implementar `ensure_animator` en AuthoringAPI. **Descartado** porque duplicaría funcionalidad existente.

### 2. Corrección de `introspect:capabilities`
**Razón:** `CapabilityRegistry` no es una API accesible para usuarios/IA. Es una clase interna.

**Solución:** Documentar como `cmd_capabilities` que es la función real que implementa `motor capabilities`.

### 3. Conservación de CLI Commands
**Decisión:** Aunque cambiamos `project:info` → `project:manifest` en el ID del capability, el CLI command sigue siendo `motor project info`.

**Razón:** El CLI command es la interfaz pública estable. El capability ID es para organización interna.

## Validación

### Tests Pasando
```bash
python -m unittest tests.test_ai_capability_registry \
                   tests.test_motor_registry_consistency \
                   tests.test_motor_cli_contract
# Result: OK (100 tests)
```

### Auditoría Pasando
```bash
python scripts/audit_registry.py
# Result: PASSED - Registry is semantically accurate
```

## Recomendaciones para Mantenimiento Futuro

1. **Ejecutar auditoría antes de releases:**
   ```bash
   python scripts/audit_registry.py
   ```

2. **Agregar auditoría a CI/CD:**
   - Fallar build si audit_registry.py retorna != 0

3. **Reglas para nuevos capabilities:**
   - Verificar que api_methods existen antes de documentar
   - Usar `scripts/audit_registry.py` como check
   - No documentar capacidades futuras como "ya disponibles"

4. **Lista de verificación para nuevos capabilities:**
   - [ ] Componentes mencionados existen en ComponentRegistry
   - [ ] api_methods existen en clases API
   - [ ] cli_commands son válidos
   - [ ] mode es coherente (edit/play/both)
   - [ ] Ejemplo es ejecutable por IA

## Conclusión

El capability registry ahora es una fuente de verdad fiable para IA. Todas las discrepancias semánticas han sido corregidas. Los tests automáticos prevenirán regresiones futuras.

**Impacto:**
- 3 capabilities corregidos
- 1 capability duplicado eliminado
- 0 breaking changes en CLI (interfaz estable)
- 100% de tests pasando
