"""
engine/api/types.py - Tipos de datos para la API

PROPÓSITO:
    Define las estructuras de datos que la API intercambia con el exterior.
    Usa TypedDict para garantizar contratos de datos claros sin obligar 
    al consumidor a importar clases internas del motor.
"""

from typing import TypedDict, List, Any, Optional, Dict

class Vector2D(TypedDict):
    x: float
    y: float

class ComponentData(TypedDict):
    """Datos genéricos de un componente."""
    type: str
    properties: Dict[str, Any]

class EntityData(TypedDict):
    """Representación serializable de una entidad."""
    name: str
    components: Dict[str, Any]  # map component_name -> specific properties

class ActionResult(TypedDict):
    """Resultado de una operación de la API."""
    success: bool
    message: Optional[str]
    data: Optional[Any]

class EngineStatus(TypedDict):
    """Estado actual del motor."""
    state: str  # EDIT, PLAY, PAUSED, STEPPING
    frame: int
    time: float
    fps: int
    entity_count: int
