from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Iterable, List

from engine.ai.types import CapabilityDescriptor, CapabilityGap
from engine.levels.component_registry import create_default_registry


UNSUPPORTED_FEATURES = {
    "navmesh": ("navmesh_support", "No existe navegación o navmesh en runtime"),
    "pathfinding": ("pathfinding_support", "No existe pathfinding declarativo para NPCs"),
    "multiplayer": ("multiplayer_support", "No existe red/multiplayer en la arquitectura actual"),
    "network": ("network_support", "No existe red/multiplayer en la arquitectura actual"),
    "particle": ("particle_support", "No existe sistema de partículas serializable"),
    "particles": ("particle_support", "No existe sistema de partículas serializable"),
}


def build_capability_registry(project_service, engine_api) -> List[CapabilityDescriptor]:
    descriptors: List[CapabilityDescriptor] = []

    for component_name in sorted(create_default_registry().list_registered()):
        descriptors.append(
            CapabilityDescriptor(
                id=f"component:{component_name.lower()}",
                name=component_name,
                category="component",
                available=True,
                description=f"Componente serializable {component_name}",
                evidence=["engine.levels.component_registry.create_default_registry"],
                tags=["ecs", "serializable"],
            )
        )

    system_dir = Path("engine/systems")
    for file_path in sorted(system_dir.glob("*.py")):
        if file_path.name.startswith("_"):
            continue
        system_name = file_path.stem
        descriptors.append(
            CapabilityDescriptor(
                id=f"system:{system_name}",
                name=system_name,
                category="system",
                available=True,
                description=f"Sistema runtime/editor disponible: {system_name}",
                evidence=[file_path.as_posix()],
                tags=["runtime"],
            )
        )

    project_summary = project_service.get_project_summary()
    descriptors.extend(
        [
            CapabilityDescriptor(
                id="authoring:engine_api",
                name="EngineAPI authoring",
                category="api",
                available=True,
                description="Authoring por API para escenas, componentes, assets y prefabs",
                evidence=["engine.api.EngineAPI"],
                tags=["api", "authoring"],
            ),
            CapabilityDescriptor(
                id="project:assets",
                name="Project assets",
                category="project",
                available=True,
                description="Assets listables desde el proyecto activo",
                evidence=[project_summary["root"]],
                tags=["project", "assets"],
            ),
        ]
    )

    prefabs_dir = project_service.get_project_path("prefabs")
    if prefabs_dir.exists():
        descriptors.append(
            CapabilityDescriptor(
                id="project:prefabs",
                name="Project prefabs",
                category="project",
                available=True,
                description="Instanciación y lectura de prefabs del proyecto",
                evidence=[prefabs_dir.as_posix()],
                tags=["project", "prefabs"],
            )
        )
    return descriptors


def capability_index(descriptors: Iterable[CapabilityDescriptor]) -> Dict[str, Dict[str, Any]]:
    return {descriptor.id: descriptor.to_dict() for descriptor in descriptors}


def detect_capability_gaps(prompt: str) -> List[CapabilityGap]:
    lower = prompt.lower()
    gaps: List[CapabilityGap] = []
    seen: set[str] = set()
    for keyword, (gap_id, reason) in UNSUPPORTED_FEATURES.items():
        if keyword in lower and gap_id not in seen:
            seen.add(gap_id)
            gaps.append(
                CapabilityGap(
                    id=gap_id,
                    title=keyword,
                    reason=reason,
                    suggested_track="plan_engine_extension",
                    blocking=True,
                    evidence=[f"prompt keyword: {keyword}"],
                )
            )
    return gaps
