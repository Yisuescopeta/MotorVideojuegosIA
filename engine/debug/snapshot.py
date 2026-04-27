"""
engine/debug/snapshot.py - Captura de estado del juego

PROPÓSITO:
    Almacena una copia completa del estado del World en un frame específico.
    Se usa para funciones de replay, time-travel, y debugging.

FUNCIONALIDAD:
    - Captura el estado usando World.clone()
    - Almacena timestamp y frame count
    - Permite restaurar el estado

DEPENDENCIAS:
    - World: Debe implementar clone() correctamente
"""

from engine.ecs.world import World


class Snapshot:
    """
    Representa el estado del juego en un momento específico.
    """

    def __init__(self, world: World, frame: int, time: float) -> None:
        """
        Crea un snapshot del mundo actual.

        Args:
            world: El mundo a capturar (se clonará)
            frame: Número de frame actual
            time: Tiempo acumulado de simulación
        """
        self.frame: int = frame
        self.time: float = time
        # Creamos una copia profunda del mundo para aislar el estado
        self.world_state: World = world.clone()

    def restore(self) -> World:
        """
        Devuelve una COPIA del estado guardado.

        IMPORTANTE: Devolvemos una copia (clone) del snapshot,
        no el snapshot mismo, para que si se modifica el mundo restaurado
        no se corrompa el historial guardado en el snapshot.

        Returns:
            Nuevo World con el estado de este snapshot
        """
        return self.world_state.clone()
