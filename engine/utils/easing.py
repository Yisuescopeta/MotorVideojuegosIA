"""
engine/utils/easing.py - Funciones de interpolacion (easing) para Tweens.
Basado en ecuaciones Robert Penner adaptadas a Python.
Soporta 11 transiciones y 4 modos de ease.
"""

from __future__ import annotations

import math
from typing import Callable

# --- Easing primitives ---

def ease_linear(t: float) -> float:
    return t

# Sine
def ease_in_sine(t: float) -> float:
    return 1.0 - math.cos(t * math.pi * 0.5)

def ease_out_sine(t: float) -> float:
    return math.sin(t * math.pi * 0.5)

def ease_in_out_sine(t: float) -> float:
    return -0.5 * (math.cos(math.pi * t) - 1.0)

def ease_out_in_sine(t: float) -> float:
    return ease_out_sine(t * 0.5) * 0.5 if t < 0.5 else ease_in_sine(t * 2.0 - 1.0) * 0.5 + 0.5

# Quad
def ease_in_quad(t: float) -> float:
    return t * t

def ease_out_quad(t: float) -> float:
    return 1.0 - (1.0 - t) * (1.0 - t)

def ease_in_out_quad(t: float) -> float:
    return 2.0 * t * t if t < 0.5 else 1.0 - (-2.0 * t + 2.0) ** 2 / 2.0

def ease_out_in_quad(t: float) -> float:
    return ease_out_quad(t * 0.5) * 0.5 if t < 0.5 else ease_in_quad(t * 2.0 - 1.0) * 0.5 + 0.5

# Cubic
def ease_in_cubic(t: float) -> float:
    return t * t * t

def ease_out_cubic(t: float) -> float:
    return 1.0 - (1.0 - t) ** 3

def ease_in_out_cubic(t: float) -> float:
    return 4.0 * t ** 3 if t < 0.5 else 1.0 - (-2.0 * t + 2.0) ** 3 / 2.0

def ease_out_in_cubic(t: float) -> float:
    return ease_out_cubic(t * 0.5) * 0.5 if t < 0.5 else ease_in_cubic(t * 2.0 - 1.0) * 0.5 + 0.5

# Quart
def ease_in_quart(t: float) -> float:
    return t ** 4

def ease_out_quart(t: float) -> float:
    return 1.0 - (1.0 - t) ** 4

def ease_in_out_quart(t: float) -> float:
    return 8.0 * t ** 4 if t < 0.5 else 1.0 - (-2.0 * t + 2.0) ** 4 / 2.0

def ease_out_in_quart(t: float) -> float:
    return ease_out_quart(t * 0.5) * 0.5 if t < 0.5 else ease_in_quart(t * 2.0 - 1.0) * 0.5 + 0.5

# Quint
def ease_in_quint(t: float) -> float:
    return t ** 5

def ease_out_quint(t: float) -> float:
    return 1.0 - (1.0 - t) ** 5

def ease_in_out_quint(t: float) -> float:
    return 16.0 * t ** 5 if t < 0.5 else 1.0 - (-2.0 * t + 2.0) ** 5 / 2.0

def ease_out_in_quint(t: float) -> float:
    return ease_out_quint(t * 0.5) * 0.5 if t < 0.5 else ease_in_quint(t * 2.0 - 1.0) * 0.5 + 0.5

# Expo
def ease_in_expo(t: float) -> float:
    return 0.0 if t == 0.0 else 2.0 ** (10.0 * t - 10.0)

def ease_out_expo(t: float) -> float:
    return 1.0 if t >= 1.0 else 1.0 - 2.0 ** (-10.0 * t)

def ease_in_out_expo(t: float) -> float:
    if t == 0.0:
        return 0.0
    if t >= 1.0:
        return 1.0
    if t < 0.5:
        return 2.0 ** (20.0 * t - 10.0) / 2.0
    return 1.0 - 2.0 ** (-20.0 * t + 10.0) / 2.0

def ease_out_in_expo(t: float) -> float:
    return ease_out_expo(t * 0.5) * 0.5 if t < 0.5 else ease_in_expo(t * 2.0 - 1.0) * 0.5 + 0.5

# Circ
def ease_in_circ(t: float) -> float:
    return 1.0 - math.sqrt(1.0 - t ** 2)

def ease_out_circ(t: float) -> float:
    return math.sqrt(1.0 - (t - 1.0) ** 2)

def ease_in_out_circ(t: float) -> float:
    if t < 0.5:
        return (1.0 - math.sqrt(1.0 - 4.0 * t * t)) / 2.0
    return (math.sqrt(-(2.0 * t - 3.0) * (2.0 * t - 1.0)) + 1.0) / 2.0

def ease_out_in_circ(t: float) -> float:
    return ease_out_circ(t * 0.5) * 0.5 if t < 0.5 else ease_in_circ(t * 2.0 - 1.0) * 0.5 + 0.5

