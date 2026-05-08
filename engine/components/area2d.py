"""
engine/components/area2d.py - Componente Area2D adaptado de Godot

PROPOSITO:
    Define un area de monitoreo 2D que detecta cuerpos y areas
    que entran/salen de su zona. Equivalente a Godot Area2D.

PROPIEDADES:
    - monitoring: Si monitorea activamente overlaps
    - monitorable: Si puede ser detectada por otras areas
    - space_override: Modo de override de espacio fisico
    - gravity_point: Si actua como punto de gravedad
    - gravity_distance_scale: Escala de distancia para gravedad
    - priority: Prioridad de procesamiento

SERIALIZACION JSON:
    {
        "monitoring": true,
        "monitorable": true,
        "space_override": "disabled",
        "gravity_point": false,
        "gravity_distance_scale": 0.0,
        "priority": 0
    }
"""

from typing import Any

from engine.ecs.component import Component


class Area2D(Component):
    """
    Componente que define un area de monitoreo 2D (adaptado de Godot Area2D).

    Monitorea cuerpos y areas que entran/salen de su zona. Emite eventos via EventBus:
    body_entered, body_exited, area_entered, area_exited.

    Requiere un Collider para definir la forma del area.
    """

    VALID_SPACE_OVERRIDE_MODES = {"disabled", "combine", "combine_replace", "replace", "replace_combine"}

    _OLD_OVERRIDE_DEFAULTS = {"", "disabled"}

    def __init__(
        self,
        monitoring: bool = True,
        monitorable: bool = True,
        space_override: str = "disabled",
        gravity_point: bool = False,
        gravity_distance_scale: float = 0.0,
        priority: int = 0,
        gravity_override_x: float = 0.0,
        gravity_override_y: float = 0.0,
        linear_damp_override: float = 0.0,
        angular_damp_override: float = 0.0,
        gravity_space_override: str = "disabled",
        linear_damp_space_override: str = "disabled",
        angular_damp_space_override: str = "disabled",
    ) -> None:
        self.enabled: bool = True
        self.monitoring: bool = monitoring
        self.monitorable: bool = monitorable
        self.space_override: str = str(space_override or "disabled")  # Deprecated: use per-mode overrides
        self.gravity_point: bool = gravity_point
        self.gravity_distance_scale: float = gravity_distance_scale
        self.priority: int = int(priority)
        self.gravity_override_x: float = float(gravity_override_x)
        self.gravity_override_y: float = float(gravity_override_y)
        self.linear_damp_override: float = float(linear_damp_override)
        self.angular_damp_override: float = float(angular_damp_override)

        # New per-mode space override fields (Godot-compatible)
        gso = str(gravity_space_override or "disabled")
        self.gravity_space_override: str = gso if gso in self.VALID_SPACE_OVERRIDE_MODES else "disabled"
        lds = str(linear_damp_space_override or "disabled")
        self.linear_damp_space_override: str = lds if lds in self.VALID_SPACE_OVERRIDE_MODES else "disabled"
        ads = str(angular_damp_space_override or "disabled")
        self.angular_damp_space_override: str = ads if ads in self.VALID_SPACE_OVERRIDE_MODES else "disabled"

        # Backward compat: if old space_override is set but new per-mode fields aren't,
        # inherit from old field
        old_mode = self.space_override
        if old_mode not in self._OLD_OVERRIDE_DEFAULTS and old_mode in self.VALID_SPACE_OVERRIDE_MODES:
            if gso in self._OLD_OVERRIDE_DEFAULTS:
                self.gravity_space_override = old_mode
            if lds in self._OLD_OVERRIDE_DEFAULTS:
                self.linear_damp_space_override = old_mode
            if ads in self._OLD_OVERRIDE_DEFAULTS:
                self.angular_damp_space_override = old_mode

        # Runtime tracking (NO serializado)
        self._tracked_bodies: set[int] = set()
        self._tracked_areas: set[int] = set()

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "monitoring": self.monitoring,
            "monitorable": self.monitorable,
            "space_override": self.space_override,
            "gravity_point": self.gravity_point,
            "gravity_distance_scale": self.gravity_distance_scale,
            "priority": self.priority,
            "gravity_override_x": self.gravity_override_x,
            "gravity_override_y": self.gravity_override_y,
            "linear_damp_override": self.linear_damp_override,
            "angular_damp_override": self.angular_damp_override,
            "gravity_space_override": self.gravity_space_override,
            "linear_damp_space_override": self.linear_damp_space_override,
            "angular_damp_space_override": self.angular_damp_space_override,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Area2D":
        component = cls(
            monitoring=data.get("monitoring", True),
            monitorable=data.get("monitorable", True),
            space_override=data.get("space_override", "disabled"),
            gravity_point=data.get("gravity_point", False),
            gravity_distance_scale=data.get("gravity_distance_scale", 0.0),
            priority=data.get("priority", 0),
            gravity_override_x=data.get("gravity_override_x", 0.0),
            gravity_override_y=data.get("gravity_override_y", 0.0),
            linear_damp_override=data.get("linear_damp_override", 0.0),
            angular_damp_override=data.get("angular_damp_override", 0.0),
            gravity_space_override=data.get("gravity_space_override", "disabled"),
            linear_damp_space_override=data.get("linear_damp_space_override", "disabled"),
            angular_damp_space_override=data.get("angular_damp_space_override", "disabled"),
        )
        component.enabled = data.get("enabled", True)
        return component
