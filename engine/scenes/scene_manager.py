"""
engine/scenes/scene_manager.py - Gestor de escenas

PROPÓSITO:
    Gestiona la Scene actual y controla la creación de
    World (EDIT) y RuntimeWorld (PLAY).

FLUJO:
    load_scene(data) → Scene almacenada
    get_edit_world() → World desde Scene (editable)
    enter_play() → RuntimeWorld (copia)
    exit_play() → World restaurado desde Scene

EJEMPLO:
    manager = SceneManager(registry)
    manager.load_scene(level_data)
    
    # EDIT
    world = manager.get_edit_world()
    
    # PLAY
    runtime = manager.enter_play()
    
    # STOP
    world = manager.exit_play()
"""

from typing import Any, Dict, Optional, TYPE_CHECKING

from engine.scenes.scene import Scene

if TYPE_CHECKING:
    from engine.ecs.world import World
    from engine.levels.component_registry import ComponentRegistry


class SceneManager:
    """
    Gestor de escenas y transiciones EDIT/PLAY.
    
    Responsabilidades:
    - Almacenar la Scene actual
    - Crear World para EDIT
    - Crear RuntimeWorld para PLAY
    - Restaurar World al salir de PLAY
    """
    
    def __init__(self, registry: "ComponentRegistry") -> None:
        """
        Inicializa el gestor de escenas.
        
        Args:
            registry: Registro de componentes
        """
        self._registry = registry
        self._scene: Optional[Scene] = None
        self._edit_world: Optional["World"] = None
        self._runtime_world: Optional["World"] = None
        self._is_playing: bool = False
    
    @property
    def current_scene(self) -> Optional[Scene]:
        """Escena actual."""
        return self._scene
    
    @property
    def scene_name(self) -> str:
        """Nombre de la escena actual."""
        return self._scene.name if self._scene else "Sin escena"
    
    @property
    def is_playing(self) -> bool:
        """True si está en modo PLAY."""
        return self._is_playing
    
    @property
    def active_world(self) -> Optional["World"]:
        """World activo según el estado actual."""
        if self._is_playing:
            return self._runtime_world
        return self._edit_world
    
    def load_scene(self, data: Dict[str, Any]) -> "World":
        """
        Carga una escena desde datos JSON.
        
        Args:
            data: Datos del nivel
            
        Returns:
            World creado desde la escena
        """
        self._scene = Scene.from_dict(data)
        self._edit_world = self._scene.create_world(self._registry)
        self._runtime_world = None
        self._is_playing = False
        
        print(f"[INFO] SceneManager: escena '{self._scene.name}' cargada")
        return self._edit_world
    
    def get_edit_world(self) -> Optional["World"]:
        """Obtiene el World de edición."""
        return self._edit_world
    
    def enter_play(self) -> Optional["World"]:
        """
        Entra en modo PLAY creando RuntimeWorld.
        
        Returns:
            RuntimeWorld (copia del World)
        """
        if self._edit_world is None:
            print("[WARNING] SceneManager: no hay world para play")
            return None
        
        # Crear copia del World
        self._runtime_world = self._edit_world.clone()
        self._is_playing = True
        
        print(f"[INFO] SceneManager: PLAY (RuntimeWorld con {self._runtime_world.entity_count()} entidades)")
        return self._runtime_world
    
    def exit_play(self) -> Optional["World"]:
        """
        Sale de modo PLAY y restaura el World original.
        
        Returns:
            World restaurado desde Scene
        """
        if self._scene is None:
            return None
        
        # Descartar RuntimeWorld
        self._runtime_world = None
        self._is_playing = False
        
        # Restaurar World desde Scene
        self._edit_world = self._scene.create_world(self._registry)
        
        print(f"[INFO] SceneManager: EDIT restaurado ({self._edit_world.entity_count()} entidades)")
        return self._edit_world
    
    def reload_scene(self) -> Optional["World"]:
        """
        Recarga la escena actual desde los datos originales.
        
        Returns:
            World recreado
        """
        if self._scene is None:
            return None
        
        self._runtime_world = None
        self._is_playing = False
        self._edit_world = self._scene.create_world(self._registry)
        
        print(f"[INFO] SceneManager: escena recargada")
        return self._edit_world
