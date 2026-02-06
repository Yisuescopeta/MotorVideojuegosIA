"""
engine/debug/timeline.py - Historial de estados (Snapshots)

PROPÓSITO:
    Gestiona una colección ordenada de Snapshots.
    Permite grabar nuevos estados y recuperar estados pasados.

FUNCIONALIDAD:
    - Lista de snapshots (historial)
    - Límite de capacidad (opcional, por defecto sin límite estricto en MVP)
    - Recuperación por índice
"""

from typing import List, Optional
from engine.ecs.world import World
from engine.debug.snapshot import Snapshot

class Timeline:
    """
    Gestiona el historial de ejecución del juego.
    """
    
    def __init__(self, capacity: int = 1000) -> None:
        """
        Inicializa la línea de tiempo.
        
        Args:
            capacity: Número máximo de snapshots a guardar (FIFO)
        """
        self.capacity: int = capacity
        self.snapshots: List[Snapshot] = []
        
    def add_snapshot(self, world: World, frame: int, time: float) -> None:
        """
        Captura y guarda el estado actual del mundo.
        
        Args:
            world: Mundo a capturar
            frame: Número de frame actual
            time: Tiempo de simulación
        """
        snapshot = Snapshot(world, frame, time)
        self.snapshots.append(snapshot)
        
        # Mantener capacidad
        if len(self.snapshots) > self.capacity:
            self.snapshots.pop(0)
            
    def get_snapshot(self, index: int) -> Optional[Snapshot]:
        """
        Obtiene un snapshot por su índice en el historial.
        
        Args:
            index: Índice (puede ser negativo para acceso desde el final)
            
        Returns:
            Snapshot o None si el índice es inválido
        """
        try:
            return self.snapshots[index]
        except IndexError:
            return None
            
    def get_latest_snapshot(self) -> Optional[Snapshot]:
        """Retorna el último snapshot guardado."""
        if not self.snapshots:
            return None
        return self.snapshots[-1]
        
    def clear(self) -> None:
        """Borra todo el historial."""
        self.snapshots.clear()
        
    def count(self) -> int:
        """Retorna número de snapshots guardados."""
        return len(self.snapshots)
