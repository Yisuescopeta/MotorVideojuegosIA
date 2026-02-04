"""
engine/systems/render_system.py - Sistema de renderizado

PROPÓSITO:
    Dibuja todas las entidades que tienen un componente Transform.
    Soporta: Sprite estático, Animator (sprite sheet), o placeholder.

DEPENDENCIAS:
    - Transform: Requiere este componente para posición
    - Sprite: Opcional, para dibujar texturas estáticas
    - Animator: Opcional, para dibujar animaciones de sprite sheet
    - Collider: Opcional, para debug de colisiones
    - TextureManager: Para cargar texturas

PRIORIDAD DE RENDERIZADO:
    1. Si tiene Animator con sprite_sheet -> dibujar frame animado
    2. Si tiene Sprite con texture_path -> dibujar textura estática
    3. Si no tiene ninguno -> dibujar placeholder

EJEMPLO DE USO:
    render_system = RenderSystem()
    render_system.render(world)
"""

import pyray as rl

from engine.ecs.world import World
from engine.ecs.entity import Entity
from engine.components.transform import Transform
from engine.components.sprite import Sprite
from engine.components.collider import Collider
from engine.components.animator import Animator
from engine.resources.texture_manager import TextureManager


class RenderSystem:
    """
    Sistema que renderiza entidades con Transform.
    
    Soporta múltiples modos de renderizado:
    - Animator: Sprite sheet animado
    - Sprite: Textura estática
    - Placeholder: Rectángulo de color
    """
    
    # Configuración del placeholder visual
    PLACEHOLDER_WIDTH: int = 32
    PLACEHOLDER_HEIGHT: int = 32
    PLACEHOLDER_COLOR = rl.SKYBLUE
    
    # Configuración de debug
    DEBUG_DRAW_COLLIDERS: bool = True
    COLLIDER_COLOR = rl.Color(0, 255, 0, 100)
    
    def __init__(self) -> None:
        """Inicializa el sistema de renderizado."""
        self._texture_manager: TextureManager = TextureManager()
    
    def render(self, world: World) -> None:
        """
        Renderiza todas las entidades con Transform.
        
        Args:
            world: El mundo que contiene las entidades
        """
        entities = world.get_entities_with(Transform)
        
        for entity in entities:
            transform = entity.get_component(Transform)
            
            if transform is None:
                continue
            
            # Renderizar según componentes disponibles
            self._render_entity(entity, transform)
            
            # Dibujar collider en modo debug
            if self.DEBUG_DRAW_COLLIDERS:
                collider = entity.get_component(Collider)
                if collider is not None:
                    self._draw_collider(transform, collider)
    
    def _render_entity(self, entity: Entity, transform: Transform) -> None:
        """
        Decide cómo renderizar una entidad según sus componentes.
        
        Prioridad:
        1. Animator (sprite sheet animado)
        2. Sprite (textura estática)
        3. Placeholder (rectángulo)
        """
        animator = entity.get_component(Animator)
        sprite = entity.get_component(Sprite)
        
        # Prioridad 1: Animator
        if animator is not None and animator.sprite_sheet:
            self._draw_animated_sprite(transform, animator)
        # Prioridad 2: Sprite estático
        elif sprite is not None and sprite.texture_path:
            self._draw_sprite(transform, sprite)
        # Prioridad 3: Placeholder
        else:
            self._draw_placeholder(entity.name, transform)
    
    def _draw_animated_sprite(self, transform: Transform, animator: Animator) -> None:
        """
        Dibuja un frame de sprite sheet animado.
        
        Args:
            transform: Componente de posición
            animator: Componente de animación
        """
        # Cargar textura del sprite sheet
        texture = self._texture_manager.load(animator.sprite_sheet)
        
        if texture.id == 0:
            return
        
        # Calcular número de columnas en el sprite sheet
        sheet_columns = texture.width // animator.frame_width
        if sheet_columns <= 0:
            sheet_columns = 1
        
        # Obtener rectángulo de origen del frame actual
        src_x, src_y, src_w, src_h = animator.get_source_rect(sheet_columns)
        
        # Aplicar escala del Transform
        dest_w = int(animator.frame_width * transform.scale_x)
        dest_h = int(animator.frame_height * transform.scale_y)
        
        # Calcular posición (centrado)
        dest_x = transform.x - dest_w / 2
        dest_y = transform.y - dest_h / 2
        
        # Crear rectángulos
        source_rect = rl.Rectangle(src_x, src_y, src_w, src_h)
        dest_rect = rl.Rectangle(dest_x, dest_y, dest_w, dest_h)
        
        # Dibujar frame
        rl.draw_texture_pro(
            texture,
            source_rect,
            dest_rect,
            rl.Vector2(0, 0),
            transform.rotation,
            rl.WHITE
        )
        
        # Debug: mostrar estado de animación
        state_text = f"{animator.current_state}[{animator.current_frame}]"
        rl.draw_text(state_text, int(dest_x), int(dest_y - 15), 10, rl.YELLOW)
    
    def _draw_sprite(self, transform: Transform, sprite: Sprite) -> None:
        """
        Dibuja una textura estática en la posición del Transform.
        
        Args:
            transform: Componente de posición
            sprite: Componente de sprite
        """
        texture = self._texture_manager.load(sprite.texture_path)
        
        if texture.id == 0:
            return
        
        # Calcular dimensiones
        width = sprite.width if sprite.width > 0 else texture.width
        height = sprite.height if sprite.height > 0 else texture.height
        
        # Aplicar escala del Transform
        width = int(width * transform.scale_x)
        height = int(height * transform.scale_y)
        
        # Calcular posición considerando origen
        dest_x = transform.x - (width * sprite.origin_x)
        dest_y = transform.y - (height * sprite.origin_y)
        
        # Preparar rectángulos de origen y destino
        source_width = texture.width if not sprite.flip_x else -texture.width
        source_height = texture.height if not sprite.flip_y else -texture.height
        
        source_rect = rl.Rectangle(0, 0, source_width, source_height)
        dest_rect = rl.Rectangle(dest_x, dest_y, width, height)
        
        # Color de tinte
        tint = rl.Color(*sprite.tint)
        
        # Dibujar textura
        rl.draw_texture_pro(
            texture,
            source_rect,
            dest_rect,
            rl.Vector2(0, 0),
            transform.rotation,
            tint
        )
    
    def _draw_placeholder(self, name: str, transform: Transform) -> None:
        """
        Dibuja un rectángulo placeholder para entidades sin sprite.
        
        Args:
            name: Nombre de la entidad
            transform: Componente de posición
        """
        width = int(self.PLACEHOLDER_WIDTH * transform.scale_x)
        height = int(self.PLACEHOLDER_HEIGHT * transform.scale_y)
        
        rect_x = int(transform.x - width / 2)
        rect_y = int(transform.y - height / 2)
        
        rl.draw_rectangle(rect_x, rect_y, width, height, self.PLACEHOLDER_COLOR)
        rl.draw_text(name, rect_x, rect_y - 15, 10, rl.WHITE)
    
    def _draw_collider(self, transform: Transform, collider: Collider) -> None:
        """
        Dibuja el área de colisión (solo para debug).
        
        Args:
            transform: Componente de posición
            collider: Componente de colisión
        """
        left, top, right, bottom = collider.get_bounds(transform.x, transform.y)
        
        rl.draw_rectangle_lines(
            int(left),
            int(top),
            int(right - left),
            int(bottom - top),
            rl.GREEN
        )
    
    def cleanup(self) -> None:
        """Libera todas las texturas cargadas."""
        self._texture_manager.unload_all()
