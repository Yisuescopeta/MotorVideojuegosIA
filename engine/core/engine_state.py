"""
engine/core/engine_state.py - Estados del motor

PROPÓSITO:
    Define los estados de ejecución del motor.
    Controla qué sistemas se actualizan en cada momento.

ESTADOS:
    - EDIT: Modo edición, física detenida, animaciones en preview
    - PLAY: Modo juego, todos los sistemas activos
    - PAUSED: Modo pausado, solo renderizado

COMPORTAMIENTO POR ESTADO:

    | Sistema          | EDIT    | PLAY | PAUSED |
    |------------------|---------|------|--------|
    | RenderSystem     | ✔️      | ✔️   | ✔️     |
    | AnimationSystem  | preview | ✔️   | ❌     |
    | PhysicsSystem    | ❌      | ✔️   | ❌     |
    | CollisionSystem  | ❌      | ✔️   | ❌     |
    | RuleSystem       | ❌      | ✔️   | ❌     |
    | InspectorSystem  | ✔️      | ✔️   | ✔️     |

EJEMPLO DE USO:
    from engine.core.engine_state import EngineState
    
    if state == EngineState.PLAY:
        physics_system.update(world, dt)
"""

from enum import Enum, auto


class EngineState(Enum):
    """
    Estados del motor de juego.
    
    Valores:
        EDIT: Modo edición - física detenida, inspección libre
        PLAY: Modo juego - todos los sistemas activos
        PAUSED: Modo pausado - juego congelado, solo render
    """
    EDIT = auto()
    PLAY = auto()
    PAUSED = auto()
    STEPPING = auto()
    
    def is_edit(self) -> bool:
        """True si está en modo edición."""
        return self == EngineState.EDIT
    
    def is_play(self) -> bool:
        """True si está en modo juego."""
        return self == EngineState.PLAY
    
    def is_paused(self) -> bool:
        """True si está pausado."""
        return self == EngineState.PAUSED
    
    def is_running(self) -> bool:
        """True si el juego está corriendo (PLAY o STEPPING)."""
        return self == EngineState.PLAY or self == EngineState.STEPPING
    
    def allows_physics(self) -> bool:
        """True si la física debe actualizarse."""
        return self == EngineState.PLAY or self == EngineState.STEPPING
    
    def allows_gameplay(self) -> bool:
        """True si las reglas y eventos deben procesarse."""
        return self == EngineState.PLAY or self == EngineState.STEPPING
    
    def allows_animation(self) -> bool:
        """True si las animaciones deben avanzar normalmente."""
        return self == EngineState.PLAY or self == EngineState.STEPPING
    
    def allows_animation_preview(self) -> bool:
        """True si las animaciones deben avanzar en modo preview (lento)."""
        return self == EngineState.EDIT
    
    def __str__(self) -> str:
        return self.name
