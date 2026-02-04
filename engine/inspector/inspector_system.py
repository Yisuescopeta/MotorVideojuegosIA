"""
engine/inspector/inspector_system.py - Sistema de inspector visual en tiempo real

PROPÓSITO:
    Renderiza un panel lateral que muestra el estado de todas las
    entidades y sus componentes. Solo lectura, sin edición.

FUNCIONALIDADES:
    - Panel lateral derecho semitransparente
    - Lista de entidades con sus componentes
    - Valores actualizados en tiempo real
    - Scroll vertical con teclas UP/DOWN
    - Toggle con tecla TAB

CONTROLES:
    - TAB: Mostrar/ocultar inspector
    - UP/DOWN: Scroll vertical
    - PAGE_UP/PAGE_DOWN: Scroll rápido

EJEMPLO DE USO:
    inspector = InspectorSystem()
    inspector.render(world)  # Llamar cada frame después de render
"""

import pyray as rl
from typing import Any, List, Tuple

from engine.ecs.world import World
from engine.ecs.entity import Entity
from engine.ecs.component import Component


class InspectorSystem:
    """
    Sistema de inspector visual para depuración.
    
    Muestra un panel con información de todas las entidades
    y sus componentes en tiempo real.
    """
    
    # Configuración del panel
    PANEL_WIDTH: int = 280
    PANEL_MARGIN: int = 10
    PANEL_PADDING: int = 8
    PANEL_BG_COLOR = rl.Color(20, 20, 30, 220)
    
    # Configuración de texto
    FONT_SIZE: int = 10
    LINE_HEIGHT: int = 14
    TITLE_SIZE: int = 14
    
    # Colores
    TITLE_COLOR = rl.Color(100, 200, 255, 255)
    ENTITY_COLOR = rl.Color(255, 220, 100, 255)
    COMPONENT_COLOR = rl.Color(150, 255, 150, 255)
    PROPERTY_COLOR = rl.Color(200, 200, 200, 255)
    VALUE_COLOR = rl.Color(255, 255, 255, 255)
    SCROLL_COLOR = rl.Color(100, 100, 100, 150)
    
    def __init__(self) -> None:
        """Inicializa el inspector."""
        self.visible: bool = True
        self.scroll_offset: int = 0
        self.max_scroll: int = 0
        self._toggle_cooldown: float = 0.0
    
    def update(self, delta_time: float) -> None:
        """
        Actualiza el estado del inspector (input).
        
        Args:
            delta_time: Tiempo desde el último frame
        """
        # Cooldown para toggle
        if self._toggle_cooldown > 0:
            self._toggle_cooldown -= delta_time
        
        # Toggle con TAB
        if rl.is_key_pressed(rl.KEY_TAB) and self._toggle_cooldown <= 0:
            self.visible = not self.visible
            self._toggle_cooldown = 0.2
        
        if not self.visible:
            return
        
        # Scroll con flechas
        scroll_speed = 3
        if rl.is_key_down(rl.KEY_DOWN):
            self.scroll_offset = min(self.scroll_offset + scroll_speed, self.max_scroll)
        if rl.is_key_down(rl.KEY_UP):
            self.scroll_offset = max(self.scroll_offset - scroll_speed, 0)
        
        # Scroll rápido con PAGE_UP/PAGE_DOWN
        page_speed = 20
        if rl.is_key_pressed(rl.KEY_PAGE_DOWN):
            self.scroll_offset = min(self.scroll_offset + page_speed, self.max_scroll)
        if rl.is_key_pressed(rl.KEY_PAGE_UP):
            self.scroll_offset = max(self.scroll_offset - page_speed, 0)
    
    def render(self, world: World, screen_width: int, screen_height: int) -> None:
        """
        Renderiza el panel del inspector.
        
        Args:
            world: Mundo con las entidades a inspeccionar
            screen_width: Ancho de la ventana
            screen_height: Alto de la ventana
        """
        if not self.visible:
            # Mostrar indicador de que está oculto
            rl.draw_text(
                "[TAB] Inspector",
                screen_width - 120, 10, 12, rl.GRAY
            )
            return
        
        # Calcular posición del panel
        panel_x = screen_width - self.PANEL_WIDTH - self.PANEL_MARGIN
        panel_y = self.PANEL_MARGIN
        panel_height = screen_height - (self.PANEL_MARGIN * 2)
        
        # Dibujar fondo del panel
        rl.draw_rectangle(
            panel_x, panel_y,
            self.PANEL_WIDTH, panel_height,
            self.PANEL_BG_COLOR
        )
        
        # Dibujar borde
        rl.draw_rectangle_lines(
            panel_x, panel_y,
            self.PANEL_WIDTH, panel_height,
            rl.Color(80, 80, 100, 255)
        )
        
        # Área de contenido (con clipping manual via posición)
        content_x = panel_x + self.PANEL_PADDING
        content_y = panel_y + self.PANEL_PADDING
        content_width = self.PANEL_WIDTH - (self.PANEL_PADDING * 2)
        content_height = panel_height - (self.PANEL_PADDING * 2)
        
        # Generar líneas de contenido
        lines = self._generate_content_lines(world)
        
        # Calcular scroll máximo
        total_height = len(lines) * self.LINE_HEIGHT
        visible_height = content_height - self.TITLE_SIZE - 10
        self.max_scroll = max(0, total_height - visible_height)
        
        # Dibujar título
        rl.draw_text(
            "INSPECTOR",
            content_x, content_y,
            self.TITLE_SIZE, self.TITLE_COLOR
        )
        
        # Info de scroll
        scroll_info = f"[UP/DOWN] Scroll ({self.scroll_offset}/{self.max_scroll})"
        rl.draw_text(
            scroll_info,
            content_x, content_y + self.TITLE_SIZE + 2,
            8, rl.GRAY
        )
        
        # Área de entidades
        entities_y = content_y + self.TITLE_SIZE + 16
        
        # Dibujar líneas con scroll
        current_y = entities_y - self.scroll_offset
        
        for line_text, line_color, indent in lines:
            # Solo dibujar si está en el área visible
            if current_y >= entities_y - self.LINE_HEIGHT and current_y < panel_y + panel_height - self.PANEL_PADDING:
                rl.draw_text(
                    line_text,
                    content_x + indent,
                    int(current_y),
                    self.FONT_SIZE,
                    line_color
                )
            current_y += self.LINE_HEIGHT
        
        # Dibujar indicador de scroll
        if self.max_scroll > 0:
            self._draw_scrollbar(
                panel_x + self.PANEL_WIDTH - 6,
                entities_y,
                4,
                visible_height,
                self.scroll_offset,
                self.max_scroll
            )
    
    def _generate_content_lines(self, world: World) -> List[Tuple[str, rl.Color, int]]:
        """
        Genera las líneas de texto para mostrar.
        
        Returns:
            Lista de tuplas (texto, color, indentación)
        """
        lines: List[Tuple[str, rl.Color, int]] = []
        
        entities = world.get_all_entities()
        
        for entity in entities:
            # Línea de entidad
            lines.append((
                f"[{entity.id}] {entity.name}",
                self.ENTITY_COLOR,
                0
            ))
            
            # Componentes de la entidad
            components = entity.get_all_components()
            
            for component in components:
                # Nombre del componente
                comp_name = type(component).__name__
                lines.append((
                    f"{comp_name}:",
                    self.COMPONENT_COLOR,
                    8
                ))
                
                # Propiedades del componente
                props = self._get_component_properties(component)
                for prop_name, prop_value in props:
                    # Formatear valor
                    value_str = self._format_value(prop_value)
                    lines.append((
                        f"{prop_name}: {value_str}",
                        self.PROPERTY_COLOR,
                        16
                    ))
            
            # Línea vacía entre entidades
            lines.append(("", rl.BLANK, 0))
        
        return lines
    
    def _get_component_properties(self, component: Component) -> List[Tuple[str, Any]]:
        """
        Obtiene las propiedades de un componente usando introspección.
        
        Args:
            component: Componente a inspeccionar
            
        Returns:
            Lista de tuplas (nombre_propiedad, valor)
        """
        props = []
        
        # Usar to_dict si está disponible (más limpio)
        if hasattr(component, 'to_dict'):
            try:
                data = component.to_dict()
                for key, value in data.items():
                    props.append((key, value))
                return props
            except Exception:
                pass
        
        # Fallback: introspección directa
        for attr_name in dir(component):
            # Ignorar atributos privados y métodos
            if attr_name.startswith('_'):
                continue
            if callable(getattr(component, attr_name)):
                continue
            
            try:
                value = getattr(component, attr_name)
                props.append((attr_name, value))
            except Exception:
                pass
        
        return props
    
    def _format_value(self, value: Any) -> str:
        """
        Formatea un valor para mostrar de forma legible.
        
        Args:
            value: Valor a formatear
            
        Returns:
            String formateado
        """
        if isinstance(value, float):
            return f"{value:.1f}"
        elif isinstance(value, bool):
            return "Yes" if value else "No"
        elif isinstance(value, dict):
            return f"{{{len(value)} items}}"
        elif isinstance(value, (list, tuple)):
            if len(value) <= 4:
                return str(value)
            return f"[{len(value)} items]"
        elif isinstance(value, str):
            if len(value) > 20:
                return f'"{value[:17]}..."'
            return f'"{value}"'
        else:
            return str(value)
    
    def _draw_scrollbar(
        self,
        x: int, y: int,
        width: int, height: int,
        scroll: int, max_scroll: int
    ) -> None:
        """Dibuja una barra de scroll vertical."""
        if max_scroll <= 0:
            return
        
        # Fondo de la barra
        rl.draw_rectangle(x, int(y), width, int(height), self.SCROLL_COLOR)
        
        # Calcular posición y tamaño del thumb
        thumb_height = max(20, int(height * height / (height + max_scroll)))
        thumb_y = y + int((height - thumb_height) * scroll / max_scroll)
        
        # Dibujar thumb
        rl.draw_rectangle(
            x, thumb_y,
            width, thumb_height,
            rl.Color(180, 180, 180, 200)
        )
