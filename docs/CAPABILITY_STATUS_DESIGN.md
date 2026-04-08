# Diseño del Sistema de Status de Capabilities

**Versión:** 2026.03  
**Fecha:** 2025-01-21  
**Estado:** IMPLEMENTADO

## Problema

El capability registry mezclaba funcionalidades implementadas con funcionalidades futuras, presentando a la IA capacidades como "disponibles" cuando aún no existían en la CLI oficial ni en la API pública.

## Solución

Se implementó un sistema de status explícito para cada capability:

```python
status: "implemented" | "planned" | "deprecated"
```

## Modelo de Capability

```python
@dataclass(frozen=True)
class Capability:
    id: str
    summary: str
    mode: str
    api_methods: List[str]
    cli_command: str
    example: CapabilityExample
    notes: str = ""
    tags: List[str] = field(default_factory=list)
    status: str = "implemented"  # NUEVO: status field
```

## Estados

### `implemented`
- Funcionalidad completamente implementada
- Disponible en CLI oficial (`motor`)
- API pública estable
- **Incluida en** `motor_ai.json` → `implemented_capabilities`

### `planned`
- Funcionalidad planificada para futuro
- No disponible aún en CLI
- API puede cambiar
- **Incluida en** `motor_ai.json` → `planned_capabilities` (roadmap)

### `deprecated`
- Funcionalidad obsoleta
- Será removida en versiones futuras
- Se mantiene por compatibilidad
- **Incluida en** `motor_ai.json` como deprecated

## Estructura de motor_ai.json

```json
{
  "schema_version": 3,
  "engine": {
    "name": "MotorVideojuegosIA",
    "version": "2026.03"
  },
  "implemented_capabilities": [
    {
      "id": "scene:create",
      "summary": "Create a new scene",
      "mode": "both",
      "status": "implemented",
      "cli_command": "motor scene create <name>",
      ...
    }
  ],
  "planned_capabilities": [
    {
      "id": "runtime:play",
      "summary": "Start play mode",
      "mode": "edit",
      "status": "planned",
      "cli_command": "motor runtime play",
      ...
    }
  ],
  "capability_counts": {
    "implemented": 25,
    "planned": 17,
    "total": 42
  }
}
```

## Capabilities Planificadas (Ejemplos)

Las siguientes capabilities están marcadas como `planned`:

- `runtime:play`, `runtime:stop`, `runtime:step` - Modo play
- `runtime:undo`, `runtime:redo` - Undo/redo system
- `physics:query:aabb`, `physics:query:ray` - Queries físicos
- `prefab:instantiate`, `prefab:list` - Sistema de prefabs
- `entity:delete`, `entity:parent`, `entity:list` - Gestión avanzada de entidades
- `asset:find`, `asset:metadata:get` - Búsqueda y metadata de assets
- `introspect:entity`, `introspect:status` - Introspección avanzada

## Implementación en Registry Builder

```python
class CapabilityRegistryBuilder:
    # Capabilities planificadas (no implementadas aún)
    _PLANNED_CAPABILITIES = {
        "runtime:play", "runtime:stop", "runtime:step",
        "runtime:undo", "runtime:redo",
        "physics:query:aabb", "physics:query:ray",
        "prefab:instantiate", "prefab:list",
        ...
    }

    def _add(self, capability: Capability) -> None:
        # Determina status basado en ID
        if capability.id in self._PLANNED_CAPABILITIES:
            capability = replace(capability, status="planned")
        self._registry.register(capability)
```

## API de Registry

### Nuevos Métodos

```python
class CapabilityRegistry:
    def list_implemented(self) -> List[Capability]:
        """Return only implemented capabilities."""
        return [cap for cap in self._capabilities.values() 
                if cap.status == "implemented"]

    def list_planned(self) -> List[Capability]:
        """Return only planned capabilities."""
        return [cap for cap in self._capabilities.values() 
                if cap.status == "planned"]

    def list_deprecated(self) -> List[Capability]:
        """Return only deprecated capabilities."""
        return [cap for cap in self._capabilities.values() 
                if cap.status == "deprecated"]
```

## Beneficios

1. **Claridad para IA** - La IA sabe exactamente qué puede usar ahora vs. qué viene en el futuro
2. **Contrato fiable** - `implemented_capabilities` es el contrato ejecutable real
3. **Roadmap visible** - `planned_capabilities` muestra dirección del motor
4. **Sin falsas promesas** - No se presenta como "disponible" lo que no existe
5. **Tests limpios** - No más "trucos" para tolerar capabilities futuras

## Validación

### Tests de Separación

```python
def test_implemented_capabilities_only_contain_implemented(self):
    registry = get_default_registry()
    for cap in registry.list_implemented():
        self.assertEqual(cap.status, "implemented")

def test_planned_capabilities_separated_from_implemented(self):
    registry = get_default_registry()
    implemented_ids = {cap.id for cap in registry.list_implemented()}
    planned_ids = {cap.id for cap in registry.list_planned()}
    # No overlap
    self.assertEqual(implemented_ids & planned_ids, set())
```

## Migración de Schema

| Versión | Cambios |
|---------|---------|
| 1 | Estructura inicial |
| 2 | Añadido engine info |
| 3 | Separación implemented/planned + status field |

## Backward Compatibility

- El campo `status` tiene valor por defecto `"implemented"`
- Capabilities existentes sin status se asumen implementadas
- Schema version incrementado a 3

## Referencias

- `engine/ai/capability_registry.py` - Modelo con status
- `engine/ai/registry_builder.py` - Builder con lista _PLANNED_CAPABILITIES
- `docs/CAPABILITY_STATUS_DESIGN.md` - Este documento
