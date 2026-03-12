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
import copy

from engine.scenes.scene import Scene
from engine.editor.console_panel import log_info, log_warn, log_err

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
        self._selected_entity_name: Optional[str] = None
        self._dirty: bool = False
        self._edit_world_sync_pending: bool = False
        self._history: Any = None
    
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
    def is_dirty(self) -> bool:
        return self._dirty

    def set_history_manager(self, history: Any) -> None:
        self._history = history
    
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
        self._rebuild_edit_world()
        self._runtime_world = None
        self._is_playing = False
        self._dirty = False
        self._edit_world_sync_pending = False

        log_info(f"SceneManager: Scene '{self._scene.name}' loaded.")
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
            log_warn("SceneManager: no hay world para play")
            return None
        
        # Crear copia del World
        self._selected_entity_name = self._edit_world.selected_entity_name
        self._runtime_world = self._edit_world.clone()
        if (
            self._selected_entity_name
            and self._runtime_world.get_entity_by_name(self._selected_entity_name) is not None
        ):
            self._runtime_world.selected_entity_name = self._selected_entity_name
        self._is_playing = True
        
        log_info(f"SceneManager: PLAY (RuntimeWorld with {self._runtime_world.entity_count()} entities)")
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
        if self._runtime_world is not None:
            self._selected_entity_name = self._runtime_world.selected_entity_name or self._selected_entity_name
        self._runtime_world = None
        self._is_playing = False
        self._edit_world_sync_pending = False
        
        # Restaurar World desde Scene
        self._rebuild_edit_world()
        
        print(f"[INFO] SceneManager: EDIT restaurado ({self._edit_world.entity_count()} entidades)")
        return self._edit_world
    
    def restore_world(self, world: "World") -> None:
        """
        Remplaza el runtime_world actual con uno dado (para Snapshots).
        
        Args:
            world: Mundo restaurado
        """
        if not self._is_playing:
            print("[WARNING] SceneManager.restore_world: solo se puede restaurar en PLAY")
            return
            
        self._runtime_world = world
        print(f"[INFO] SceneManager: World restaurado ({world.entity_count()} entidades)")
    
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
        self._rebuild_edit_world()
        self._dirty = False
        self._edit_world_sync_pending = False
        
        print(f"[INFO] SceneManager: escena recargada")
        return self._edit_world
    
    def apply_edit_to_world(
        self,
        entity_name: str,
        component_name: str,
        property_name: str,
        value: Any
    ) -> bool:
        """
        Aplica una edición a Scene y sincroniza con World.
        
        Solo funciona en modo EDIT (cuando _is_playing es False).
        
        Args:
            entity_name: Nombre de la entidad
            component_name: Nombre del componente
            property_name: Nombre de la propiedad
            value: Nuevo valor
            
        Returns:
            True si se aplicó correctamente
        """
        # Seguridad: no editar durante PLAY
        if self._is_playing:
            print("[WARNING] SceneManager: no se puede editar en PLAY")
            return False
        
        if self._scene is None or self._edit_world is None:
            return False
        self._flush_pending_edit_world()
        before = copy.deepcopy(self._scene.to_dict())
        if not self._scene.update_component(entity_name, component_name, property_name, value):
            return False
        self._rebuild_edit_world()
        self._dirty = True
        self._record_scene_change(f"{entity_name}.{component_name}.{property_name}", before)
        return True

    def update_entity_property(self, entity_name: str, property_name: str, value: Any) -> bool:
        """Actualiza un metadato de entidad y reconstruye el mundo de edicion."""
        if self._is_playing or self._scene is None:
            return False
        self._flush_pending_edit_world()
        before = copy.deepcopy(self._scene.to_dict())
        if not self._scene.update_entity_property(entity_name, property_name, value):
            return False
        self._rebuild_edit_world()
        self._dirty = True
        self._record_scene_change(f"{entity_name}.{property_name}", before)
        return True

    def replace_component_data(self, entity_name: str, component_name: str, component_data: Dict[str, Any]) -> bool:
        """Reemplaza la fuente serializable completa de un componente."""
        if self._is_playing or self._scene is None or self._edit_world is None:
            return False
        self._flush_pending_edit_world()
        before = copy.deepcopy(self._scene.to_dict())
        if not self._scene.replace_component_data(entity_name, component_name, copy.deepcopy(component_data)):
            return False
        self._rebuild_edit_world()
        self._dirty = True
        self._record_scene_change(f"{entity_name}.{component_name}", before)
        return True

    def set_entity_active(self, entity_name: str, active: bool) -> bool:
        """Actualiza el flag serializable `active` de una entidad."""
        return self.update_entity_property(entity_name, "active", active)

    def set_entity_tag(self, entity_name: str, tag: str) -> bool:
        """Actualiza el `tag` serializable de una entidad."""
        return self.update_entity_property(entity_name, "tag", tag)

    def set_entity_layer(self, entity_name: str, layer: str) -> bool:
        """Actualiza el `layer` serializable de una entidad."""
        return self.update_entity_property(entity_name, "layer", layer)

    def create_entity(self, name: str, components: Optional[Dict[str, Dict[str, Any]]] = None) -> bool:
        """Crea una entidad serializable en la escena de edicion."""
        if self._is_playing or self._scene is None:
            return False
        self._flush_pending_edit_world()
        entity_data = {
            "name": name,
            "active": True,
            "tag": "Untagged",
            "layer": "Default",
            "components": components or {"Transform": {"enabled": True, "x": 0.0, "y": 0.0, "rotation": 0.0, "scale_x": 1.0, "scale_y": 1.0}},
        }
        before = copy.deepcopy(self._scene.to_dict())
        if not self._scene.add_entity(entity_data):
            return False
        self._rebuild_edit_world()
        self._dirty = True
        self._record_scene_change(f"create_entity:{name}", before)
        return True

    def create_entity_from_data(self, entity_data: Dict[str, Any]) -> bool:
        """Crea una entidad completa a partir de datos serializables."""
        if self._is_playing or self._scene is None:
            return False
        self._flush_pending_edit_world()
        payload = copy.deepcopy(entity_data)
        payload.setdefault("active", True)
        payload.setdefault("tag", "Untagged")
        payload.setdefault("layer", "Default")
        payload.setdefault("components", {})
        before = copy.deepcopy(self._scene.to_dict())
        if not self._scene.add_entity(payload):
            return False
        self._rebuild_edit_world()
        self._dirty = True
        self._record_scene_change(f"create_entity:{payload.get('name', '')}", before)
        return True

    def remove_entity(self, entity_name: str) -> bool:
        """Elimina una entidad de la escena de edicion."""
        if self._is_playing or self._scene is None:
            return False
        self._flush_pending_edit_world()
        before = copy.deepcopy(self._scene.to_dict())
        if not self._scene.remove_entity(entity_name):
            return False
        self._rebuild_edit_world()
        self._dirty = True
        self._record_scene_change(f"remove_entity:{entity_name}", before)
        return True

    def add_component_to_entity(
        self,
        entity_name: str,
        component_name: str,
        component_data: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Añade un componente a la entidad en la escena de edicion."""
        if self._is_playing or self._scene is None:
            return False
        self._flush_pending_edit_world()
        data = component_data or {"enabled": True}
        before = copy.deepcopy(self._scene.to_dict())
        if not self._scene.add_component(entity_name, component_name, data):
            return False
        self._rebuild_edit_world()
        self._dirty = True
        self._record_scene_change(f"add_component:{entity_name}.{component_name}", before)
        return True

    def remove_component_from_entity(self, entity_name: str, component_name: str) -> bool:
        """Elimina un componente de la entidad y reconstruye el mundo."""
        if self._is_playing or self._scene is None:
            return False
        self._flush_pending_edit_world()
        before = copy.deepcopy(self._scene.to_dict())
        if not self._scene.remove_component(entity_name, component_name):
            return False
        self._rebuild_edit_world()
        self._dirty = True
        self._record_scene_change(f"remove_component:{entity_name}.{component_name}", before)
        return True

    def set_component_enabled(self, entity_name: str, component_name: str, enabled: bool) -> bool:
        """Activa o desactiva un componente sin saltarse la escena serializable."""
        return self.apply_edit_to_world(entity_name, component_name, "enabled", enabled)

    def find_entity_data(self, entity_name: str) -> Optional[Dict[str, Any]]:
        """Devuelve los datos serializados de una entidad de la escena actual."""
        if self._scene is None:
            return None
        self._flush_pending_edit_world()
        return self._scene.find_entity(entity_name)

    def sync_from_edit_world(self, force: bool = False) -> bool:
        """Sincroniza el world visible hacia la escena serializable."""
        if self._is_playing or self._scene is None or self._edit_world is None:
            return False
        if not force and not self._edit_world_sync_pending:
            return False
        self._selected_entity_name = self._edit_world.selected_entity_name
        data = self._edit_world.serialize()
        data["name"] = self._scene.name
        data["rules"] = self._scene.rules_data
        data["feature_metadata"] = self._scene.feature_metadata
        self._scene = Scene(data["name"], data)
        self._edit_world_sync_pending = False
        return True

    def mark_edit_world_dirty(self) -> bool:
        """Marca que el World de edicion fue mutado fuera del modelo Scene."""
        if self._is_playing or self._scene is None or self._edit_world is None:
            return False
        self._dirty = True
        self._edit_world_sync_pending = True
        return True

    def set_selected_entity(self, entity_name: Optional[str]) -> bool:
        """Persiste la seleccion tanto en EDIT como en PLAY sin volverla estado solo visual."""
        self._selected_entity_name = entity_name

        world = self.active_world
        if world is None:
            return False

        if entity_name and world.get_entity_by_name(entity_name) is None:
            return False

        world.selected_entity_name = entity_name
        if self._edit_world is not None and not self._is_playing:
            self._edit_world.selected_entity_name = entity_name
        if self._runtime_world is not None and self._is_playing:
            self._runtime_world.selected_entity_name = entity_name
        return True
        
    def save_scene_to_file(self, path: str) -> bool:
        """
        Guarda la escena actual (estado del Edit World) a disco.
        """
        if self._edit_world is None:
            return False
            
        try:
             import json
             self.sync_from_edit_world(force=True)
             data = self._scene.to_dict() if self._scene is not None else self._edit_world.serialize()
             data["name"] = self._scene.name if self._scene else "Untitled"
             
             with open(path, 'w') as f:
                 json.dump(data, f, indent=4)
                 
             print(f"[SCENE] Guardado exitoso en {path}")
             # Actualizar objeto Scene interno también
             self._scene = Scene(data["name"], data)
             self._rebuild_edit_world()
             self._dirty = False
             self._edit_world_sync_pending = False
             return True
        except Exception as e:
            print(f"[SCENE] Error al guardar en {path}: {e}")
            return False

    def create_new_scene(self, name: str = "New Scene") -> "World":
        """
        Crea una nueva escena vacía.
        
        Args:
            name: Nombre de la nueva escena
            
        Returns:
            Nuevo World editable
        """
        self._scene = Scene(name)
        self._rebuild_edit_world()
        self._runtime_world = None
        self._is_playing = False
        self._dirty = False
        self._edit_world_sync_pending = False
        
        log_info(f"SceneManager: Nueva escena '{name}' creada.")
        return self._edit_world

    def load_scene_from_file(self, path: str) -> Optional["World"]:
        """
        Carga una escena desde un archivo JSON.
        
        Args:
            path: Ruta al archivo .json
            
        Returns:
            World cargado o None si hubo error
        """
        try:
            import json
            with open(path, 'r') as f:
                data = json.load(f)
            return self.load_scene(data)
        except Exception as e:
            log_err(f"SceneManager: Error cargando {path}: {e}")
            return None

    def _rebuild_edit_world(self) -> None:
        """Reconstruye el world de edicion desde la fuente serializable."""
        if self._scene is None:
            self._edit_world = None
            return
        selected_name = self._selected_entity_name
        if selected_name is None and self._edit_world is not None:
            selected_name = self._edit_world.selected_entity_name
        self._edit_world = self._scene.create_world(self._registry)
        if selected_name and self._edit_world.get_entity_by_name(selected_name) is not None:
            self._edit_world.selected_entity_name = selected_name
            self._selected_entity_name = selected_name
        elif self._edit_world is not None:
            self._edit_world.selected_entity_name = None

    def restore_scene_data(self, data: Dict[str, Any]) -> bool:
        if self._is_playing:
            return False
        self._scene = Scene(data.get("name", self.scene_name), copy.deepcopy(data))
        self._rebuild_edit_world()
        self._dirty = True
        self._edit_world_sync_pending = False
        return True

    def clear_dirty(self) -> None:
        self._dirty = False

    def _record_scene_change(self, label: str, before: Dict[str, Any]) -> None:
        if self._history is None or self._scene is None:
            return
        after = copy.deepcopy(self._scene.to_dict())
        self._history.push(
            label=label,
            undo=lambda: self.restore_scene_data(before),
            redo=lambda: self.restore_scene_data(after),
        )

    def _flush_pending_edit_world(self) -> None:
        if self._edit_world_sync_pending:
            self.sync_from_edit_world(force=True)
