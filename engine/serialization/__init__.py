from engine.serialization.schema import (
    CURRENT_PREFAB_SCHEMA_VERSION,
    CURRENT_SCENE_SCHEMA_VERSION,
    ResolvedSceneReference,
    build_canonical_scene_payload,
    canonicalize_scene_cross_references,
    migrate_prefab_data,
    migrate_scene_data,
    validate_prefab_data,
    validate_scene_data,
    validate_no_session_only_references,
)

__all__ = [
    "CURRENT_PREFAB_SCHEMA_VERSION",
    "CURRENT_SCENE_SCHEMA_VERSION",
    "ResolvedSceneReference",
    "build_canonical_scene_payload",
    "canonicalize_scene_cross_references",
    "migrate_prefab_data",
    "migrate_scene_data",
    "validate_prefab_data",
    "validate_scene_data",
    "validate_no_session_only_references",
]