# Back
_C1 = 1.70158
_C2 = _C1 * 1.525
_C3 = _C1 + 1.0

def ease_in_back(t: float) -> float:
    return _C3 * t ** 3 - _C1 * t * t

def ease_out_back(t: float) -> float:
    return 1.0 + _C3 * (t - 1.0) ** 3 + _C1 * (t - 1.0) ** 2

def ease_in_out_back(t: float) -> float:
    if t < 0.5:
        return (4.0 * t * t * ((_C2 + 1.0) * t - _C2)) / 2.0
    return ((2.0 * t - 2.0) ** 3 * ((_C2 + 1.0) * (t * 2.0 - 2.0) + _C2) + 2.0) / 2.0

def ease_out_in_back(t: float) -> float:
    return ease_out_back(t * 0.5) * 0.5 if t < 0.5 else ease_in_back(t * 2.0 - 1.0) * 0.5 + 0.5

# Elastic
def ease_in_elastic(t: float) -> float:
    if t == 0.0:
        return 0.0
    if t >= 1.0:
        return 1.0
    return -(2.0 ** (10.0 * t - 10.0)) * math.sin((t * 10.0 - 10.75) * (2.0 * math.pi) / 3.0)

def ease_out_elastic(t: float) -> float:
    if t == 0.0:
        return 0.0
    if t >= 1.0:
        return 1.0
    return 2.0 ** (-10.0 * t) * math.sin((t * 10.0 - 0.75) * (2.0 * math.pi) / 3.0) + 1.0

def ease_in_out_elastic(t: float) -> float:
    if t == 0.0:
        return 0.0
    if t >= 1.0:
        return 1.0
    c5 = (2.0 * math.pi) / 4.5
    if t < 0.5:
        return -(2.0 ** (20.0 * t - 10.0) * math.sin((20.0 * t - 11.125) * c5)) / 2.0
    return 2.0 ** (-20.0 * t + 10.0) * math.sin((20.0 * t - 11.125) * c5) / 2.0 + 1.0

def ease_out_in_elastic(t: float) -> float:
    return ease_out_elastic(t * 0.5) * 0.5 if t < 0.5 else ease_in_elastic(t * 2.0 - 1.0) * 0.5 + 0.5

# Bounce
def ease_out_bounce(t: float) -> float:
    n1 = 7.5625
    d1 = 2.75
    if t < 1.0 / d1:
        return n1 * t * t
    elif t < 2.0 / d1:
        t_sub = t - 1.5 / d1
        return n1 * t_sub * t_sub + 0.75
    elif t < 2.5 / d1:
        t_sub = t - 2.25 / d1
        return n1 * t_sub * t_sub + 0.9375
    t_sub = t - 2.625 / d1
    return n1 * t_sub * t_sub + 0.984375

def ease_in_bounce(t: float) -> float:
    return 1.0 - ease_out_bounce(1.0 - t)

def ease_in_out_bounce(t: float) -> float:
    if t < 0.5:
        return (1.0 - ease_out_bounce(1.0 - 2.0 * t)) / 2.0
    return (1.0 + ease_out_bounce(2.0 * t - 1.0)) / 2.0

def ease_out_in_bounce(t: float) -> float:
    return ease_out_bounce(t * 0.5) * 0.5 if t < 0.5 else ease_in_bounce(t * 2.0 - 1.0) * 0.5 + 0.5

# Spring
def ease_out_spring(t: float) -> float:
    if t == 0.0:
        return 0.0
    if t >= 1.0:
        return 1.0
    return 1.0 - 2.0 ** (-10.0 * t) * math.cos(8.0 * math.pi * t)

def ease_in_spring(t: float) -> float:
    if t >= 1.0:
        return 1.0
    return 1.0 - ease_out_spring(1.0 - t)

def ease_in_out_spring(t: float) -> float:
    if t < 0.5:
        return (1.0 - ease_out_spring(1.0 - 2.0 * t)) / 2.0
    return (1.0 + ease_out_spring(2.0 * t - 1.0)) / 2.0

def ease_out_in_spring(t: float) -> float:
    return ease_out_spring(t * 0.5) * 0.5 if t < 0.5 else ease_in_spring(t * 2.0 - 1.0) * 0.5 + 0.5


# --- Easing map: (transition, ease) -> function ---

