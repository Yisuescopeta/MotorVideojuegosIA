"""
engine/components/rigidbody.py - Componente de física básica

PROPÓSITO:
    Añade propiedades físicas simples a una entidad:
    velocidad, gravedad y detección de suelo.

PROPIEDADES:
    - velocity_x (float): Velocidad horizontal (píxeles/segundo)
    - velocity_y (float): Velocidad vertical (píxeles/segundo)
    - gravity_scale (float): Multiplicador de gravedad (0 = sin gravedad)
    - is_grounded (bool): Si la entidad está en el suelo

EJEMPLO DE USO:
    rb = RigidBody(gravity_scale=1.0)
    entity.add_component(rb)

    # El PhysicsSystem actualizará la posición
    rb.velocity_x = 100  # Mover a la derecha

SERIALIZACIÓN JSON:
    {
        "velocity_x": 0,
        "velocity_y": 0,
        "gravity_scale": 1.0,
        "is_grounded": false
    }
"""

from typing import Any

from engine.ecs.component import Component


class RigidBody(Component):
    """
    Componente de física básica con velocidad y gravedad.

    Atributos:
        velocity_x: Velocidad horizontal (px/s)
        velocity_y: Velocidad vertical (px/s)
        gravity_scale: Multiplicador de gravedad
        is_grounded: Si está tocando el suelo
    """

    VALID_CONSTRAINTS = {
        "None",
        "FreezePositionX",
        "FreezePositionY",
        "FreezePosition",
    }

    def __init__(
        self,
        velocity_x: float = 0.0,
        velocity_y: float = 0.0,
        gravity_scale: float = 1.0,
        is_grounded: bool = False,
        body_type: str = "dynamic",
        simulated: bool = True,
        freeze_x: bool = False,
        freeze_y: bool = False,
        use_full_kinematic_contacts: bool = False,
        collision_detection_mode: str = "discrete",
        constraints: list[str] | None = None,
        mass: float = 1.0,
        linear_damping: float = 0.0,
        angular_damping: float = 0.0,
        angular_velocity: float = 0.0,
        inertia: float = 1.0,
        center_of_mass_x: float = 0.0,
        center_of_mass_y: float = 0.0,
    ) -> None:
        """
        Inicializa el RigidBody.

        Args:
            velocity_x: Velocidad horizontal inicial
            velocity_y: Velocidad vertical inicial
            gravity_scale: Multiplicador de gravedad (0=sin gravedad)
            is_grounded: Estado inicial de contacto con suelo
            mass: Masa del cuerpo en kg (afecta respuesta a fuerzas y colisiones)
            linear_damping: Amortiguación lineal (0=sin fricción de aire, 1=se detiene instantáneamente)
            angular_damping: Amortiguación angular (0=sin fricción rotacional)
            angular_velocity: Velocidad angular en rad/s
            inertia: Momento de inercia (afecta respuesta a torque)
            center_of_mass_x: Centro de masa relativo X
            center_of_mass_y: Centro de masa relativo Y
        """
        self.enabled: bool = True
        self.velocity_x: float = velocity_x
        self.velocity_y: float = velocity_y
        self.gravity_scale: float = gravity_scale
        self.is_grounded: bool = is_grounded
        self.body_type: str = body_type
        self.simulated: bool = simulated
        normalized_constraints = self.normalize_constraints(constraints)
        if normalized_constraints:
            freeze_x = "FreezePositionX" in normalized_constraints
            freeze_y = "FreezePositionY" in normalized_constraints
        self.freeze_x: bool = freeze_x
        self.freeze_y: bool = freeze_y
        self.constraints: list[str] = self.constraints_from_freeze(self.freeze_x, self.freeze_y)
        self.use_full_kinematic_contacts: bool = use_full_kinematic_contacts
        self.collision_detection_mode: str = str(collision_detection_mode or "discrete")
        self.mass: float = mass
        self.linear_damping: float = linear_damping
        self.angular_damping: float = angular_damping
        self.angular_velocity: float = angular_velocity
        self.inertia: float = inertia
        self.center_of_mass_x: float = center_of_mass_x
        self.center_of_mass_y: float = center_of_mass_y

        # Buffers de fuerzas runtime (NO se serializan — se limpian cada frame)
        self._force_buffer_x: float = 0.0
        self._force_buffer_y: float = 0.0
        self._torque_buffer: float = 0.0
        self._impulse_buffer_x: float = 0.0
        self._impulse_buffer_y: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Serializa el RigidBody a diccionario."""
        self.constraints = self.constraints_from_freeze(self.freeze_x, self.freeze_y)
        return {
            "enabled": self.enabled,
            "velocity_x": self.velocity_x,
            "velocity_y": self.velocity_y,
            "gravity_scale": self.gravity_scale,
            "is_grounded": self.is_grounded,
            "body_type": self.body_type,
            "simulated": self.simulated,
            "freeze_x": self.freeze_x,
            "freeze_y": self.freeze_y,
            "constraints": list(self.constraints),
            "use_full_kinematic_contacts": self.use_full_kinematic_contacts,
            "collision_detection_mode": self.collision_detection_mode,
            "mass": self.mass,
            "linear_damping": self.linear_damping,
            "angular_damping": self.angular_damping,
            "angular_velocity": self.angular_velocity,
            "inertia": self.inertia,
            "center_of_mass_x": self.center_of_mass_x,
            "center_of_mass_y": self.center_of_mass_y,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RigidBody":
        """Crea un RigidBody desde un diccionario."""
        has_explicit_freeze = "freeze_x" in data or "freeze_y" in data
        component = cls(
            velocity_x=data.get("velocity_x", 0.0),
            velocity_y=data.get("velocity_y", 0.0),
            gravity_scale=data.get("gravity_scale", 1.0),
            is_grounded=data.get("is_grounded", False),
            body_type=data.get("body_type", "dynamic"),
            simulated=data.get("simulated", True),
            freeze_x=data.get("freeze_x", False),
            freeze_y=data.get("freeze_y", False),
            use_full_kinematic_contacts=data.get("use_full_kinematic_contacts", False),
            collision_detection_mode=data.get("collision_detection_mode", "discrete"),
            constraints=data.get("constraints") if not has_explicit_freeze else None,
            mass=data.get("mass", 1.0),
            linear_damping=data.get("linear_damping", 0.0),
            angular_damping=data.get("angular_damping", 0.0),
            angular_velocity=data.get("angular_velocity", 0.0),
            inertia=data.get("inertia", 1.0),
            center_of_mass_x=data.get("center_of_mass_x", 0.0),
            center_of_mass_y=data.get("center_of_mass_y", 0.0),
        )
        component.enabled = data.get("enabled", True)
        return component

    @classmethod
    def normalize_constraints(cls, constraints: Any) -> list[str]:
        if constraints is None:
            return []
        if isinstance(constraints, str):
            candidates = [constraints]
        elif isinstance(constraints, list):
            candidates = constraints
        else:
            return []

        freeze_x = False
        freeze_y = False
        for value in candidates:
            name = str(value).strip()
            if not name:
                continue
            if name == "FreezePosition":
                freeze_x = True
                freeze_y = True
            elif name == "FreezePositionX":
                freeze_x = True
            elif name == "FreezePositionY":
                freeze_y = True
            elif name == "None":
                freeze_x = False
                freeze_y = False
        return cls.constraints_from_freeze(freeze_x, freeze_y)

    @classmethod
    def constraints_from_freeze(cls, freeze_x: bool, freeze_y: bool) -> list[str]:
        if freeze_x and freeze_y:
            return ["FreezePositionX", "FreezePositionY"]
        if freeze_x:
            return ["FreezePositionX"]
        if freeze_y:
            return ["FreezePositionY"]
        return ["None"]

    def apply_force(self, force_x: float, force_y: float) -> None:
        """Aplica una fuerza continua al centro de masa. Se acumula y se aplica en el step de física.
        Adaptado de Godot RigidBody2D.apply_force()."""
        self._force_buffer_x += force_x
        self._force_buffer_y += force_y

    def apply_impulse(self, impulse_x: float, impulse_y: float) -> None:
        """Aplica un impulso instantáneo al centro de masa. Cambia la velocidad inmediatamente.
        Adaptado de Godot RigidBody2D.apply_impulse()."""
        self._impulse_buffer_x += impulse_x
        self._impulse_buffer_y += impulse_y

    def apply_torque(self, torque: float) -> None:
        """Aplica torque angular. Se acumula y se aplica en el step de física."""
        self._torque_buffer += torque

    def _clear_force_buffers(self) -> None:
        """Limpia los buffers de fuerza (llamado por PhysicsSystem al final del step)."""
        self._force_buffer_x = 0.0
        self._force_buffer_y = 0.0
        self._torque_buffer = 0.0
        self._impulse_buffer_x = 0.0
        self._impulse_buffer_y = 0.0
