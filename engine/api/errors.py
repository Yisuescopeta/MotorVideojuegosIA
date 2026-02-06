"""
engine/api/errors.py - Excepciones de la API

PROPÓSITO:
    Define errores específicos que la API puede levantar.
    Facilita el manejo de errores por parte del consumidor (IA/Scripts).
"""

class EngineError(Exception):
    """Error base del motor."""
    pass

class EntityNotFoundError(EngineError):
    """La entidad solicitada no existe."""
    pass

class ComponentNotFoundError(EngineError):
    """El componente solicitado no existe en la entidad."""
    pass

class InvalidOperationError(EngineError):
    """La operación no es válida en el estado actual (ej: editar en PLAY)."""
    pass

class LevelLoadError(EngineError):
    """Error al cargar un nivel/escena."""
    pass
