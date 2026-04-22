from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Any, Callable

from engine.editor.console_panel import log_err, log_warn

DeferredCallback = Callable[..., Any]


@dataclass
class DeferredCall:
    """Representa una llamada diferida pendiente de ejecutarse."""

    callback: DeferredCallback
    args: tuple[Any, ...] = ()
    kwargs: dict[str, Any] = field(default_factory=dict)
    description: str = ""

    def invoke(self) -> Any:
        """Ejecuta la llamada diferida."""
        return self.callback(*self.args, **self.kwargs)


class DeferredCallQueue:
    """Cola acotada de llamadas diferidas para flush en POST_UPDATE."""

    def __init__(self, *, max_size: int = 1024, max_flush_per_cycle: int | None = None) -> None:
        self._calls: deque[DeferredCall] = deque()
        self._max_size = max(1, int(max_size))
        if max_flush_per_cycle is None:
            self._max_flush_per_cycle = self._max_size
        else:
            self._max_flush_per_cycle = max(1, int(max_flush_per_cycle))

    @property
    def size(self) -> int:
        """Retorna el número de llamadas pendientes."""
        return len(self._calls)

    @property
    def max_size(self) -> int:
        """Retorna la capacidad máxima configurada."""
        return self._max_size

    def enqueue(self, callback: DeferredCallback, *args: Any, description: str = "", **kwargs: Any) -> bool:
        """Encola una llamada si hay capacidad disponible."""
        if len(self._calls) >= self._max_size:
            detalle = f" ({description})" if description else ""
            log_warn(f"DeferredCallQueue overflow{detalle}: limite={self._max_size}")
            return False

        self._calls.append(
            DeferredCall(
                callback=callback,
                args=args,
                kwargs=dict(kwargs),
                description=description,
            )
        )
        return True

    def flush(self, *, max_calls: int | None = None) -> int:
        """Ejecuta llamadas pendientes respetando un límite de seguridad."""
        processed = 0
        if max_calls is None:
            limit = self._max_flush_per_cycle
        else:
            limit = max(0, int(max_calls))

        while self._calls and processed < limit:
            deferred_call = self._calls.popleft()
            try:
                deferred_call.invoke()
            except Exception as exc:
                detalle = f" ({deferred_call.description})" if deferred_call.description else ""
                log_err(f"DeferredCallQueue callback falló{detalle}: {exc}")
            processed += 1

        if self._calls and processed >= limit:
            log_warn(
                "DeferredCallQueue flush alcanzó el límite "
                f"de {limit} llamadas; quedan {len(self._calls)} pendientes"
            )

        return processed

    def clear(self) -> None:
        """Descarta todas las llamadas pendientes."""
        self._calls.clear()
