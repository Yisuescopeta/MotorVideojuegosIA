"""
engine/agent/model_presets.py - Presets curados de modelos por proveedor.

PROPOSITO:
    Proveer una lista estable y ampliable de IDs de modelo sugeridos por
    proveedor para el selector del panel del agente. No es un listado en
    tiempo real de modelos disponibles en el endpoint remoto: es una capa
    local editable pensada para acelerar el cambio de modelo sin tener que
    escribirlo a mano cada vez.

GARANTIAS:
    - Nunca falla por proveedor desconocido: devuelve lista vacia.
    - Siempre incluye el modelo por defecto declarado en credenciales
      (`DEFAULT_OPENAI_MODEL`, `DEFAULT_OPENCODE_GO_MODEL`) si aplica.
    - Mantiene el orden declarado (primero el default recomendado).
"""

from __future__ import annotations

from engine.agent.credentials import DEFAULT_OPENAI_MODEL, DEFAULT_OPENCODE_GO_MODEL

# Presets curados. Se mantienen modestos y centrados en IDs ampliamente
# conocidos del ecosistema. Cualquier ID que no aparezca aqui puede
# introducirse via la opcion "Custom..." del panel.
_PRESETS: dict[str, tuple[str, ...]] = {
    "openai": (
        DEFAULT_OPENAI_MODEL,
        "gpt-5-mini",
        "gpt-4.1",
        "gpt-4o",
        "o4-mini",
        "o3",
    ),
    "opencode-go": (
        DEFAULT_OPENCODE_GO_MODEL,
        "opencode-go/claude-sonnet-4.5",
        "opencode-go/qwen3-coder-480b",
        "opencode-go/deepseek-v3.1",
        "opencode-go/gpt-5-mini",
    ),
    "fake": ("fake",),
}


def list_model_presets(provider_id: str) -> list[str]:
    """Devuelve los IDs de modelo sugeridos para un proveedor.

    El resultado siempre incluye el modelo por defecto conocido (si existe)
    como primer elemento. Providers desconocidos devuelven lista vacia.
    """
    key = _normalize(provider_id)
    presets = list(_PRESETS.get(key, ()))
    default = _default_model(key)
    if default and default not in presets:
        presets.insert(0, default)
    return presets


def recommended_model(provider_id: str) -> str:
    """Devuelve el modelo recomendado para un proveedor (primero de la lista).

    Si no hay preset conocido, devuelve cadena vacia.
    """
    presets = list_model_presets(provider_id)
    return presets[0] if presets else ""


def _normalize(provider_id: str) -> str:
    value = str(provider_id or "").strip().lower()
    if value in {"opencode", "opencodego", "go"}:
        return "opencode-go"
    return value


def _default_model(provider_id: str) -> str:
    if provider_id == "openai":
        return DEFAULT_OPENAI_MODEL
    if provider_id == "opencode-go":
        return DEFAULT_OPENCODE_GO_MODEL
    if provider_id == "fake":
        return "fake"
    return ""
