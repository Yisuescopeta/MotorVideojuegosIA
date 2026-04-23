"""
engine/utils/easing.py - Funciones de interpolacion (easing) para Tweens.
Basado en ecuaciones Robert Penner adaptadas a Python.
"""

from __future__ import annotations

import math


def linear(t: float) -> float:
    return t


def sine_in(t: float) -> float:
    return 1.0 - math.cos(t * math.pi * 0.5)


def sine_out(t: float) -> float:
    return math.sin(t * math.pi * 0.5)


def sine_in_out(t: float) -> float:
    return -0.5 * (math.cos(math.pi * t) - 1.0)


def quad_in(t: float) -> float:
    return t * t


def quad_out(t: float) -> float:
    return -t * (t - 2.0)


def quad_in_out(t: float) -> float:
    t *= 2.0
    if t < 1.0:
        return 0.5 * t * t
    t -= 1.0
    return -0.5 * (t * (t - 2.0) - 1.0)


def cubic_in(t: float) -> float:
    return t * t * t


def cubic_out(t: float) -> float:
    t -= 1.0
    return t * t * t + 1.0


def cubic_in_out(t: float) -> float:
    t *= 2.0
    if t < 1.0:
        return 0.5 * t * t * t
    t -= 2.0
    return 0.5 * (t * t * t + 2.0)


def expo_in(t: float) -> float:
    return 0.0 if t == 0.0 else math.pow(2.0, 10.0 * (t - 1.0))


def expo_out(t: float) -> float:
    return 1.0 if t >= 1.0 else 1.0 - math.pow(2.0, -10.0 * t)


def expo_in_out(t: float) -> float:
    if t == 0.0:
        return 0.0
    if t >= 1.0:
        return 1.0
    t *= 2.0
    if t < 1.0:
        return 0.5 * math.pow(2.0, 10.0 * (t - 1.0))
    return 0.5 * (2.0 - math.pow(2.0, -10.0 * (t - 1.0)))


EASING_FUNCTIONS: dict[str, callable] = {
    "linear": linear,
    "sine_in": sine_in,
    "sine_out": sine_out,
    "sine_in_out": sine_in_out,
    "quad_in": quad_in,
    "quad_out": quad_out,
    "quad_in_out": quad_in_out,
    "cubic_in": cubic_in,
    "cubic_out": cubic_out,
    "cubic_in_out": cubic_in_out,
    "expo_in": expo_in,
    "expo_out": expo_out,
    "expo_in_out": expo_in_out,
}


def get_easing(name: str) -> callable:
    """Obtiene una funcion de easing por nombre; devuelve linear si no existe."""
    return EASING_FUNCTIONS.get(str(name or "linear").strip().lower(), linear)
