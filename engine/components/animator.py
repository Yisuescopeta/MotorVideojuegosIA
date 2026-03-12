"""
engine/components/animator.py - Componente de animaciones por sprite sheet

PROPÓSITO:
    Gestiona animaciones basadas en sprite sheets con múltiples estados.
    Cada estado tiene una lista de frames, velocidad y comportamiento de loop.

PROPIEDADES:
    - sprite_sheet (str): Ruta al sprite sheet
    - frame_width (int): Ancho de cada frame en píxeles
    - frame_height (int): Alto de cada frame en píxeles
    - animations (dict): Diccionario de AnimationData por nombre de estado
    - current_state (str): Estado de animación actual
    - current_frame (int): Índice del frame actual en la animación
    - elapsed_time (float): Tiempo acumulado desde el último cambio de frame
    - is_finished (bool): True si la animación no-loop terminó

EJEMPLO DE USO:
    animator = Animator(
        sprite_sheet="assets/player_sheet.png",
        frame_width=32,
        frame_height=32,
        animations={
            "idle": AnimationData(frames=[0, 1, 2, 3], fps=8, loop=True),
            "run": AnimationData(frames=[4, 5, 6, 7, 8, 9], fps=12, loop=True),
            "jump": AnimationData(frames=[10, 11], fps=10, loop=False, on_complete="idle")
        },
        default_state="idle"
    )
    entity.add_component(animator)

SERIALIZACIÓN JSON:
    {
        "sprite_sheet": "assets/player_sheet.png",
        "frame_width": 32,
        "frame_height": 32,
        "animations": {
            "idle": {"frames": [0,1,2,3], "fps": 8, "loop": true},
            "run": {"frames": [4,5,6,7,8,9], "fps": 12, "loop": true}
        },
        "current_state": "idle"
    }
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from engine.ecs.component import Component


@dataclass
class AnimationData:
    """
    Datos de una animación individual.
    
    Atributos:
        frames: Lista de índices de frames en el sprite sheet
        fps: Velocidad de la animación (frames por segundo)
        loop: Si la animación debe repetirse
        on_complete: Estado al que cambiar cuando termina (solo si loop=False)
    """
    frames: List[int] = field(default_factory=lambda: [0])
    slice_names: List[str] = field(default_factory=list)
    fps: float = 8.0
    loop: bool = True
    on_complete: Optional[str] = None
    
    def to_dict(self) -> dict[str, Any]:
        """Serializa AnimationData a diccionario."""
        result: dict[str, Any] = {
            "frames": self.frames,
            "slice_names": self.slice_names,
            "fps": self.fps,
            "loop": self.loop
        }
        if self.on_complete is not None:
            result["on_complete"] = self.on_complete
        return result
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AnimationData":
        """Crea AnimationData desde un diccionario."""
        return cls(
            frames=data.get("frames", [0]),
            slice_names=data.get("slice_names", []),
            fps=data.get("fps", 8.0),
            loop=data.get("loop", True),
            on_complete=data.get("on_complete")
        )

    def get_frame_count(self) -> int:
        if self.slice_names:
            return len(self.slice_names)
        return len(self.frames)


class Animator(Component):
    """
    Componente que gestiona animaciones por sprite sheet.
    
    El Animator almacena múltiples animaciones (estados) y controla
    cuál se está reproduciendo. El AnimationSystem actualiza los frames.
    
    Atributos:
        sprite_sheet: Ruta al archivo de sprite sheet
        frame_width: Ancho de cada frame
        frame_height: Alto de cada frame
        animations: Diccionario de estados -> AnimationData
        current_state: Nombre del estado actual
        current_frame: Índice del frame actual (dentro de animations[current_state].frames)
        elapsed_time: Tiempo acumulado para cambio de frame
        is_finished: True si animación no-loop terminó
    """
    
    def __init__(
        self,
        sprite_sheet: str = "",
        frame_width: int = 32,
        frame_height: int = 32,
        animations: Optional[Dict[str, AnimationData]] = None,
        default_state: str = "idle"
    ) -> None:
        """
        Inicializa el Animator.
        
        Args:
            sprite_sheet: Ruta al archivo de sprite sheet
            frame_width: Ancho de cada frame en píxeles
            frame_height: Alto de cada frame en píxeles
            animations: Diccionario de animaciones por estado
            default_state: Estado inicial de la animación
        """
        self.enabled: bool = True
        self.sprite_sheet: str = sprite_sheet
        self.frame_width: int = frame_width
        self.frame_height: int = frame_height
        self.animations: Dict[str, AnimationData] = animations or {}
        self.default_state: str = default_state
        
        # Estado de reproducción
        self.current_state: str = default_state
        self.current_frame: int = 0  # Índice dentro de la lista de frames
        self.elapsed_time: float = 0.0
        self.is_finished: bool = False
    
    def play(self, state: str, force_restart: bool = False) -> None:
        """
        Cambia al estado de animación especificado.
        
        Args:
            state: Nombre del estado a reproducir
            force_restart: Si True, reinicia aunque sea el mismo estado
        """
        if state not in self.animations:
            print(f"[WARNING] Animator: estado '{state}' no existe")
            return
        
        # Si es el mismo estado y no forzamos reinicio, no hacer nada
        if state == self.current_state and not force_restart:
            return
        
        self.current_state = state
        self.current_frame = 0
        self.elapsed_time = 0.0
        self.is_finished = False
    
    def get_current_animation(self) -> Optional[AnimationData]:
        """
        Obtiene los datos de la animación actual.
        
        Returns:
            AnimationData del estado actual, o None si no existe
        """
        return self.animations.get(self.current_state)
    
    def get_current_sprite_frame(self) -> int:
        """
        Obtiene el índice del frame actual en el sprite sheet.
        
        Returns:
            Índice del frame en el sprite sheet (no el índice en la lista)
        """
        anim = self.get_current_animation()
        if anim is None or not anim.frames:
            return 0
        
        # Asegurar que current_frame está en rango
        frame_index = min(self.current_frame, len(anim.frames) - 1)
        return anim.frames[frame_index]

    def get_current_slice_name(self) -> Optional[str]:
        """Devuelve el slice nombrado actual si la animacion usa metadata de slicing."""
        anim = self.get_current_animation()
        if anim is None or not anim.slice_names:
            return None
        frame_index = min(self.current_frame, len(anim.slice_names) - 1)
        return anim.slice_names[frame_index]
    
    def get_source_rect(self, sheet_columns: int) -> tuple[int, int, int, int]:
        """
        Calcula el rectángulo de origen en el sprite sheet.
        
        El sprite sheet se organiza en una grilla donde los frames
        están numerados de izquierda a derecha, de arriba a abajo.
        
        Args:
            sheet_columns: Número de columnas en el sprite sheet
            
        Returns:
            Tupla (x, y, width, height) del rectángulo de origen
        """
        frame_index = self.get_current_sprite_frame()
        
        # Calcular posición en la grilla
        col = frame_index % sheet_columns
        row = frame_index // sheet_columns
        
        return (
            col * self.frame_width,
            row * self.frame_height,
            self.frame_width,
            self.frame_height
        )
    
    def to_dict(self) -> dict[str, Any]:
        """Serializa el Animator a diccionario."""
        return {
            "enabled": self.enabled,
            "sprite_sheet": self.sprite_sheet,
            "frame_width": self.frame_width,
            "frame_height": self.frame_height,
            "animations": {
                name: anim.to_dict()
                for name, anim in self.animations.items()
            },
            "default_state": self.default_state,
            "current_state": self.current_state,
            "current_frame": self.current_frame,
            "is_finished": self.is_finished
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Animator":
        """Crea un Animator desde un diccionario."""
        animations = {}
        for name, anim_data in data.get("animations", {}).items():
            animations[name] = AnimationData.from_dict(anim_data)
        
        animator = cls(
            sprite_sheet=data.get("sprite_sheet", ""),
            frame_width=data.get("frame_width", 32),
            frame_height=data.get("frame_height", 32),
            animations=animations,
            default_state=data.get("default_state", data.get("current_state", "idle"))
        )
        animator.enabled = data.get("enabled", True)
        animator.current_state = data.get("current_state", animator.default_state)
        animator.current_frame = data.get("current_frame", 0)
        animator.is_finished = data.get("is_finished", False)
        return animator
