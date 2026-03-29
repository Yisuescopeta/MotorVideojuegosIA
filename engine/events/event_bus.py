"""
engine/events/event_bus.py - Bus central de eventos

PROPÃ“SITO:
    Sistema de eventos publish-subscribe para comunicaciÃ³n
    desacoplada entre sistemas del motor.

EVENTOS PREDEFINIDOS:
    - on_collision: Cuando dos entidades colisionan
    - on_trigger_enter: Cuando una entidad entra en un trigger
    - on_animation_end: Cuando una animaciÃ³n termina
    - on_level_loaded: Cuando se carga un nivel

EJEMPLO DE USO:
    bus = EventBus()

    # Suscribirse
    def on_collision(event):
        print(f"ColisiÃ³n: {event.data}")
    bus.subscribe("on_collision", on_collision)

    # Emitir evento
    bus.emit("on_collision", {"entity_a": "Player", "entity_b": "Enemy"})

FORMATO DE EVENTO:
    Event(name="on_collision", data={"entity_a": "Player", ...})
"""

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List


@dataclass
class Event:
    """
    Representa un evento emitido.

    Atributos:
        name: Nombre del evento (ej: "on_collision")
        data: Datos asociados al evento
    """
    name: str
    data: Dict[str, Any] = field(default_factory=dict)


# Tipo para callbacks de eventos
EventCallback = Callable[[Event], None]


class EventBus:
    """
    Bus central de eventos con patrÃ³n publish-subscribe.

    Permite que los sistemas emitan eventos y que otros
    sistemas (como RuleSystem) reaccionen a ellos.
    """

    def __init__(self) -> None:
        """Inicializa el bus de eventos."""
        self._subscribers: Dict[str, List[EventCallback]] = {}
        self._event_history: List[Event] = []
        self._history_limit: int = 50

    def subscribe(self, event_name: str, callback: EventCallback) -> None:
        """
        Suscribe un callback a un tipo de evento.

        Args:
            event_name: Nombre del evento (ej: "on_collision")
            callback: FunciÃ³n a ejecutar cuando ocurra el evento
        """
        if event_name not in self._subscribers:
            self._subscribers[event_name] = []

        self._subscribers[event_name].append(callback)

    def unsubscribe(self, event_name: str, callback: EventCallback) -> None:
        """
        Cancela la suscripciÃ³n de un callback.

        Args:
            event_name: Nombre del evento
            callback: FunciÃ³n a remover
        """
        if event_name in self._subscribers:
            try:
                self._subscribers[event_name].remove(callback)
            except ValueError:
                pass

    def emit(self, event_name: str, data: Dict[str, Any] | None = None) -> None:
        """
        Emite un evento a todos los suscriptores.

        Args:
            event_name: Nombre del evento
            data: Datos del evento (opcional)
        """
        event = Event(name=event_name, data=data or {})

        # Guardar en historial
        self._event_history.append(event)
        if len(self._event_history) > self._history_limit:
            self._event_history.pop(0)

        # Notificar suscriptores
        if event_name in self._subscribers:
            for callback in self._subscribers[event_name]:
                try:
                    callback(event)
                except Exception as e:
                    print(f"[ERROR] EventBus: error en callback de '{event_name}': {e}")

    def get_recent_events(self, count: int = 10) -> List[Event]:
        """
        Obtiene los eventos mÃ¡s recientes.

        Args:
            count: NÃºmero de eventos a obtener

        Returns:
            Lista de eventos recientes
        """
        return self._event_history[-count:]

    def clear_history(self) -> None:
        """Limpia el historial de eventos."""
        self._event_history.clear()

    def get_subscriber_count(self, event_name: str) -> int:
        """Obtiene el nÃºmero de suscriptores a un evento."""
        return len(self._subscribers.get(event_name, []))
