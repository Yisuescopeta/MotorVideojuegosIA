"""
engine/systems/physics_system.py - Sistema de física

PROPÓSITO:
    Aplica física básica a entidades con RigidBody:
    - Gravedad
    - Integración de velocidad (Euler)
    - Actualización de posición

DEPENDENCIAS:
    - Transform: Para modificar la posición
    - RigidBody: Para leer velocidad y gravedad

EJEMPLO DE USO:
    physics = PhysicsSystem(gravity=980)
    physics.update(world, delta_time)
"""

from engine.ecs.world import World
from engine.components.transform import Transform
from engine.components.rigidbody import RigidBody


class PhysicsSystem:
    """
    Sistema que aplica física básica (gravedad y movimiento).
    
    Usa integración Euler simple:
    velocity += gravity * dt
    position += velocity * dt
    """
    
    # Gravedad por defecto (píxeles/segundo²)
    DEFAULT_GRAVITY: float = 980.0
    
    def __init__(self, gravity: float = DEFAULT_GRAVITY) -> None:
        """
        Inicializa el sistema de física.
        
        Args:
            gravity: Aceleración de gravedad (px/s²)
        """
        self.gravity: float = gravity
    
    def update(self, world: World, delta_time: float) -> None:
        """
        Actualiza la física de todas las entidades con RigidBody.
        
        Args:
            world: Mundo con las entidades
            delta_time: Tiempo desde el último frame (segundos)
        """
        # Obtener entidades con Transform y RigidBody
        entities = world.get_entities_with(Transform, RigidBody)
        
        for entity in entities:
            transform = entity.get_component(Transform)
            rigidbody = entity.get_component(RigidBody)
            
            if transform is None or rigidbody is None:
                continue
            
            # Aplicar gravedad (solo si no está en el suelo)
            if not rigidbody.is_grounded:
                rigidbody.velocity_y += self.gravity * rigidbody.gravity_scale * delta_time
            
            # Integración Euler: actualizar posición
            transform.x += rigidbody.velocity_x * delta_time
            transform.y += rigidbody.velocity_y * delta_time
            
            # Límite simple de suelo (temporal - para testing)
            # En el futuro esto lo manejará el CollisionSystem
            ground_y = 550.0  # Suelo temporal
            if transform.y > ground_y:
                transform.y = ground_y
                rigidbody.velocity_y = 0
                rigidbody.is_grounded = True
            else:
                rigidbody.is_grounded = False
