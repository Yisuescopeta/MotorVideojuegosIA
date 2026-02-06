"""
engine/components/sprite.py - Componente de renderizado de sprites

PROPÓSITO:
    Permite renderizar una imagen 2D (textura) en pantalla.
    Requiere un componente Transform para la posición.

PROPIEDADES:
    - texture_path (str): Ruta relativa al archivo de imagen
    - width (int): Ancho de renderizado en píxeles (0 = usar tamaño original)
    - height (int): Alto de renderizado en píxeles (0 = usar tamaño original)
    - origin_x (float): Punto de origen X (0-1, default 0.5 = centro)
    - origin_y (float): Punto de origen Y (0-1, default 0.5 = centro)
    - flip_x (bool): Invertir horizontalmente
    - flip_y (bool): Invertir verticalmente
    - tint (tuple): Color de tinte RGBA (default blanco = sin tinte)

EJEMPLO DE USO:
    sprite = Sprite(texture_path="assets/player.png")
    entity.add_component(sprite)

SERIALIZACIÓN JSON:
    {
        "texture_path": "assets/player.png",
        "width": 32,
        "height": 32,
        "origin_x": 0.5,
        "origin_y": 0.5,
        "flip_x": false,
        "flip_y": false
    }
"""

from typing import Any, Tuple

from engine.ecs.component import Component


class Sprite(Component):
    """
    Componente para renderizar una textura 2D.
    
    Atributos:
        texture_path: Ruta al archivo de imagen
        width: Ancho de renderizado (0 = original)
        height: Alto de renderizado (0 = original)
        origin_x: Origen horizontal (0=izq, 0.5=centro, 1=der)
        origin_y: Origen vertical (0=arriba, 0.5=centro, 1=abajo)
        flip_x: Invertir horizontalmente
        flip_y: Invertir verticalmente
        tint: Color de tinte (R, G, B, A) valores 0-255
    """
    
    def __init__(
        self,
        texture_path: str = "",
        width: int = 0,
        height: int = 0,
        origin_x: float = 0.5,
        origin_y: float = 0.5,
        flip_x: bool = False,
        flip_y: bool = False,
        tint: Tuple[int, int, int, int] = (255, 255, 255, 255)
    ) -> None:
        """
        Inicializa el Sprite.
        
        Args:
            texture_path: Ruta al archivo de imagen
            width: Ancho de renderizado (0 = usar tamaño original)
            height: Alto de renderizado (0 = usar tamaño original)
            origin_x: Punto de origen X (0-1)
            origin_y: Punto de origen Y (0-1)
            flip_x: Si es True, invierte horizontalmente
            flip_y: Si es True, invierte verticalmente
            tint: Color de tinte RGBA
        """
        self.texture_path: str = texture_path
        self.width: int = width
        self.height: int = height
        self.origin_x: float = origin_x
        self.origin_y: float = origin_y
        self.flip_x: bool = flip_x
        self.flip_y: bool = flip_y
        self.tint: Tuple[int, int, int, int] = tint
    
    def to_dict(self) -> dict[str, Any]:
        """Serializa el Sprite a diccionario."""
        return {
            "texture_path": self.texture_path,
            "width": self.width,
            "height": self.height,
            "origin_x": self.origin_x,
            "origin_y": self.origin_y,
            "flip_x": self.flip_x,
            "flip_y": self.flip_y,
            "tint": list(self.tint)
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Sprite":
        """Crea un Sprite desde un diccionario."""
        tint = data.get("tint", [255, 255, 255, 255])
        return cls(
            texture_path=data.get("texture_path", ""),
            width=data.get("width", 0),
            height=data.get("height", 0),
            origin_x=data.get("origin_x", 0.5),
            origin_y=data.get("origin_y", 0.5),
            flip_x=data.get("flip_x", False),
            flip_y=data.get("flip_y", False),
            tint=tuple(tint)  # type: ignore
        )
