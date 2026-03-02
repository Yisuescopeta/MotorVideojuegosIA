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
    from engine.config import GRAVITY_DEFAULT
    physics = PhysicsSystem(gravity=GRAVITY_DEFAULT)
    physics.update(world, delta_time)
"""

from engine.ecs.world import World
from engine.components.transform import Transform
from engine.components.rigidbody import RigidBody
from engine.config import GRAVITY_DEFAULT, GROUND_Y_TEMP


class PhysicsSystem:
    """
    Sistema que aplica física básica (gravedad y movimiento).
    
    Usa integración Euler simple:
    velocity += gravity * dt
    position += velocity * dt
    """
    
    def __init__(self, gravity: float = GRAVITY_DEFAULT) -> None:
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
            if transform.y > GROUND_Y_TEMP:
                transform.y = GROUND_Y_TEMP
                rigidbody.velocity_y = 0
                rigidbody.is_grounded = True
            else:
                rigidbody.is_grounded = False
