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
from engine.components.collider import Collider
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
        solids = [
            entity for entity in world.get_entities_with(Transform, Collider)
            if entity.get_component(Collider) is not None and not entity.get_component(Collider).is_trigger
        ]
        
        for entity in entities:
            transform = entity.get_component(Transform)
            rigidbody = entity.get_component(RigidBody)
            
            if transform is None or rigidbody is None:
                continue
            
            collider = entity.get_component(Collider)

            # Aplicar gravedad (solo si no está en el suelo)
            if not rigidbody.is_grounded:
                rigidbody.velocity_y += self.gravity * rigidbody.gravity_scale * delta_time

            transform.x += rigidbody.velocity_x * delta_time
            if collider is not None and collider.enabled:
                self._resolve_horizontal(world, entity, transform, rigidbody, collider, solids)

            transform.y += rigidbody.velocity_y * delta_time
            rigidbody.is_grounded = False
            if collider is not None and collider.enabled:
                self._resolve_vertical(world, entity, transform, rigidbody, collider, solids)
                if not rigidbody.is_grounded:
                    rigidbody.is_grounded = self._has_ground_support(entity, transform, collider, solids)

            if not rigidbody.is_grounded and transform.y > GROUND_Y_TEMP:
                transform.y = GROUND_Y_TEMP
                rigidbody.velocity_y = 0
                rigidbody.is_grounded = True

    def _resolve_horizontal(
        self,
        world: World,
        entity,
        transform: Transform,
        rigidbody: RigidBody,
        collider: Collider,
        solids: list,
    ) -> None:
        left, top, right, bottom = collider.get_bounds(transform.x, transform.y)
        for other in solids:
            if other.id == entity.id:
                continue
            other_transform = other.get_component(Transform)
            other_collider = other.get_component(Collider)
            if other_transform is None or other_collider is None or not other_collider.enabled:
                continue
            o_left, o_top, o_right, o_bottom = other_collider.get_bounds(other_transform.x, other_transform.y)
            overlap_y = top < o_bottom and bottom > o_top
            overlap_x = left < o_right and right > o_left
            if not overlap_x or not overlap_y:
                continue
            if rigidbody.velocity_x > 0:
                transform.x -= right - o_left
            elif rigidbody.velocity_x < 0:
                transform.x += o_right - left
            rigidbody.velocity_x = 0.0
            left, top, right, bottom = collider.get_bounds(transform.x, transform.y)

    def _resolve_vertical(
        self,
        world: World,
        entity,
        transform: Transform,
        rigidbody: RigidBody,
        collider: Collider,
        solids: list,
    ) -> None:
        left, top, right, bottom = collider.get_bounds(transform.x, transform.y)
        for other in solids:
            if other.id == entity.id:
                continue
            other_transform = other.get_component(Transform)
            other_collider = other.get_component(Collider)
            if other_transform is None or other_collider is None or not other_collider.enabled:
                continue
            o_left, o_top, o_right, o_bottom = other_collider.get_bounds(other_transform.x, other_transform.y)
            overlap_y = top < o_bottom and bottom > o_top
            overlap_x = left < o_right and right > o_left
            if not overlap_x or not overlap_y:
                continue
            if rigidbody.velocity_y > 0:
                transform.y -= bottom - o_top
                rigidbody.is_grounded = True
            elif rigidbody.velocity_y < 0:
                transform.y += o_bottom - top
            rigidbody.velocity_y = 0.0
            left, top, right, bottom = collider.get_bounds(transform.x, transform.y)

    def _has_ground_support(
        self,
        entity,
        transform: Transform,
        collider: Collider,
        solids: list,
    ) -> bool:
        left, top, right, bottom = collider.get_bounds(transform.x, transform.y)
        probe_top = bottom
        probe_bottom = bottom + 1.0
        for other in solids:
            if other.id == entity.id:
                continue
            other_transform = other.get_component(Transform)
            other_collider = other.get_component(Collider)
            if other_transform is None or other_collider is None or not other_collider.enabled:
                continue
            o_left, o_top, o_right, o_bottom = other_collider.get_bounds(other_transform.x, other_transform.y)
            overlap_x = left < o_right and right > o_left
            overlap_y = probe_top <= o_bottom and probe_bottom >= o_top
            if overlap_x and overlap_y:
                return True
        return False