EASING_MAP: dict[tuple[str, str], Callable[[float], float]] = {
    ("linear", "ease_in"): ease_linear,
    ("linear", "ease_out"): ease_linear,
    ("linear", "ease_in_out"): ease_linear,
    ("linear", "ease_out_in"): ease_linear,
    ("sine", "ease_in"): ease_in_sine,
    ("sine", "ease_out"): ease_out_sine,
    ("sine", "ease_in_out"): ease_in_out_sine,
    ("sine", "ease_out_in"): ease_out_in_sine,
    ("quad", "ease_in"): ease_in_quad,
    ("quad", "ease_out"): ease_out_quad,
    ("quad", "ease_in_out"): ease_in_out_quad,
    ("quad", "ease_out_in"): ease_out_in_quad,
    ("cubic", "ease_in"): ease_in_cubic,
    ("cubic", "ease_out"): ease_out_cubic,
    ("cubic", "ease_in_out"): ease_in_out_cubic,
    ("cubic", "ease_out_in"): ease_out_in_cubic,
    ("quart", "ease_in"): ease_in_quart,
    ("quart", "ease_out"): ease_out_quart,
    ("quart", "ease_in_out"): ease_in_out_quart,
    ("quart", "ease_out_in"): ease_out_in_quart,
    ("quint", "ease_in"): ease_in_quint,
    ("quint", "ease_out"): ease_out_quint,
    ("quint", "ease_in_out"): ease_in_out_quint,
    ("quint", "ease_out_in"): ease_out_in_quint,
    ("expo", "ease_in"): ease_in_expo,
    ("expo", "ease_out"): ease_out_expo,
    ("expo", "ease_in_out"): ease_in_out_expo,
    ("expo", "ease_out_in"): ease_out_in_expo,
    ("circ", "ease_in"): ease_in_circ,
    ("circ", "ease_out"): ease_out_circ,
    ("circ", "ease_in_out"): ease_in_out_circ,
    ("circ", "ease_out_in"): ease_out_in_circ,
    ("back", "ease_in"): ease_in_back,
    ("back", "ease_out"): ease_out_back,
    ("back", "ease_in_out"): ease_in_out_back,
    ("back", "ease_out_in"): ease_out_in_back,
    ("elastic", "ease_in"): ease_in_elastic,
    ("elastic", "ease_out"): ease_out_elastic,
    ("elastic", "ease_in_out"): ease_in_out_elastic,
    ("elastic", "ease_out_in"): ease_out_in_elastic,
    ("bounce", "ease_in"): ease_in_bounce,
    ("bounce", "ease_out"): ease_out_bounce,
    ("bounce", "ease_in_out"): ease_in_out_bounce,
    ("bounce", "ease_out_in"): ease_out_in_bounce,
    ("spring", "ease_in"): ease_in_spring,
    ("spring", "ease_out"): ease_out_spring,
    ("spring", "ease_in_out"): ease_in_out_spring,
    ("spring", "ease_out_in"): ease_out_in_spring,
}

# --- Legacy backward-compat functions and map ---

linear = ease_linear
sine_in = ease_in_sine
sine_out = ease_out_sine
sine_in_out = ease_in_out_sine
quad_in = ease_in_quad
quad_out = ease_out_quad
quad_in_out = ease_in_out_quad
cubic_in = ease_in_cubic
cubic_out = ease_out_cubic
cubic_in_out = ease_in_out_cubic
expo_in = ease_in_expo
expo_out = ease_out_expo
expo_in_out = ease_in_out_expo

EASING_FUNCTIONS: dict[str, Callable[[float], float]] = {
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

# Legacy transitions that embed ease in the name
LEGACY_TRANSITION_TO_STANDARD: dict[str, tuple[str, str]] = {
    "sine_in": ("sine", "ease_in"),
    "sine_out": ("sine", "ease_out"),
    "sine_in_out": ("sine", "ease_in_out"),
    "quad_in": ("quad", "ease_in"),
    "quad_out": ("quad", "ease_out"),
    "quad_in_out": ("quad", "ease_in_out"),
    "cubic_in": ("cubic", "ease_in"),
    "cubic_out": ("cubic", "ease_out"),
    "cubic_in_out": ("cubic", "ease_in_out"),
    "expo_in": ("expo", "ease_in"),
    "expo_out": ("expo", "ease_out"),
    "expo_in_out": ("expo", "ease_in_out"),
}


def get_legacy_easing(name: str) -> Callable[[float], float]:
    """Backward-compat: obtiene funcion de easing por nombre legacy."""
    return EASING_FUNCTIONS.get(str(name or "linear").strip().lower(), linear)


def get_easing(transition: str, ease: str = "ease_in_out") -> Callable[[float], float]:
    """Obtiene la funcion de easing para una transicion y modo de ease.

    Args:
        transition: Nombre de la transicion (linear, sine, quad, cubic, quart,
                    quint, expo, circ, back, elastic, bounce, spring).
        ease: Modo de ease (ease_in, ease_out, ease_in_out, ease_out_in).

    Returns:
        Funcion de easing que recibe t [0,1] y devuelve valor [0,1].
        Si la combinacion no existe, devuelve linear.
    """
    trans = str(transition or "linear").strip().lower()
    ease_mode = str(ease or "ease_in_out").strip().lower()

    # Handle legacy names like "sine_in_out" -> ("sine", "ease_in_out")
    if trans in LEGACY_TRANSITION_TO_STANDARD:
        trans, ease_mode = LEGACY_TRANSITION_TO_STANDARD[trans]

    key = (trans, ease_mode)
    return EASING_MAP.get(key, ease_linear)
