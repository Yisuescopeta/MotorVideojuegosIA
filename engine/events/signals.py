from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntFlag
from typing import Any, Callable

from engine.editor.console_panel import log_err
from engine.events.deferred_queue import DeferredCallQueue

SignalCallback = Callable[..., Any]


class SignalConnectionFlags(IntFlag):
    """Flags runtime para controlar cómo se ejecuta una conexión."""

    NONE = 0
    DEFERRED = 1 << 0
    PERSIST = 1 << 1
    ONE_SHOT = 1 << 2
    REFERENCE_COUNTED = 1 << 3


@dataclass(frozen=True)
class SignalRef:
    """Identifica una señal emitida por una fuente concreta."""

    source_id: str
    signal_name: str


@dataclass
class SignalConnection:
    """Representa una conexión runtime entre una señal y un callback."""

    connection_id: str
    signal: SignalRef
    callback: SignalCallback
    flags: SignalConnectionFlags = SignalConnectionFlags.NONE
    binds: tuple[Any, ...] = ()
    enabled: bool = True
    reference_count: int = 1
    description: str = ""

    @property
    def is_deferred(self) -> bool:
        """Indica si la conexión debe ejecutarse por cola diferida."""
        return bool(self.flags & SignalConnectionFlags.DEFERRED)

    @property
    def is_one_shot(self) -> bool:
        """Indica si la conexión debe desconectarse antes de invocar."""
        return bool(self.flags & SignalConnectionFlags.ONE_SHOT)

    @property
    def is_reference_counted(self) -> bool:
        """Indica si la conexión acumula referencias repetidas."""
        return bool(self.flags & SignalConnectionFlags.REFERENCE_COUNTED)


class SignalRuntime:
    """Despachador runtime de señales con snapshot y soporte diferido."""

    def __init__(self, deferred_queue: DeferredCallQueue | None = None) -> None:
        self._deferred_queue = deferred_queue or DeferredCallQueue()
        self._connections_by_signal: dict[SignalRef, list[SignalConnection]] = {}
        self._connections_by_id: dict[str, SignalConnection] = {}
        self._next_connection_number = 1

    @property
    def deferred_queue(self) -> DeferredCallQueue:
        """Expone la cola diferida asociada."""
        return self._deferred_queue

    def connect(
        self,
        source_id: str,
        signal_name: str,
        callback: SignalCallback,
        *,
        flags: SignalConnectionFlags = SignalConnectionFlags.NONE,
        binds: tuple[Any, ...] | list[Any] | None = None,
        connection_id: str | None = None,
        description: str = "",
    ) -> str:
        """Conecta una señal a un callback y retorna el id runtime de la conexión."""
        signal = SignalRef(source_id=str(source_id), signal_name=str(signal_name))
        normalized_binds = tuple(binds or ())

        if flags & SignalConnectionFlags.REFERENCE_COUNTED:
            existing = self._find_connection(signal, callback, normalized_binds, flags)
            if existing is not None:
                existing.reference_count += 1
                return existing.connection_id

        normalized_connection_id = connection_id or self._generate_connection_id(signal)
        connection = SignalConnection(
            connection_id=normalized_connection_id,
            signal=signal,
            callback=callback,
            flags=flags,
            binds=normalized_binds,
            description=description,
        )
        self._connections_by_signal.setdefault(signal, []).append(connection)
        self._connections_by_id[normalized_connection_id] = connection
        return normalized_connection_id

    def disconnect(self, connection_id: str) -> bool:
        """Desconecta una conexión runtime por id."""
        connection = self._connections_by_id.get(connection_id)
        if connection is None:
            return False

        if connection.is_reference_counted and connection.reference_count > 1:
            connection.reference_count -= 1
            return True

        return self._remove_connection(connection_id)

    def disconnect_signal(self, source_id: str, signal_name: str) -> int:
        """Desconecta todas las conexiones de una señal concreta."""
        signal = SignalRef(source_id=str(source_id), signal_name=str(signal_name))
        signal_connections = list(self._connections_by_signal.get(signal, []))
        removed = 0
        for connection in signal_connections:
            removed += 1 if self._remove_connection(connection.connection_id) else 0
        return removed

    def is_connected(self, connection_id: str) -> bool:
        """Indica si una conexión runtime sigue activa."""
        return connection_id in self._connections_by_id

    def list_connections(self, source_id: str | None = None, signal_name: str | None = None) -> list[SignalConnection]:
        """Lista conexiones runtime activas, opcionalmente filtradas."""
        if source_id is None and signal_name is None:
            return list(self._connections_by_id.values())

        filtered: list[SignalConnection] = []
        normalized_source = None if source_id is None else str(source_id)
        normalized_signal = None if signal_name is None else str(signal_name)
        for connection in self._connections_by_id.values():
            if normalized_source is not None and connection.signal.source_id != normalized_source:
                continue
            if normalized_signal is not None and connection.signal.signal_name != normalized_signal:
                continue
            filtered.append(connection)
        return filtered

    def emit(self, source_id: str, signal_name: str, *args: Any, **kwargs: Any) -> int:
        """Emite una señal a todas sus conexiones activas."""
        signal = SignalRef(source_id=str(source_id), signal_name=str(signal_name))
        signal_connections = list(self._connections_by_signal.get(signal, []))
        executed = 0

        for connection in signal_connections:
            if not connection.enabled:
                continue

            if connection.is_one_shot:
                self._remove_connection(connection.connection_id)

            try:
                if connection.is_deferred:
                    enqueued = self._deferred_queue.enqueue(
                        connection.callback,
                        *args,
                        *connection.binds,
                        description=connection.description or connection.connection_id,
                        **kwargs,
                    )
                    executed += 1 if enqueued else 0
                    continue

                connection.callback(*args, *connection.binds, **kwargs)
                executed += 1
            except Exception as exc:
                detalle = connection.description or connection.connection_id
                log_err(f"SignalRuntime emit falló en '{detalle}': {exc}")

        return executed

    def clear(self) -> None:
        """Limpia todas las conexiones runtime."""
        self._connections_by_signal.clear()
        self._connections_by_id.clear()

    def _remove_connection(self, connection_id: str) -> bool:
        """Elimina una conexión runtime sin respetar reference_count."""
        connection = self._connections_by_id.get(connection_id)
        if connection is None:
            return False

        signal_connections = self._connections_by_signal.get(connection.signal)
        self._connections_by_id.pop(connection_id, None)
        if signal_connections is None:
            return True

        self._connections_by_signal[connection.signal] = [
            current for current in signal_connections if current.connection_id != connection_id
        ]
        if not self._connections_by_signal[connection.signal]:
            self._connections_by_signal.pop(connection.signal, None)
        return True

    def _find_connection(
        self,
        signal: SignalRef,
        callback: SignalCallback,
        binds: tuple[Any, ...],
        flags: SignalConnectionFlags,
    ) -> SignalConnection | None:
        for connection in self._connections_by_signal.get(signal, []):
            if connection.callback is not callback:
                continue
            if connection.binds != binds:
                continue
            if connection.flags != flags:
                continue
            return connection
        return None

    def _generate_connection_id(self, signal: SignalRef) -> str:
        connection_id = (
            f"signal::{signal.source_id}::{signal.signal_name}::{self._next_connection_number}"
        )
        self._next_connection_number += 1
        return connection_id
