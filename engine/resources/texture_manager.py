"""
engine/resources/texture_manager.py - Gestor de texturas

PROPÓSITO:
    Centraliza la carga de texturas para evitar duplicados.
    Mantiene una caché de texturas ya cargadas.

DEPENDENCIAS:
    - pyray: Para cargar texturas con Raylib

EJEMPLO DE USO:
    manager = TextureManager()
    texture = manager.load("assets/player.png")
    # La segunda carga retorna la misma textura (cacheada)
    texture2 = manager.load("assets/player.png")
    
    # Liberar recursos al final
    manager.unload_all()
"""

import pyray as rl
from typing import Dict


class TextureManager:
    """
    Gestor centralizado de texturas con caché.
    
    Evita cargar la misma textura múltiples veces.
    Debe llamarse unload_all() antes de cerrar la ventana.
    """
    
    def __init__(self) -> None:
        """Inicializa el gestor con caché vacía."""
        self._cache: Dict[str, rl.Texture] = {}
    
    def load(self, path: str) -> rl.Texture:
        """
        Carga una textura desde archivo o retorna la cacheada.
        
        Args:
            path: Ruta relativa al archivo de imagen
            
        Returns:
            Textura de Raylib cargada
        """
        # Si ya está en caché, retornarla
        if path in self._cache:
            return self._cache[path]
        
        # Cargar nueva textura
        texture = rl.load_texture(path)
        
        # Verificar que se cargó correctamente
        if texture.id == 0:
            print(f"[WARNING] No se pudo cargar textura: {path}")
        
        # Guardar en caché
        self._cache[path] = texture
        return texture
    
    def unload(self, path: str) -> None:
        """
        Descarga una textura específica de memoria.
        
        Args:
            path: Ruta de la textura a descargar
        """
        if path in self._cache:
            rl.unload_texture(self._cache[path])
            del self._cache[path]
    
    def unload_all(self) -> None:
        """Descarga todas las texturas de la caché."""
        for texture in self._cache.values():
            rl.unload_texture(texture)
        self._cache.clear()
    
    def is_loaded(self, path: str) -> bool:
        """Verifica si una textura ya está cargada."""
        return path in self._cache
    
    def get_loaded_count(self) -> int:
        """Retorna el número de texturas cargadas."""
        return len(self._cache)
