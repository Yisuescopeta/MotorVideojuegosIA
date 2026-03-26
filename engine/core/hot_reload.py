"""
engine/core/hot_reload.py - Sistema de recarga en caliente

PROPÓSITO:
    Permite recargar módulos Python en tiempo de ejecución sin cerrar
    el motor. Monitoriza el directorio /scripts para cambios y recarga
    los módulos modificados usando importlib.reload().

FUNCIONALIDAD:
    - Registrar módulos para monitorizar
    - Detectar cambios por timestamp de archivo
    - Recargar módulos con importlib sin crashear
    - Loguear errores de import en consola

EJEMPLO DE USO:
    from engine.core.hot_reload import HotReloadManager

    manager = HotReloadManager("scripts")
    manager.scan_directory()       # Descubrir scripts
    changed = manager.check_for_changes()  # Detectar y recargar
"""

import os
import sys
import importlib
import time
from typing import Dict, List, Optional, Any
from pathlib import Path


class HotReloadManager:
    """
    Gestor de recarga en caliente de módulos Python.
    
    Monitoriza archivos .py en un directorio y los recarga
    automáticamente cuando detecta cambios.
    """
    
    def __init__(self, scripts_dir: str = "scripts") -> None:
        """
        Inicializa el gestor de hot-reload.
        
        Args:
            scripts_dir: Ruta al directorio de scripts a monitorizar
        """
        self.scripts_dir: str = scripts_dir
        self._module_timestamps: Dict[str, float] = {}
        self._loaded_modules: Dict[str, Any] = {}
        self._errors: List[str] = []
        self._last_check_time: float = 0.0
        
        # Asegurar que el directorio de scripts está en sys.path
        abs_dir = os.path.abspath(scripts_dir)
        if abs_dir not in sys.path:
            sys.path.insert(0, abs_dir)
    
    def scan_directory(self) -> int:
        """
        Escanea el directorio de scripts y registra archivos .py.
        
        Returns:
            Número de scripts encontrados
        """
        if not os.path.isdir(self.scripts_dir):
            return 0

        abs_dir = os.path.abspath(self.scripts_dir)
        if abs_dir not in sys.path:
            sys.path.insert(0, abs_dir)
        
        count = 0
        for filepath in Path(self.scripts_dir).rglob("*.py"):
            if filepath.name.startswith("_"):
                continue
            module_name = filepath.relative_to(self.scripts_dir).with_suffix("").as_posix().replace("/", ".")
            mtime = os.path.getmtime(filepath)
            self._module_timestamps[module_name] = mtime
            count += 1
        
        return count
    
    def check_for_changes(self) -> List[str]:
        """
        Comprueba si hay archivos modificados y los recarga.
        
        Returns:
            Lista de nombres de módulos recargados
        """
        if not os.path.isdir(self.scripts_dir):
            return []

        abs_dir = os.path.abspath(self.scripts_dir)
        if abs_dir not in sys.path:
            sys.path.insert(0, abs_dir)
        
        reloaded: List[str] = []
        self._errors.clear()
        
        for filepath_obj in Path(self.scripts_dir).rglob("*.py"):
            if filepath_obj.name.startswith("_"):
                continue
            
            filepath = filepath_obj.as_posix()
            module_name = filepath_obj.relative_to(self.scripts_dir).with_suffix("").as_posix().replace("/", ".")
            
            try:
                current_mtime = os.path.getmtime(filepath)
            except OSError:
                continue
            
            last_mtime = self._module_timestamps.get(module_name, 0)
            
            if current_mtime > last_mtime:
                # Archivo modificado, recargar
                success = self._reload_module(module_name)
                if success:
                    reloaded.append(module_name)
                self._module_timestamps[module_name] = current_mtime
        
        self._last_check_time = time.time()
        return reloaded

    def ensure_module_loaded(self, module_name: str) -> Optional[Any]:
        """
        Garantiza que un modulo este cargado y actualizado antes de usarlo.
        """
        abs_dir = os.path.abspath(self.scripts_dir)
        if abs_dir not in sys.path:
            sys.path.insert(0, abs_dir)

        normalized = module_name.strip().replace("\\", "/")
        if normalized.endswith(".py"):
            normalized = normalized[:-3]
        normalized = normalized.strip("/").replace("/", ".")
        if not normalized:
            return None

        filepath = self._module_filepath(normalized)
        if filepath is None:
            self._errors.append(f"[HOT-RELOAD] Modulo no encontrado: {normalized}")
            return None

        current_mtime = os.path.getmtime(filepath)
        last_mtime = self._module_timestamps.get(normalized, 0.0)
        if normalized not in self._loaded_modules or current_mtime > last_mtime:
            if self._reload_module(normalized):
                self._module_timestamps[normalized] = current_mtime
        return self._loaded_modules.get(normalized)
    
    def _reload_module(self, module_name: str) -> bool:
        """
        Recarga un módulo específico.
        
        Args:
            module_name: Nombre del módulo (sin .py)
            
        Returns:
            True si se recargó exitosamente, False si hubo error
        """
        try:
            if module_name in sys.modules:
                # Recargar módulo existente
                module = importlib.reload(sys.modules[module_name])
                print(f"[HOT-RELOAD] Recargado: {module_name}")
            else:
                # Cargar por primera vez
                module = importlib.import_module(module_name)
                print(f"[HOT-RELOAD] Cargado: {module_name}")
            
            self._loaded_modules[module_name] = module
            
            # Ejecutar hook on_reload si existe
            if hasattr(module, "on_reload"):
                module.on_reload()
            
            return True
            
        except Exception as e:
            error_msg = f"[HOT-RELOAD] Error en {module_name}: {e}"
            print(error_msg)
            self._errors.append(error_msg)
            return False

    def _module_filepath(self, module_name: str) -> Optional[str]:
        filename = module_name.replace(".", os.sep) + ".py"
        filepath = os.path.join(self.scripts_dir, filename)
        if os.path.isfile(filepath):
            return filepath
        return None
    
    def get_module(self, module_name: str) -> Optional[Any]:
        """
        Obtiene un módulo cargado por nombre.
        
        Args:
            module_name: Nombre del módulo
            
        Returns:
            El módulo si está cargado, None en caso contrario
        """
        return self._loaded_modules.get(module_name)
    
    def get_all_modules(self) -> Dict[str, Any]:
        """
        Retorna todos los módulos cargados.
        
        Returns:
            Diccionario de nombre -> módulo
        """
        return dict(self._loaded_modules)
    
    def get_errors(self) -> List[str]:
        """
        Retorna los errores del último check.
        
        Returns:
            Lista de mensajes de error
        """
        return list(self._errors)
    
    @property
    def module_count(self) -> int:
        """Número de módulos registrados."""
        return len(self._module_timestamps)
    
    @property
    def loaded_count(self) -> int:
        """Número de módulos cargados exitosamente."""
        return len(self._loaded_modules)
