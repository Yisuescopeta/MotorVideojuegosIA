"""
engine/components/collision_filter_2d.py - Componente de filtro de colisión por capas

PROPÓSITO:
    Define capas de colisión y máscara para filtrado de colisiones entre entidades.
    Adaptado del concepto Godot collision_layer/collision_mask pero implementado
    como componente ECS serializable.

REGLAS DE COLISIÓN:
    Dos entidades A y B colisionan si y solo si:
        (A.mask & B.layer) != 0  AND  (B.mask & A.layer) != 0

    Si una entidad NO tiene CollisionFilter2D, colisiona con todo (compatibilidad).

PROPIEDADES:
    - layer (int): Máscara de bits que indica en qué capas está la entidad.
                   Bit 0 = capa 1, bit 1 = capa 2, etc.
                   Default: 1 (solo capa 1).
    - mask (int): Máscara de bits que indica con qué capas esta entidad colisiona.
                  Default: 0xFFFFFFFF (colisiona con todas las capas).

EJEMPLO DE USO:
    # Jugador en capa 1, colisiona con capas 1, 2, 3
    player_filter = CollisionFilter2D(layer=1, mask=0b111)

    # Enemigo en capa 2, colisiona con capa 1
    enemy_filter = CollisionFilter2D(layer=2, mask=1)

    # Colisionan? (player.mask & enemy.layer) = 0b111 & 2 = 2 != 0 ✓
    #             (enemy.mask & player.layer) = 1 & 1 = 1 != 0 ✓ → SÍ

    # Bala en capa 3, colisiona con capa 2
    # Colisiona con jugador? (bullet.mask & player.layer) = 2 & 1 = 0 ✗ → NO

SERIALIZACIÓN JSON:
    {
        "enabled": true,
        "layer": 1,
        "mask": 4294967295
    }
"""

from __future__ import annotations

from typing import Any

from engine.ecs.component import Component

MASK_ALL: int = 0xFFFFFFFF


class CollisionFilter2D(Component):
    """Componente que define capas de colisión y máscara para filtrado.

    Adaptado del concepto Godot collision_layer/collision_mask pero
    implementado como componente ECS serializable.

    - layer: máscara de bits que indica en qué capas está la entidad
    - mask: máscara de bits que indica con qué capas colisiona
    - Regla: colisión ocurre si (A.mask & B.layer) != 0 AND (B.mask & A.layer) != 0
    - Si no hay CollisionFilter2D en una entidad, colisiona con todo (compatibilidad)
    """

    def __init__(self, layer: int = 1, mask: int = MASK_ALL) -> None:
        self.enabled: bool = True
        self.layer: int = int(layer)
        self.mask: int = int(mask)

    def set_layer_bit(self, bit_index: int) -> None:
        """Activa una capa de colisión por índice de bit (0-based).

        Args:
            bit_index: Índice del bit a activar (0 = capa 1, 1 = capa 2, ...).
        """
        self.layer |= 1 << int(bit_index)

    def clear_layer_bit(self, bit_index: int) -> None:
        """Desactiva una capa de colisión por índice de bit (0-based).

        Args:
            bit_index: Índice del bit a desactivar (0 = capa 1, 1 = capa 2, ...).
        """
        self.layer &= ~(1 << int(bit_index))

    def has_layer_bit(self, bit_index: int) -> bool:
        """Verifica si una capa está activa.

        Args:
            bit_index: Índice del bit a verificar (0 = capa 1, 1 = capa 2, ...).

        Returns:
            True si el bit está activo.
        """
        return (self.layer & (1 << int(bit_index))) != 0

    def set_mask_bit(self, bit_index: int) -> None:
        """Activa una capa en la máscara de colisión por índice de bit (0-based).

        Args:
            bit_index: Índice del bit a activar (0 = capa 1, 1 = capa 2, ...).
        """
        self.mask |= 1 << int(bit_index)

    def clear_mask_bit(self, bit_index: int) -> None:
        """Desactiva una capa en la máscara de colisión por índice de bit (0-based).

        Args:
            bit_index: Índice del bit a desactivar (0 = capa 1, 1 = capa 2, ...).
        """
        self.mask &= ~(1 << int(bit_index))

    def has_mask_bit(self, bit_index: int) -> bool:
        """Verifica si una capa está activa en la máscara.

        Args:
            bit_index: Índice del bit a verificar (0 = capa 1, 1 = capa 2, ...).

        Returns:
            True si el bit está activo en la máscara.
        """
        return (self.mask & (1 << int(bit_index))) != 0

    @staticmethod
    def should_collide(
        filter_a: CollisionFilter2D | None,
        filter_b: CollisionFilter2D | None,
    ) -> bool:
        """Determina si dos entidades deben colisionar según sus filtros.

        Si alguna entidad no tiene CollisionFilter2D, colisiona con todo
        (compatibilidad).

        Args:
            filter_a: Filtro de la entidad A, o None.
            filter_b: Filtro de la entidad B, o None.

        Returns:
            True si las entidades deben colisionar.
        """
        if filter_a is None or filter_b is None:
            return True
        return (filter_a.mask & filter_b.layer) != 0 and (filter_b.mask & filter_a.layer) != 0

    def to_dict(self) -> dict[str, Any]:
        """Serializa el componente a diccionario."""
        return {
            "enabled": self.enabled,
            "layer": self.layer,
            "mask": self.mask,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CollisionFilter2D:
        """Crea un CollisionFilter2D desde un diccionario."""
        component = cls(
            layer=data.get("layer", 1),
            mask=data.get("mask", MASK_ALL),
        )
        component.enabled = data.get("enabled", True)
        return component
