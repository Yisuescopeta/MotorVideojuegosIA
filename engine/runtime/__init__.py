"""Separated runtime for exported games.

Must NOT import: engine.editor, engine.inspector, tools, tests, docs, main.
"""

__all__ = [
    "ContentLoader",
    "ExportRuntime",
    "RuntimeConfig",
    "SharedGameRuntime",
    "bootstrap_config",
    "find_runtime_config",
]

_LAZY_IMPORTS = {
    "bootstrap_config": ("engine.runtime.bootstrap", "bootstrap_config"),
    "find_runtime_config": ("engine.runtime.bootstrap", "find_runtime_config"),
    "ContentLoader": ("engine.runtime.content_loader", "ContentLoader"),
    "ExportRuntime": ("engine.runtime.export_runtime", "ExportRuntime"),
    "RuntimeConfig": ("engine.runtime.runtime_config", "RuntimeConfig"),
    "SharedGameRuntime": ("engine.runtime.shared_game_runtime", "SharedGameRuntime"),
}


def __getattr__(name: str):
    try:
        module_name, attr_name = _LAZY_IMPORTS[name]
    except KeyError as exc:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from exc
    import importlib

    value = getattr(importlib.import_module(module_name), attr_name)
    globals()[name] = value
    return value
