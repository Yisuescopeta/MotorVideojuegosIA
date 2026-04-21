"""
engine/services/registro_servicios.py - Registro de servicios globales / autoloads

PROPÓSITO:
    Mantener servicios globales accesibles por nombre durante el runtime del motor.
    Soporta dos capas:
    - builtins: servicios globales del motor, persistentes entre sesiones de PLAY.
    - runtime: servicios creados dinámicamente para una sesión de PLAY.

CICLO DE VIDA:
    - Los builtins se registran al inicializar el motor o al cargar un proyecto.
    - Los runtime se registran al entrar en PLAY y se limpian al salir.
    - Todo se limpia al apagar el motor.
"""

from typing import Any


class RegistroServicios:
    """Registro de servicios globales con soporte para built-ins y runtime."""

    def __init__(self) -> None:
        self._builtins: dict[str, Any] = {}
        self._runtime: dict[str, Any] = {}

    def registrar_builtin(self, nombre: str, servicio: Any) -> None:
        """Registra un servicio global persistente entre sesiones de PLAY."""
        self._builtins[nombre] = servicio

    def registrar(self, nombre: str, servicio: Any) -> None:
        """Registra un servicio para la sesión de PLAY actual."""
        self._runtime[nombre] = servicio

    def obtener(self, nombre: str) -> Any | None:
        """Obtiene un servicio por nombre (prioriza runtime sobre builtins)."""
        if nombre in self._runtime:
            return self._runtime[nombre]
        return self._builtins.get(nombre)

    def tiene(self, nombre: str) -> bool:
        """Indica si existe un servicio registrado con el nombre dado."""
        return nombre in self._runtime or nombre in self._builtins

    def desregistrar(self, nombre: str) -> bool:
        """Elimina un servicio runtime. Retorna True si existía."""
        if nombre in self._runtime:
            del self._runtime[nombre]
            return True
        return False

    def desregistrar_builtin(self, nombre: str) -> bool:
        """Elimina un servicio builtin. Retorna True si existía."""
        if nombre in self._builtins:
            del self._builtins[nombre]
            return True
        return False

    def limpiar_runtime(self) -> None:
        """Limpia todos los servicios runtime (al salir de PLAY)."""
        self._runtime.clear()

    def limpiar_todo(self) -> None:
        """Limpia builtins y runtime (al apagar el motor)."""
        self._runtime.clear()
        self._builtins.clear()

    def listar_servicios(self) -> list[str]:
        """Lista todos los nombres de servicios registrados."""
        return sorted(set(self._builtins.keys()) | set(self._runtime.keys()))
