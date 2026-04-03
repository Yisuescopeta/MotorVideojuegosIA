from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from engine.assets.asset_service import AssetService
from engine.project.project_service import ProjectService
from engine.scenes.scene_transition_support import collect_project_scene_transitions
from engine.serialization.schema import migrate_prefab_data, migrate_scene_data
from engine.workflows.ai_assist.types import (
    ContextPackAssetMetadataRecord,
    ContextPackAssetRecord,
    ContextPackAssetSection,
    ContextPackFeatureSection,
    ContextPackOpenSceneRecord,
    ContextPackProjectSection,
    ContextPackPublicDataField,
    ContextPackSceneRecord,
    ContextPackSceneSection,
    ContextPackScriptBehaviourSection,
    ContextPackScriptBehaviourUsage,
    ContextPackSourceKind,
    ProjectContextPack,
    ProjectContextPackArtifacts,
)

try:
    from engine.api.engine_api import EngineAPI
except Exception:  # pragma: no cover - defensive import for limited runtimes
    EngineAPI = Any  # type: ignore[misc,assignment]


class ProjectContextPackGenerator:
    SCHEMA_VERSION = 1
    JSON_FILE_NAME = "ai_context_pack.json"
    MARKDOWN_FILE_NAME = "ai_context_pack.md"

    def __init__(
        self,
        project_service: ProjectService,
        asset_service: AssetService,
        api: EngineAPI | None = None,
    ) -> None:
        self._project_service = project_service
        self._asset_service = asset_service
        self._api = api

    def generate(self) -> ProjectContextPackArtifacts:
        pack = self._build_pack()
        meta_root = self._project_service.get_project_path("meta")
        meta_root.mkdir(parents=True, exist_ok=True)
        json_path = meta_root / self.JSON_FILE_NAME
        markdown_path = meta_root / self.MARKDOWN_FILE_NAME
        json_path.write_text(self._render_json(pack), encoding="utf-8")
        markdown_path.write_text(self._render_markdown(pack), encoding="utf-8")
        return ProjectContextPackArtifacts(
            json_path=self._project_service.to_relative_path(json_path),
            markdown_path=self._project_service.to_relative_path(markdown_path),
            pack=pack,
        )

    def _build_pack(self) -> ProjectContextPack:
        project = self._build_project_section()
        scenes = self._build_scene_section()
        assets = self._build_asset_section()
        features = self._build_feature_section(
            project_scenes=scenes.project_scenes,
            transition_rows=scenes.transition_rows,
        )
        script_behaviours = self._build_script_behaviour_section(
            project_scenes=scenes.project_scenes,
            prefabs=assets.prefabs,
        )
        relevant_paths = {
            metadata.path
            for metadata in assets.relevant_metadata
        }
        for usage in script_behaviours.usages:
            if usage.script_path:
                relevant_paths.add(usage.script_path)
        assets = self._build_asset_section(relevant_paths=relevant_paths)
        return ProjectContextPack(
            schema_version=self.SCHEMA_VERSION,
            project=project,
            scenes=scenes,
            assets=assets,
            features=features,
            script_behaviours=script_behaviours,
        )

    def _build_project_section(self) -> ContextPackProjectSection:
        manifest = copy.deepcopy(self._project_service.get_project_summary())
        manifest["paths"] = {
            key: self._normalize_rel_path(value)
            for key, value in sorted(dict(manifest.get("paths", {})).items())
        }
        if "root" in manifest:
            manifest["root"] = self._normalize_rel_path(manifest["root"], allow_absolute=True)
        if "manifest_path" in manifest:
            manifest["manifest_path"] = self._normalize_rel_path(manifest["manifest_path"], allow_absolute=True)
        editor_state = self._normalize_editor_state(self._project_service.load_editor_state())
        startup_scene = self._normalize_rel_path(
            self._project_service.load_project_settings().get("startup_scene", "")
        )
        return ContextPackProjectSection(
            manifest=manifest,
            important_paths=dict(manifest.get("paths", {})),
            startup_scene=startup_scene,
            editor_state=editor_state,
        )

    def _build_scene_section(self) -> ContextPackSceneSection:
        project_scenes = [
            ContextPackSceneRecord(
                name=str(record.get("name", "") or ""),
                path=self._normalize_rel_path(record.get("path", "")),
            )
            for record in self._project_service.list_project_scenes()
            if not str(record.get("path", "") or "").endswith(".meta.json")
        ]
        project_scenes.sort(key=lambda item: (item.path.lower(), item.name.lower()))

        active_scene: dict[str, Any] = {}
        open_scenes: list[ContextPackOpenSceneRecord] = []
        active_scene_flow_connections: dict[str, str] = {}
        scene_manager = None
        if self._api is not None:
            active_scene = self._normalize_scene_summary(self._api.get_active_scene())
            open_scenes = [
                ContextPackOpenSceneRecord(
                    key=str(item.get("key", "") or ""),
                    name=str(item.get("name", "") or ""),
                    path=self._normalize_rel_path(item.get("path", "")),
                    dirty=bool(item.get("dirty", False)),
                    is_active=bool(item.get("is_active", False)),
                )
                for item in self._api.list_open_scenes()
            ]
            open_scenes.sort(key=lambda item: (item.path.lower(), item.name.lower(), item.key.lower()))
            active_scene_flow_connections = {
                str(key): self._normalize_rel_path(value)
                for key, value in sorted(self._api.get_scene_connections().items())
                if str(key).strip() and str(value).strip()
            }
            scene_manager = getattr(self._api, "scene_manager", None)

        transitions = collect_project_scene_transitions(self._project_service, scene_manager)
        return ContextPackSceneSection(
            project_scenes=project_scenes,
            active_scene=active_scene,
            open_scenes=open_scenes,
            active_scene_flow_connections=active_scene_flow_connections,
            transition_summaries=self._normalize_transition_records(transitions.get("summaries", [])),
            transition_rows=self._normalize_transition_records(transitions.get("rows", [])),
            transition_issues=self._normalize_transition_records(transitions.get("issues", [])),
        )

    def _build_asset_section(
        self,
        *,
        relevant_paths: set[str] | None = None,
    ) -> ContextPackAssetSection:
        catalog = self._asset_service.get_asset_database().ensure_catalog()
        asset_records = [
            ContextPackAssetRecord(
                path=self._normalize_rel_path(entry.get("path", "")),
                guid=str(entry.get("guid", "") or ""),
                asset_kind=str(entry.get("asset_kind", "") or ""),
                importer=str(entry.get("importer", "") or ""),
                labels=sorted(str(label) for label in entry.get("labels", []) if str(label).strip()),
                dependencies=sorted(
                    self._normalize_rel_path(path)
                    for path in entry.get("dependencies", [])
                    if str(path).strip()
                ),
            )
            for entry in catalog.get("assets", [])
            if str(entry.get("path", "")).strip()
        ]
        asset_records.sort(key=lambda item: item.path.lower())

        prefabs = self._list_project_prefabs()
        scripts = self._list_project_scripts()
        relevant_metadata = self._build_relevant_metadata(
            asset_records=asset_records,
            prefabs=prefabs,
            scripts=scripts,
            relevant_paths=relevant_paths or set(),
        )
        return ContextPackAssetSection(
            catalog=asset_records,
            prefabs=prefabs,
            scripts=scripts,
            relevant_metadata=relevant_metadata,
        )

    def _build_feature_section(
        self,
        *,
        project_scenes: list[ContextPackSceneRecord],
        transition_rows: list[dict[str, Any]],
    ) -> ContextPackFeatureSection:
        sorting_layers: set[str] = set()
        physics_metadata: list[dict[str, Any]] = []
        scene_flow_metadata: list[dict[str, Any]] = []

        for scene in project_scenes:
            payload = self._load_scene_payload(scene.path)
            if payload is None:
                continue
            feature_metadata = payload.get("feature_metadata", {})
            if not isinstance(feature_metadata, dict):
                continue
            render_2d = feature_metadata.get("render_2d", {})
            if isinstance(render_2d, dict):
                for layer in render_2d.get("sorting_layers", []):
                    layer_name = str(layer or "").strip()
                    if layer_name:
                        sorting_layers.add(layer_name)
            physics_2d = feature_metadata.get("physics_2d", {})
            if isinstance(physics_2d, dict) and physics_2d:
                physics_metadata.append(
                    {
                        "scene_path": scene.path,
                        "backend": str(physics_2d.get("backend", "") or ""),
                        "layer_matrix": self._sorted_mapping(physics_2d.get("layer_matrix", {})),
                    }
                )
            scene_flow = feature_metadata.get("scene_flow", {})
            if isinstance(scene_flow, dict) and scene_flow:
                scene_flow_metadata.append(
                    {
                        "scene_path": scene.path,
                        "connections": {
                            str(key): self._normalize_rel_path(value)
                            for key, value in sorted(scene_flow.items())
                            if str(key).strip() and str(value).strip()
                        },
                    }
                )

        physics_backend_selection: dict[str, Any] = {}
        if self._api is not None:
            physics_backend_selection = self._sorted_mapping(self._api.get_physics_backend_selection())

        if transition_rows:
            for record in scene_flow_metadata:
                record["transition_count"] = sum(
                    1
                    for row in transition_rows
                    if str(row.get("source_scene_path", "") or "") == record["scene_path"]
                )

        physics_metadata.sort(key=lambda item: item["scene_path"].lower())
        scene_flow_metadata.sort(key=lambda item: item["scene_path"].lower())
        return ContextPackFeatureSection(
            sorting_layers=sorted(sorting_layers),
            physics_backend_selection=physics_backend_selection,
            physics_metadata=physics_metadata,
            scene_flow_metadata=scene_flow_metadata,
        )

    def _build_script_behaviour_section(
        self,
        *,
        project_scenes: list[ContextPackSceneRecord],
        prefabs: list[str],
    ) -> ContextPackScriptBehaviourSection:
        usages: list[ContextPackScriptBehaviourUsage] = []
        for scene in project_scenes:
            payload = self._load_scene_payload(scene.path)
            if payload is not None:
                usages.extend(self._extract_script_behaviours(payload, scene.path, ContextPackSourceKind.SCENE))
        for prefab_path in prefabs:
            payload = self._load_prefab_payload(prefab_path)
            if payload is not None:
                usages.extend(self._extract_script_behaviours(payload, prefab_path, ContextPackSourceKind.PREFAB))
        usages.sort(
            key=lambda item: (
                item.source_path.lower(),
                item.entity_name.lower(),
                item.module_path.lower(),
                item.script_path.lower(),
            )
        )
        return ContextPackScriptBehaviourSection(usages=usages)

    def _build_relevant_metadata(
        self,
        *,
        asset_records: list[ContextPackAssetRecord],
        prefabs: list[str],
        scripts: list[str],
        relevant_paths: set[str],
    ) -> list[ContextPackAssetMetadataRecord]:
        paths: set[str] = {
            self._normalize_rel_path(path)
            for path in prefabs + scripts
            if str(path).strip()
        }
        for record in asset_records:
            if record.asset_kind in {"scene_data", "prefab"}:
                paths.update(record.dependencies)
        paths.update(self._normalize_rel_path(path) for path in relevant_paths if str(path).strip())

        metadata_records: list[ContextPackAssetMetadataRecord] = []
        for path in sorted(paths):
            if not path:
                continue
            metadata = self._normalize_metadata(self._asset_service.load_metadata(path))
            metadata_records.append(
                ContextPackAssetMetadataRecord(
                    path=path,
                    guid=str(metadata.get("guid", "") or ""),
                    asset_kind=str(metadata.get("asset_kind", "") or ""),
                    importer=str(metadata.get("importer", "") or ""),
                    asset_type=str(metadata.get("asset_type", "") or ""),
                    import_mode=str(metadata.get("import_mode", "") or ""),
                    labels=sorted(str(label) for label in metadata.get("labels", []) if str(label).strip()),
                    dependencies=sorted(
                        self._normalize_rel_path(value)
                        for value in metadata.get("dependencies", [])
                        if str(value).strip()
                    ),
                    import_settings=self._sorted_mapping(metadata.get("import_settings", {})),
                    slices_count=len(metadata.get("slices", [])) if isinstance(metadata.get("slices"), list) else 0,
                )
            )
        return metadata_records

    def _list_project_prefabs(self) -> list[str]:
        prefabs_root = self._project_service.get_project_path("prefabs")
        if not prefabs_root.exists():
            return []
        return [
            self._project_service.to_relative_path(path)
            for path in sorted(prefabs_root.rglob("*.json"))
            if path.is_file() and not path.name.endswith(".meta.json")
        ]

    def _list_project_scripts(self) -> list[str]:
        scripts_root = self._project_service.get_project_path("scripts")
        if not scripts_root.exists():
            return []
        return [
            self._project_service.to_relative_path(path)
            for path in sorted(scripts_root.rglob("*.py"))
            if path.is_file() and not path.name.endswith(".meta.json")
        ]

    def _extract_script_behaviours(
        self,
        payload: dict[str, Any],
        source_path: str,
        source_kind: ContextPackSourceKind,
    ) -> list[ContextPackScriptBehaviourUsage]:
        usages: list[ContextPackScriptBehaviourUsage] = []
        entities = payload.get("entities", [])
        if not isinstance(entities, list):
            return usages
        for entity in entities:
            if not isinstance(entity, dict):
                continue
            components = entity.get("components", {})
            if not isinstance(components, dict):
                continue
            script_behaviour = components.get("ScriptBehaviour")
            if not isinstance(script_behaviour, dict):
                continue
            script_value = script_behaviour.get("script", {})
            script_path = ""
            if isinstance(script_value, dict):
                script_path = self._normalize_rel_path(script_value.get("path", ""))
            elif isinstance(script_value, str):
                script_path = self._normalize_rel_path(script_value)
            public_data = script_behaviour.get("public_data", {})
            public_data_shape = []
            if isinstance(public_data, dict):
                public_data_shape = [
                    ContextPackPublicDataField(key=str(key), value_type=self._value_type_name(value))
                    for key, value in sorted(public_data.items(), key=lambda item: str(item[0]).lower())
                    if str(key).strip()
                ]
            usages.append(
                ContextPackScriptBehaviourUsage(
                    source_kind=source_kind,
                    source_path=self._normalize_rel_path(source_path),
                    entity_name=str(entity.get("name", "") or ""),
                    script_path=script_path,
                    module_path=str(script_behaviour.get("module_path", "") or ""),
                    run_in_edit_mode=bool(script_behaviour.get("run_in_edit_mode", False)),
                    public_data_shape=public_data_shape,
                )
            )
        return usages

    def _load_scene_payload(self, scene_path: str) -> dict[str, Any] | None:
        return self._load_payload(scene_path, migrate_scene_data)

    def _load_prefab_payload(self, prefab_path: str) -> dict[str, Any] | None:
        return self._load_payload(prefab_path, migrate_prefab_data)

    def _load_payload(
        self,
        asset_path: str,
        migrate_fn: Any,
    ) -> dict[str, Any] | None:
        path = self._project_service.resolve_path(asset_path)
        if not path.exists():
            return None
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError, json.JSONDecodeError):
            return None
        if not isinstance(raw, dict):
            return None
        try:
            return migrate_fn(raw)
        except ValueError:
            return None

    def _normalize_transition_records(self, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        normalized: list[dict[str, Any]] = []
        for record in records:
            if not isinstance(record, dict):
                continue
            item = self._sorted_mapping(record)
            for key in (
                "source_scene_path",
                "target_scene_path",
                "source_scene_ref",
                "target_scene_ref",
            ):
                if key in item:
                    item[key] = self._normalize_rel_path(item[key])
            normalized.append(item)
        normalized.sort(
            key=lambda item: (
                str(item.get("source_scene_path", "") or item.get("source_scene_ref", "")).lower(),
                str(item.get("source_entity_name", "") or item.get("source_scene_name", "")).lower(),
                str(item.get("target_scene_path", "") or item.get("target_scene_ref", "")).lower(),
            )
        )
        return normalized

    def _normalize_scene_summary(self, summary: dict[str, Any]) -> dict[str, Any]:
        normalized = self._sorted_mapping(summary)
        if "path" in normalized:
            normalized["path"] = self._normalize_rel_path(normalized["path"])
        return normalized

    def _normalize_editor_state(self, state: dict[str, Any]) -> dict[str, Any]:
        recent_assets = state.get("recent_assets", {})
        scene_view_states = state.get("scene_view_states", {})
        return {
            "last_scene": self._normalize_rel_path(state.get("last_scene", "")),
            "preferences": self._sorted_mapping(state.get("preferences", {})),
            "recent_assets": {
                str(category): sorted(
                    self._normalize_rel_path(item)
                    for item in items
                    if str(item).strip()
                )
                for category, items in sorted(recent_assets.items())
                if isinstance(items, list)
            }
            if isinstance(recent_assets, dict)
            else {},
            "scene_view_states": {
                self._normalize_rel_path(key): self._sorted_mapping(value)
                for key, value in sorted(scene_view_states.items())
                if str(key).strip() and isinstance(value, dict)
            }
            if isinstance(scene_view_states, dict)
            else {},
        }

    def _normalize_metadata(self, metadata: dict[str, Any]) -> dict[str, Any]:
        normalized = self._sorted_mapping(metadata)
        if "source_path" in normalized:
            normalized["source_path"] = self._normalize_rel_path(normalized["source_path"])
        if "path" in normalized:
            normalized["path"] = self._normalize_rel_path(normalized["path"])
        if "dependencies" in normalized and isinstance(normalized["dependencies"], list):
            normalized["dependencies"] = sorted(
                self._normalize_rel_path(value)
                for value in normalized["dependencies"]
                if str(value).strip()
            )
        if "labels" in normalized and isinstance(normalized["labels"], list):
            normalized["labels"] = sorted(str(value) for value in normalized["labels"] if str(value).strip())
        return normalized

    def _sorted_mapping(self, value: Any) -> Any:
        if isinstance(value, dict):
            return {
                str(key): self._sorted_mapping(value[key])
                for key in sorted(value, key=lambda item: str(item).lower())
            }
        if isinstance(value, list):
            return [self._sorted_mapping(item) for item in value]
        return value

    def _normalize_rel_path(self, path: Any, *, allow_absolute: bool = False) -> str:
        value = str(path or "").strip()
        if not value:
            return ""
        normalized = value.replace("\\", "/")
        try:
            relative = self._project_service.to_relative_path(normalized)
        except Exception:
            relative = normalized
        if not allow_absolute and Path(relative).is_absolute():
            return normalized
        return str(relative).replace("\\", "/")

    def _value_type_name(self, value: Any) -> str:
        if value is None:
            return "null"
        if isinstance(value, bool):
            return "bool"
        if isinstance(value, int):
            return "int"
        if isinstance(value, float):
            return "float"
        if isinstance(value, str):
            return "str"
        if isinstance(value, list):
            return "list"
        if isinstance(value, dict):
            return "object"
        return type(value).__name__

    def _render_json(self, pack: ProjectContextPack) -> str:
        return json.dumps(pack.to_dict(), indent=2, sort_keys=True, ensure_ascii=True) + "\n"

    def _render_markdown(self, pack: ProjectContextPack) -> str:
        project = pack.project
        scenes = pack.scenes
        assets = pack.assets
        script_behaviours = pack.script_behaviours
        active_scene_path = str(scenes.active_scene.get("path", "") or "")
        lines = [
            "# AI Context Pack",
            "",
            "## Project",
            f"- Name: `{project.manifest.get('name', '')}`",
            f"- Startup scene: `{project.startup_scene}`",
            f"- Meta artifact: `{self.JSON_FILE_NAME}`",
            "",
            "## Scenes",
            f"- Project scenes: {len(scenes.project_scenes)}",
            f"- Active scene: `{active_scene_path}`" if active_scene_path else "- Active scene: `(none)`",
            f"- Open scenes: {len(scenes.open_scenes)}",
            f"- Transition rows: {len(scenes.transition_rows)}",
            "",
            "## Assets",
            f"- Catalog entries: {len(assets.catalog)}",
            f"- Prefabs: {len(assets.prefabs)}",
            f"- Scripts: {len(assets.scripts)}",
            f"- Relevant metadata entries: {len(assets.relevant_metadata)}",
            "",
            "## Features",
            f"- Sorting layers: {', '.join(pack.features.sorting_layers) if pack.features.sorting_layers else '(none)'}",
            f"- Physics scenes: {len(pack.features.physics_metadata)}",
            f"- Scene flow scenes: {len(pack.features.scene_flow_metadata)}",
            "",
            "## ScriptBehaviour",
            f"- Usage count: {len(script_behaviours.usages)}",
            f"- Modules: {', '.join(script_behaviours.module_paths) if script_behaviours.module_paths else '(none)'}",
        ]
        top_transitions = scenes.transition_rows[:5]
        if top_transitions:
            lines.extend(["", "## Transition Highlights"])
            for row in top_transitions:
                source_path = str(row.get("source_scene_path", "") or "")
                target_path = str(row.get("target_scene_path", "") or "")
                entry_id = str(row.get("target_entry_id", "") or "")
                suffix = f" [{entry_id}]" if entry_id else ""
                lines.append(f"- `{source_path}` -> `{target_path}`{suffix}")
        top_usages = script_behaviours.usages[:5]
        if top_usages:
            lines.extend(["", "## ScriptBehaviour Highlights"])
            for usage in top_usages:
                shape = ", ".join(f"{field.key}:{field.value_type}" for field in usage.public_data_shape) or "no public data"
                lines.append(
                    f"- `{usage.source_path}` / `{usage.entity_name}` -> `{usage.module_path or usage.script_path}` ({shape})"
                )
        return "\n".join(lines) + "\n"
