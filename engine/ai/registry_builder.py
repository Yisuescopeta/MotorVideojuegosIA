"""
engine/ai/registry_builder.py - Builder for AI capability registry

Builds and serializes the capability registry to motor_ai.json and START_HERE_AI.md.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from engine.ai.capability_registry import Capability, CapabilityExample, CapabilityRegistry
from engine.config import ENGINE_VERSION


class CapabilityRegistryBuilder:
    """
    Builder that constructs a CapabilityRegistry from known motor capabilities.
    """

    def __init__(self, engine_version: Optional[str] = None) -> None:
        self._registry = CapabilityRegistry(
            schema_version=1,
            engine_name="MotorVideojuegosIA",
            engine_version=engine_version or ENGINE_VERSION,
        )

    def build(self) -> CapabilityRegistry:
        """Build and return the full capability registry."""
        self._register_scene_capabilities()
        self._register_entity_capabilities()
        self._register_component_capabilities()
        self._register_asset_capabilities()
        self._register_slicing_capabilities()
        self._register_animator_capabilities()
        self._register_prefab_capabilities()
        self._register_project_capabilities()
        self._register_runtime_capabilities()
        self._register_physics_capabilities()
        self._register_introspection_capabilities()
        self._register_agent_capabilities()
        return self._registry

    def _register_scene_capabilities(self) -> None:
        self._add(Capability(
            id="scene:list",
            summary="List all available scenes in the project",
            mode="both",
            api_methods=["SceneWorkspaceAPI.list_project_scenes"],
            cli_command="motor scene list",
            example=CapabilityExample(
                description="List all scenes in the project",
                api_calls=[
                    {"method": "list_project_scenes", "args": {}},
                ],
                expected_outcome="Returns list of scene paths and names",
            ),
            notes="Searches levels/ directory for .json scene files.",
            tags=["scene", "query", "workspace"],
        ))

        self._add(Capability(
            id="scene:create",
            summary="Create a new scene with a unique file path",
            mode="both",
            api_methods=["SceneWorkspaceAPI.create_scene"],
            cli_command="motor scene create <name>",
            example=CapabilityExample(
                description="Create a new scene called 'Level 1'",
                api_calls=[
                    {"method": "create_scene", "args": {"name": "Level 1"}},
                ],
                expected_outcome="A new scene file is created at levels/level_1.json and becomes the active scene",
            ),
            notes="Scene name is sanitized to snake_case for the filename. Avoids collisions automatically.",
            tags=["scene", "authoring", "workspace"],
        ))

        self._add(Capability(
            id="scene:load",
            summary="Load a scene from a JSON file path",
            mode="both",
            api_methods=["SceneWorkspaceAPI.load_level", "SceneWorkspaceAPI.load_scene"],
            cli_command="motor scene load <path>",
            example=CapabilityExample(
                description="Load the intro scene",
                api_calls=[
                    {"method": "load_level", "args": {"path": "levels/intro.json"}},
                ],
                expected_outcome="The scene is loaded and becomes the active world",
            ),
            notes="Supports relative paths from project root. Creates world from serialized scene data.",
            tags=["scene", "workspace", "runtime"],
        ))

        self._add(Capability(
            id="scene:save",
            summary="Save the active scene to its source file",
            mode="edit",
            api_methods=["SceneWorkspaceAPI.save_scene"],
            cli_command="motor scene save [--project <path>]",
            example=CapabilityExample(
                description="Save the current scene",
                api_calls=[
                    {"method": "save_scene", "args": {}},
                ],
                expected_outcome="The active scene is serialized and written to its source_path",
            ),
            notes="Saves the currently active scene. Requires a scene to be loaded first.",
            tags=["scene", "persistence"],
        ))

        self._add(Capability(
            id="scene:flow:set_next",
            summary="Set the next scene connection for scene flow navigation",
            mode="edit",
            api_methods=["SceneWorkspaceAPI.set_next_scene"],
            cli_command="motor scene flow next <path>",
            example=CapabilityExample(
                description="Configure current scene to load level2 when triggered",
                api_calls=[
                    {"method": "set_next_scene", "args": {"path": "levels/level2.json"}},
                ],
                expected_outcome="Scene metadata updated with next_scene reference",
            ),
            notes="Stores relative path in scene metadata. Used by load_next_scene at runtime.",
            tags=["scene", "flow", "navigation"],
        ))

        self._add(Capability(
            id="scene:flow:load_next",
            summary="Load the configured next scene in the scene flow",
            mode="both",
            api_methods=["SceneWorkspaceAPI.load_next_scene"],
            cli_command="motor scene flow load-next",
            example=CapabilityExample(
                description="Transition to the next configured scene",
                api_calls=[
                    {"method": "load_next_scene", "args": {}},
                ],
                expected_outcome="The next_scene from current scene metadata is loaded",
            ),
            notes="Uses next_scene key from feature_metadata.scene_flow. Fails if not configured.",
            tags=["scene", "flow", "navigation", "runtime"],
        ))

    def _register_entity_capabilities(self) -> None:
        self._add(Capability(
            id="entity:create",
            summary="Create a new entity with optional components",
            mode="edit",
            api_methods=["AuthoringAPI.create_entity"],
            cli_command="motor entity create <name> [--components <json>]",
            example=CapabilityExample(
                description="Create a player entity with Transform",
                api_calls=[
                    {"method": "create_entity", "args": {
                        "name": "Player",
                        "components": {"Transform": {"x": 100, "y": 200}},
                    }},
                ],
                expected_outcome="Entity 'Player' exists in active scene with Transform component",
            ),
            notes="Entity names must be unique in the scene. Components are optional at creation. Use --components '{\"Transform\":{\"x\":100}}' to add components.",
            tags=["entity", "authoring"],
        ))

        self._add(Capability(
            id="entity:delete",
            summary="Remove an entity from the active scene, reparenting children to grandparent",
            mode="edit",
            api_methods=["AuthoringAPI.delete_entity"],
            cli_command="motor entity delete <name>",
            example=CapabilityExample(
                description="Delete the Player entity",
                api_calls=[
                    {"method": "delete_entity", "args": {"name": "Player"}},
                ],
                expected_outcome="Entity 'Player' is removed; any children are reparented to Player's parent (or unparented if Player had no parent). Children preserve their world transform.",
            ),
            notes="CHILDREN ARE NOT DELETED - they are reparented to the deleted entity's parent (grandparent). Their local transforms are recalculated to preserve world position. Use remove_entity_subtree for recursive deletion. Cannot be undone automatically.",
            tags=["entity", "authoring"],
        ))

        self._add(Capability(
            id="entity:parent",
            summary="Set or change an entity's parent for hierarchical transforms",
            mode="edit",
            api_methods=["AuthoringAPI.set_entity_parent"],
            cli_command="motor entity parent <child> <parent>",
            example=CapabilityExample(
                description="Parent a weapon to the player",
                api_calls=[
                    {"method": "set_entity_parent", "args": {"name": "Sword", "parent_name": "Player"}},
                ],
                expected_outcome="Sword becomes a child of Player and inherits its transform",
            ),
            notes="Pass None/null as parent to unparent. Child transform is applied relative to parent.",
            tags=["entity", "hierarchy", "transform"],
        ))

        self._add(Capability(
            id="entity:list",
            summary="List all entities in the active scene, optionally filtered",
            mode="both",
            api_methods=["RuntimeAPI.list_entities"],
            cli_command="motor entity list [--tag <tag>] [--layer <layer>] [--active-only]",
            example=CapabilityExample(
                description="List all active entities with the 'Enemy' tag",
                api_calls=[
                    {"method": "list_entities", "args": {"tag": "Enemy", "active": True}},
                ],
                expected_outcome="Returns list of EntityData for matching entities",
            ),
            notes="Filtering is optional. Returns empty list if no entities match.",
            tags=["entity", "query", "runtime"],
        ))

    def _register_component_capabilities(self) -> None:
        self._add(Capability(
            id="component:add",
            summary="Add a component to an existing entity",
            mode="edit",
            api_methods=["AuthoringAPI.add_component"],
            cli_command="motor component add <entity> <component> [--data <json>]",
            example=CapabilityExample(
                description="Add a Sprite to the Player",
                api_calls=[
                    {"method": "add_component", "args": {
                        "entity_name": "Player",
                        "component_name": "Sprite",
                        "data": {"asset_path": "assets/player.png"},
                    }},
                ],
                expected_outcome="Player entity now has a Sprite component",
            ),
            notes="Component data is optional; defaults are used if not provided. Fails if component already exists. Use canonical component names from the component registry.",
            tags=["component", "authoring"],
        ))

        self._add(Capability(
            id="component:edit",
            summary="Edit a property of an existing component",
            mode="edit",
            api_methods=["AuthoringAPI.edit_component"],
            cli_command="motor component edit <entity> <component> <property> <value>",
            example=CapabilityExample(
                description="Move player to x=200",
                api_calls=[
                    {"method": "edit_component", "args": {
                        "entity_name": "Player",
                        "component": "Transform",
                        "property": "x",
                        "value": 200,
                    }},
                ],
                expected_outcome="Player's Transform.x is updated to 200",
            ),
            notes="Property names are component-specific. Type conversion is automatic.",
            tags=["component", "authoring"],
        ))

        self._add(Capability(
            id="component:remove",
            summary="Remove a component from an entity",
            mode="edit",
            api_methods=["AuthoringAPI.remove_component"],
            cli_command="motor component remove <entity> <component>",
            example=CapabilityExample(
                description="Remove the Collider from an entity",
                api_calls=[
                    {"method": "remove_component", "args": {
                        "entity_name": "Player",
                        "component_name": "Collider",
                    }},
                ],
                expected_outcome="Collider component is removed from Player",
            ),
            notes="Some components (like Transform) are required and cannot be removed. Use canonical component names from the component registry.",
            tags=["component", "authoring"],
        ))

    def _register_asset_capabilities(self) -> None:
        self._add(Capability(
            id="asset:list",
            summary="List all assets in the project catalog",
            mode="both",
            api_methods=["AssetsProjectAPI.list_project_assets"],
            cli_command="motor asset list [--search <query>]",
            example=CapabilityExample(
                description="List all sprite assets",
                api_calls=[
                    {"method": "list_project_assets", "args": {"search": "sprite"}},
                ],
                expected_outcome="Returns filtered list of asset records with paths and guids",
            ),
            notes="Search matches against asset paths. Results include guid, path, asset_kind, importer.",
            tags=["asset", "query"],
        ))

        self._add(Capability(
            id="asset:find",
            summary="Find assets by kind, importer, or extension",
            mode="both",
            api_methods=["AssetsProjectAPI.find_assets"],
            cli_command="motor asset find [--kind <kind>] [--importer <importer>] [--ext <ext>]",
            example=CapabilityExample(
                description="Find all texture assets",
                api_calls=[
                    {"method": "find_assets", "args": {"asset_kind": "texture"}},
                ],
                expected_outcome="Returns list of texture assets with metadata",
            ),
            notes="Multiple filters can be combined. Empty result means no matches.",
            tags=["asset", "query"],
        ))

        self._add(Capability(
            id="asset:metadata:get",
            summary="Get metadata for a specific asset",
            mode="both",
            api_methods=["AssetsProjectAPI.get_asset_metadata"],
            cli_command="motor asset metadata <path>",
            example=CapabilityExample(
                description="Get metadata for player.png",
                api_calls=[
                    {"method": "get_asset_metadata", "args": {"asset_path": "assets/player.png"}},
                ],
                expected_outcome="Returns asset metadata including guid, importer settings, dependencies",
            ),
            notes="Metadata includes slices if the asset has been sliced.",
            tags=["asset", "metadata"],
        ))

        self._add(Capability(
            id="asset:refresh",
            summary="Refresh the asset catalog and detect changes",
            mode="both",
            api_methods=["AssetsProjectAPI.refresh_asset_catalog"],
            cli_command="motor asset refresh",
            example=CapabilityExample(
                description="Refresh asset catalog",
                api_calls=[
                    {"method": "refresh_asset_catalog", "args": {}},
                ],
                expected_outcome="Asset catalog is updated with any new or modified assets",
            ),
            notes="Run this after adding new files to assets/ folder.",
            tags=["asset", "catalog"],
        ))

    def _register_slicing_capabilities(self) -> None:
        self._add(Capability(
            id="asset:slice:grid",
            summary="Create grid-based slices from a sprite sheet asset",
            mode="edit",
            api_methods=["AssetsProjectAPI.create_grid_slices"],
            cli_command="motor asset slice grid <asset> --cell-width <w> --cell-height <h>",
            example=CapabilityExample(
                description="Slice a 256x256 sprite sheet into 32x32 tiles",
                api_calls=[
                    {"method": "create_grid_slices", "args": {
                        "asset_path": "assets/tiles.png",
                        "cell_width": 32,
                        "cell_height": 32,
                        "margin": 0,
                        "spacing": 0,
                    }},
                ],
                expected_outcome="Asset metadata updated with grid-based slice definitions",
            ),
            notes="Creates uniform slices based on cell size. Non-uniform regions require manual slicing.",
            tags=["asset", "slicing", "sprite"],
        ))

        self._add(Capability(
            id="asset:slice:list",
            summary="List all slices defined for an asset",
            mode="both",
            api_methods=["AssetsProjectAPI.list_asset_slices"],
            cli_command="motor asset slice list <asset>",
            example=CapabilityExample(
                description="List slices for player sprite sheet",
                api_calls=[
                    {"method": "list_asset_slices", "args": {"asset_path": "assets/player.png"}},
                ],
                expected_outcome="Returns list of slice definitions with names and rectangles",
            ),
            notes="Slices are stored in asset metadata and referenced by name in Animator.",
            tags=["asset", "slicing"],
        ))

        self._add(Capability(
            id="asset:slice:auto",
            summary="Auto-detect slices from a sprite sheet asset",
            mode="edit",
            api_methods=["AssetsProjectAPI.preview_auto_slices", "AssetsProjectAPI.create_auto_slices"],
            cli_command="motor asset slice auto <asset> [--preview]",
            example=CapabilityExample(
                description="Auto-detect slices for player sprite",
                api_calls=[
                    {"method": "create_auto_slices", "args": {"asset_path": "assets/player.png"}},
                ],
                expected_outcome="Slices auto-detected and saved to asset metadata",
            ),
            notes="Uses alpha channel to detect sprite boundaries. Preview mode shows detections without saving.",
            tags=["asset", "slicing", "sprite"],
        ))

        self._add(Capability(
            id="asset:slice:manual",
            summary="Save manually defined slices for an asset",
            mode="edit",
            api_methods=["AssetsProjectAPI.save_manual_slices"],
            cli_command="motor asset slice manual <asset> --slices <json>",
            example=CapabilityExample(
                description="Save manual slice definitions",
                api_calls=[
                    {"method": "save_manual_slices", "args": {
                        "asset_path": "assets/player.png",
                        "slices": [{"name": "idle_0", "x": 0, "y": 0, "width": 32, "height": 32}],
                    }},
                ],
                expected_outcome="Manual slices saved to asset metadata",
            ),
            notes="Use for non-uniform sprites that don't fit grid or auto-detection.",
            tags=["asset", "slicing", "sprite"],
        ))

    def _register_animator_capabilities(self) -> None:
        self._add(Capability(
            id="animator:ensure",
            summary="Ensure Animator exists on entity with optional sheet (creates or updates)",
            mode="edit",
            api_methods=["AuthoringAPI.add_component", "AuthoringAPI.set_animator_sprite_sheet"],
            cli_command="motor animator ensure <entity> [--sheet <asset>]",
            example=CapabilityExample(
                description="Ensure Player has Animator with sprite sheet",
                api_calls=[
                    {"method": "add_component", "args": {
                        "entity_name": "Player",
                        "component_name": "Animator",
                        "data": {"enabled": True, "speed": 1.0, "sprite_sheet": "assets/player.png"},
                    }},
                ],
                expected_outcome="Animator exists on Player with sprite_sheet set to assets/player.png (created if missing, sheet updated if different)",
            ),
            notes="Idempotent operation. If Animator does NOT exist: creates it with the provided sheet. If Animator ALREADY exists and no sheet provided: succeeds without changes. If Animator ALREADY exists and sheet provided: updates the sheet. This provides a single-command 'ensure exists with this configuration' workflow ideal for headless automation.",
            tags=["animator", "setup", "idempotent"],
        ))

        self._add(Capability(
            id="animator:set_sheet",
            summary="Set the sprite sheet asset for an Animator",
            mode="edit",
            api_methods=["AuthoringAPI.set_animator_sprite_sheet"],
            cli_command="motor animator set-sheet <entity> <asset>",
            example=CapabilityExample(
                description="Set player sprite sheet",
                api_calls=[
                    {"method": "set_animator_sprite_sheet", "args": {
                        "entity_name": "Player",
                        "asset_path": "assets/player.png",
                    }},
                ],
                expected_outcome="Player's Animator now references the specified sprite sheet",
            ),
            notes="The asset must have slices defined. Used before creating animation states. Requires Animator to already exist; use 'animator ensure' if you need to create and set sheet in one operation.",
            tags=["animator", "setup"],
        ))

        self._add(Capability(
            id="animator:state:create",
            summary="Create or update an animation state",
            mode="edit",
            api_methods=["AuthoringAPI.upsert_animator_state"],
            cli_command="motor animator state create <entity> <state> --slices <slices...> [--fps <n>] [--loop|--no-loop] [--set-default] [--auto-create]",
            example=CapabilityExample(
                description="Create idle animation state using slice_0 through slice_3",
                api_calls=[
                    {"method": "upsert_animator_state", "args": {
                        "entity_name": "Player",
                        "state_name": "idle",
                        "slice_names": ["slice_0", "slice_1", "slice_2", "slice_3"],
                        "fps": 8,
                        "loop": True,
                    }},
                ],
                expected_outcome="'idle' state created on Player's Animator (upserts if exists)",
            ),
            notes="Upserts: creates if not exists, updates if exists. Use --auto-create to create Animator component if missing. First state becomes default. --loop enables looping (default), --no-loop disables it.",
            tags=["animator", "animation", "state"],
        ))

        self._add(Capability(
            id="animator:state:remove",
            summary="Remove an animation state from an Animator",
            mode="edit",
            api_methods=["AuthoringAPI.remove_animator_state"],
            cli_command="motor animator state remove <entity> <state>",
            example=CapabilityExample(
                description="Remove the unused 'hurt' state",
                api_calls=[
                    {"method": "remove_animator_state", "args": {
                        "entity_name": "Player",
                        "state_name": "hurt",
                    }},
                ],
                expected_outcome="'hurt' state removed. Default and current state updated if they referenced 'hurt'. Any on_complete references to 'hurt' are cleared (set to null).",
            ),
            notes="CAN remove the last state (schema allows empty animations object). When the last state is removed, default_state is set to the removed state's name as a placeholder (schema requires non-empty string). When removing a state, on_complete references pointing to it from other states are automatically cleared.",
            tags=["animator", "animation", "state"],
        ))

        self._add(Capability(
            id="animator:info",
            summary="Get detailed information about an entity's Animator",
            mode="both",
            api_methods=["AuthoringAPI.get_animator_info"],
            cli_command="motor animator info <entity>",
            example=CapabilityExample(
                description="Get animator details for Player",
                api_calls=[
                    {"method": "get_animator_info", "args": {"entity_name": "Player"}},
                ],
                expected_outcome="Returns sprite_sheet, frame size, states list with durations",
            ),
            notes="Useful for debugging animation states and verifying configuration.",
            tags=["animator", "query"],
        ))

    def _register_prefab_capabilities(self) -> None:
        self._add(Capability(
            id="prefab:create",
            summary="Create a prefab asset from an existing entity subtree",
            mode="edit",
            api_methods=["SceneWorkspaceAPI.create_prefab"],
            cli_command="motor prefab create <entity> <path> [--replace-original] [--instance-name <name>] [--project <path>]",
            example=CapabilityExample(
                description="Create an enemy prefab from an existing entity",
                api_calls=[
                    {"method": "create_prefab", "args": {
                        "entity_name": "EnemyTemplate",
                        "path": "prefabs/enemy.prefab",
                        "replace_original": True,
                    }},
                ],
                expected_outcome="Writes prefabs/enemy.prefab and optionally replaces the original subtree with a linked instance",
            ),
            notes="Creates a prefab asset through the public authoring route. With --replace-original it swaps the subtree for a linked prefab instance.",
            tags=["prefab", "authoring"],
        ))

        self._add(Capability(
            id="prefab:instantiate",
            summary="Create an entity instance from a prefab file",
            mode="edit",
            api_methods=["SceneWorkspaceAPI.instantiate_prefab"],
            cli_command="motor prefab instantiate <path> [--name <name>] [--parent <parent>] [--project <path>]",
            example=CapabilityExample(
                description="Instantiate an enemy prefab",
                api_calls=[
                    {"method": "instantiate_prefab", "args": {
                        "path": "prefabs/enemy.prefab",
                        "name": "Enemy_01",
                    }},
                ],
                expected_outcome="Entity 'Enemy_01' created with all prefab components",
            ),
            notes="Creates a linked instance. Changes to prefab can be propagated to instances.",
            tags=["prefab", "authoring"],
        ))

        self._add(Capability(
            id="prefab:unpack",
            summary="Convert a prefab instance to a regular entity",
            mode="edit",
            api_methods=["SceneWorkspaceAPI.unpack_prefab"],
            cli_command="motor prefab unpack <entity> [--project <path>]",
            example=CapabilityExample(
                description="Unpack Enemy_01 to modify it independently",
                api_calls=[
                    {"method": "unpack_prefab", "args": {"entity_name": "Enemy_01"}},
                ],
                expected_outcome="Entity is no longer linked to prefab, becomes editable",
            ),
            notes="Breaks the prefab link. Entity keeps its components but won't receive prefab updates.",
            tags=["prefab", "authoring"],
        ))

        self._add(Capability(
            id="prefab:apply",
            summary="Apply instance overrides back to the source prefab",
            mode="edit",
            api_methods=["SceneWorkspaceAPI.apply_prefab_overrides"],
            cli_command="motor prefab apply <entity> [--project <path>]",
            example=CapabilityExample(
                description="Apply Enemy_01 changes to the prefab",
                api_calls=[
                    {"method": "apply_prefab_overrides", "args": {"entity_name": "Enemy_01"}},
                ],
                expected_outcome="Prefab file is updated with the instance's overrides",
            ),
            notes="Only works on prefab instances. Updates the source .prefab file.",
            tags=["prefab", "authoring"],
        ))

        self._add(Capability(
            id="prefab:list",
            summary="List all prefabs available in the project",
            mode="both",
            api_methods=["AssetsProjectAPI.list_project_prefabs"],
            cli_command="motor prefab list [--project <path>]",
            example=CapabilityExample(
                description="List all prefabs",
                api_calls=[
                    {"method": "list_project_prefabs", "args": {}},
                ],
                expected_outcome="Returns list of prefab paths",
            ),
            notes="Searches prefabs/ directory and lists .prefab and .json files.",
            tags=["prefab", "query"],
        ))

    def _register_project_capabilities(self) -> None:
        self._add(Capability(
            id="project:bootstrap-ai",
            summary="Generate AI bootstrap files (motor_ai.json and START_HERE_AI.md)",
            mode="both",
            api_methods=["ProjectService.generate_ai_bootstrap"],
            cli_command="motor project bootstrap-ai",
            example=CapabilityExample(
                description="Generate AI bootstrap files for the project",
                api_calls=[
                    {"method": "generate_ai_bootstrap", "args": {}},
                ],
                expected_outcome="motor_ai.json and START_HERE_AI.md are created in project root",
            ),
            notes="Regenerates the AI-facing documentation files. Safe to run multiple times (idempotent).",
            tags=["project", "bootstrap", "ai"],
        ))

        self._add(Capability(
            id="project:open",
            summary="Open a different project and load its startup scene",
            mode="both",
            api_methods=["AssetsProjectAPI.open_project"],
            cli_command="motor project open <path>",
            example=CapabilityExample(
                description="Open the platformer project",
                api_calls=[
                    {"method": "open_project", "args": {"path": "projects/platformer"}},
                ],
                expected_outcome="Project is opened and last scene (or first available) is loaded",
            ),
            notes="Switches the active project context. Unsaved changes in current project may be lost.",
            tags=["project", "workspace"],
        ))

        self._add(Capability(
            id="project:manifest",
            summary="Get the current project's manifest summary",
            mode="both",
            api_methods=["AssetsProjectAPI.get_project_manifest"],
            cli_command="motor project info",
            example=CapabilityExample(
                description="Get project manifest",
                api_calls=[
                    {"method": "get_project_manifest", "args": {}},
                ],
                expected_outcome="Returns project name, root, paths, engine_version",
            ),
            notes="Read-only. Use for discovering project structure programmatically.",
            tags=["project", "query"],
        ))

        self._add(Capability(
            id="project:editor_state",
            summary="Get or set editor state including recent assets and last scene",
            mode="edit",
            api_methods=["AssetsProjectAPI.get_editor_state", "AssetsProjectAPI.save_editor_state"],
            cli_command="motor project state [get|set] [data...]",
            example=CapabilityExample(
                description="Get current editor state",
                api_calls=[
                    {"method": "get_editor_state", "args": {}},
                ],
                expected_outcome="Returns recent_assets, last_scene, open_scenes, preferences",
            ),
            notes="Editor state is persisted in .motor/editor_state.json",
            tags=["project", "state"],
        ))

    def _register_runtime_capabilities(self) -> None:
        self._add(Capability(
            id="runtime:play",
            summary="Start play mode to test game logic",
            mode="edit",
            api_methods=["RuntimeAPI.play"],
            cli_command="motor runtime play",
            example=CapabilityExample(
                description="Start play mode",
                api_calls=[
                    {"method": "play", "args": {}},
                ],
                expected_outcome="Engine enters PLAY mode, scripts with run_in_edit_mode execute",
            ),
            notes="Only available in EDIT mode. Scripts can control entities during play.",
            tags=["runtime", "play"],
        ))

        self._add(Capability(
            id="runtime:stop",
            summary="Stop play mode and return to edit mode",
            mode="play",
            api_methods=["RuntimeAPI.stop"],
            cli_command="motor runtime stop",
            example=CapabilityExample(
                description="Stop play mode",
                api_calls=[
                    {"method": "stop", "args": {}},
                ],
                expected_outcome="Engine returns to EDIT mode, world state is restored",
            ),
            notes="Restores world to pre-play state. Autosave may preserve changes.",
            tags=["runtime", "play"],
        ))

        self._add(Capability(
            id="runtime:step",
            summary="Advance the simulation by N frames",
            mode="play",
            api_methods=["RuntimeAPI.step"],
            cli_command="motor runtime step [--frames <n>]",
            example=CapabilityExample(
                description="Advance simulation by 10 frames",
                api_calls=[
                    {"method": "step", "args": {"frames": 10}},
                ],
                expected_outcome="World updates for 10 frames",
            ),
            notes="Useful for debugging. Can be called during play or step-through mode.",
            tags=["runtime", "play"],
        ))

        self._add(Capability(
            id="runtime:undo",
            summary="Undo the last edit operation",
            mode="edit",
            api_methods=["RuntimeAPI.undo"],
            cli_command="motor undo",
            example=CapabilityExample(
                description="Undo last edit",
                api_calls=[
                    {"method": "undo", "args": {}},
                ],
                expected_outcome="Last change is reverted",
            ),
            notes="Uses scene manager's change tracking. Not all operations are undoable.",
            tags=["runtime", "edit"],
        ))

        self._add(Capability(
            id="runtime:redo",
            summary="Redo a previously undone operation",
            mode="edit",
            api_methods=["RuntimeAPI.redo"],
            cli_command="motor redo",
            example=CapabilityExample(
                description="Redo last undone operation",
                api_calls=[
                    {"method": "redo", "args": {}},
                ],
                expected_outcome="Previously undone change is reapplied",
            ),
            notes="Only available if undo was called. Cleared on new edits.",
            tags=["runtime", "edit"],
        ))

    def _register_physics_capabilities(self) -> None:
        self._add(Capability(
            id="physics:query:aabb",
            summary="Query physics entities within an axis-aligned bounding box",
            mode="both",
            api_methods=["RuntimeAPI.query_physics_aabb"],
            cli_command="motor physics query aabb <left> <top> <right> <bottom>",
            example=CapabilityExample(
                description="Find entities in region (100,100) to (300,300)",
                api_calls=[
                    {"method": "query_physics_aabb", "args": {
                        "left": 100, "top": 100, "right": 300, "bottom": 300,
                    }},
                ],
                expected_outcome="Returns list of entities with colliders in the region",
            ),
            notes="Uses active physics backend. Results include entity names and collision data.",
            tags=["physics", "query", "collision"],
        ))

        self._add(Capability(
            id="physics:query:ray",
            summary="Cast a ray and find intersecting physics bodies",
            mode="both",
            api_methods=["RuntimeAPI.query_physics_ray"],
            cli_command="motor physics query ray <ox> <oy> <dx> <dy> <max_dist>",
            example=CapabilityExample(
                description="Cast ray from player position looking right",
                api_calls=[
                    {"method": "query_physics_ray", "args": {
                        "origin_x": 100, "origin_y": 200,
                        "direction_x": 1, "direction_y": 0,
                        "max_distance": 500,
                    }},
                ],
                expected_outcome="Returns hit information sorted by distance",
            ),
            notes="Direction is normalized. Returns empty list if no hits.",
            tags=["physics", "query", "collision"],
        ))

        self._add(Capability(
            id="physics:backend:list",
            summary="List available physics backends and their status",
            mode="both",
            api_methods=["RuntimeAPI.list_physics_backends", "RuntimeAPI.get_physics_backend_selection"],
            cli_command="motor physics backends",
            example=CapabilityExample(
                description="List physics backends",
                api_calls=[
                    {"method": "list_physics_backends", "args": {}},
                ],
                expected_outcome="Returns list of backends with availability status",
            ),
            notes="Backends include 'legacy_aabb' (always available) and optional 'box2d'.",
            tags=["physics", "query"],
        ))

    def _register_introspection_capabilities(self) -> None:
        self._add(Capability(
            id="introspect:doctor",
            summary="Diagnose project health and detect issues",
            mode="both",
            api_methods=["CapabilityRegistry.cmd_doctor"],
            cli_command="motor doctor [--project <path>]",
            example=CapabilityExample(
                description="Check project health",
                api_calls=[
                    {"method": "cmd_doctor", "args": {"project_path": ".", "json_output": True}},
                ],
                expected_outcome="Returns diagnostic report with checks, warnings, and recommendations",
            ),
            notes="Read-only operation. Validates project.json, motor_ai.json, START_HERE_AI.md, and directory structure.",
            tags=["introspection", "diagnostics"],
        ))

        self._add(Capability(
            id="introspect:capabilities",
            summary="Query this capability registry itself",
            mode="both",
            api_methods=["CapabilityRegistry.cmd_capabilities"],
            cli_command="motor capabilities [--json]",
            example=CapabilityExample(
                description="List all capabilities in JSON format",
                api_calls=[
                    {"method": "cmd_capabilities", "args": {"json_output": True}},
                ],
                expected_outcome="Returns full capability registry as JSON",
            ),
            notes="The registry is accessible via 'motor capabilities' CLI command. Use for discovering available operations.",
            tags=["introspection", "meta"],
        ))

        self._add(Capability(
            id="introspect:entity",
            summary="Get full data for a specific entity",
            mode="both",
            api_methods=["RuntimeAPI.get_entity"],
            cli_command="motor entity inspect <name>",
            example=CapabilityExample(
                description="Get Player entity data",
                api_calls=[
                    {"method": "get_entity", "args": {"name": "Player"}},
                ],
                expected_outcome="Returns EntityData with all components and values",
            ),
            notes="Throws EntityNotFoundError if entity doesn't exist.",
            tags=["introspection", "entity"],
        ))

        self._add(Capability(
            id="introspect:status",
            summary="Get engine status including FPS, entity count, time",
            mode="both",
            api_methods=["RuntimeAPI.get_status"],
            cli_command="motor status",
            example=CapabilityExample(
                description="Get engine status",
                api_calls=[
                    {"method": "get_status", "args": {}},
                ],
                expected_outcome="Returns state, frame, time, fps, entity_count",
            ),
            notes="Lightweight status check. Safe to call frequently.",
            tags=["introspection", "runtime"],
        ))

    def _register_agent_capabilities(self) -> None:
        self._add(Capability(
            id="agent:session:create",
            summary="Create an experimental clean-room agent session inside the engine",
            mode="both",
            api_methods=["AgentAPI.create_agent_session"],
            cli_command="motor agent session create",
            example=CapabilityExample(
                description="Create a confirm-actions agent session",
                api_calls=[
                    {"method": "create_agent_session", "args": {"permission_mode": "confirm_actions"}},
                ],
                expected_outcome="Returns a session id and empty session state",
            ),
            notes="Experimental/tooling API and CLI. Uses an offline deterministic test provider by default.",
            tags=["agent", "experimental", "tooling"],
        ))

        self._add(Capability(
            id="agent:message:send",
            summary="Send a message to an engine-native agent session",
            mode="both",
            api_methods=["AgentAPI.send_agent_message"],
            cli_command="motor agent message send <session> <message>",
            example=CapabilityExample(
                description="Ask the fake provider to read a project file",
                api_calls=[
                    {
                        "method": "send_agent_message",
                        "args": {"session_id": "agent-session-id", "message": "read README.md"},
                    },
                ],
                expected_outcome="The session records the user message, assistant response and tool result or pending action",
            ),
            notes="Experimental/tooling API. Mutating tool calls require approval unless the session is full_access.",
            tags=["agent", "experimental", "tooling"],
        ))

        self._add(Capability(
            id="agent:action:approve",
            summary="Approve or reject a pending agent action",
            mode="both",
            api_methods=["AgentAPI.approve_agent_action"],
            cli_command="motor agent action approve <session> <action>",
            example=CapabilityExample(
                description="Approve a pending file write",
                api_calls=[
                    {
                        "method": "approve_agent_action",
                        "args": {"session_id": "agent-session-id", "action_id": "agent-action-id", "approved": True},
                    },
                ],
                expected_outcome="The pending action is executed and audited",
            ),
            notes="Experimental/tooling API. Hard guards still block unsafe paths and obvious secrets.",
            tags=["agent", "experimental", "permissions"],
        ))

        self._add(Capability(
            id="agent:runtime",
            summary="Run the v3 clean-room agent turn loop with provider/tool-result continuation",
            mode="both",
            api_methods=["AgentAPI.send_agent_message", "AgentAPI.approve_agent_action"],
            cli_command="motor agent message send <session> <message>",
            example=CapabilityExample(
                description="Send a message that may trigger tools and continue after tool results",
                api_calls=[
                    {
                        "method": "send_agent_message",
                        "args": {"session_id": "agent-session-id", "message": "read README.md"},
                    },
                ],
                expected_outcome="The session records provider events, tool results and a final assistant response",
            ),
            notes="Experimental/tooling. Fake/replay remain offline test providers; OpenAI is available as opt-in online provider requiring environment credentials.",
            tags=["agent", "experimental", "runtime"],
        ))

        self._add(Capability(
            id="agent:providers:list",
            summary="List configured agent providers and metadata",
            mode="both",
            api_methods=["AgentAPI.list_agent_providers"],
            cli_command="motor agent providers list",
            example=CapabilityExample(
                description="List offline and online agent provider adapters",
                api_calls=[
                    {"method": "list_agent_providers", "args": {}},
                ],
                expected_outcome="Returns provider ids, kind, credential requirements, streaming and usage support",
            ),
            notes="OpenAI is listed as online and requires OPENAI_API_KEY; fake/replay are test-only.",
            tags=["agent", "experimental", "providers"],
        ))

        self._add(Capability(
            id="agent:session:compact",
            summary="Compact an agent session transcript into local memory",
            mode="both",
            api_methods=["AgentAPI.compact_agent_session"],
            cli_command="motor agent session compact <session>",
            example=CapabilityExample(
                description="Compact an agent session",
                api_calls=[
                    {"method": "compact_agent_session", "args": {"session_id": "agent-session-id"}},
                ],
                expected_outcome="Stores a sanitized session summary and keeps recent messages",
            ),
            notes="Experimental/tooling. Protected paths and obvious secrets are excluded from memory summaries.",
            tags=["agent", "experimental", "memory"],
        ))

        self._add(Capability(
            id="agent:session:inspect",
            summary="Inspect an agent session without mutating it",
            mode="both",
            api_methods=["AgentAPI.inspect_agent_session"],
            cli_command="motor agent session inspect <session>",
            example=CapabilityExample(
                description="Inspect session state and runtime config",
                api_calls=[
                    {"method": "inspect_agent_session", "args": {"session_id": "agent-session-id"}},
                ],
                expected_outcome="Returns schema, provider, pending actions, runtime config and usage counts",
            ),
            notes="Read-only diagnostic command for migrated or manually edited sessions.",
            tags=["agent", "experimental", "diagnostics"],
        ))

        self._add(Capability(
            id="agent:usage",
            summary="Show token and cost usage recorded for an agent session",
            mode="both",
            api_methods=["AgentAPI.get_agent_usage"],
            cli_command="motor agent usage <session>",
            example=CapabilityExample(
                description="Inspect session token usage",
                api_calls=[
                    {"method": "get_agent_usage", "args": {"session_id": "agent-session-id"}},
                ],
                expected_outcome="Returns usage records and totals; cost is unknown unless pricing is configured",
            ),
            notes="Cost is never invented. It remains unknown when provider usage or prices are unavailable.",
            tags=["agent", "experimental", "usage"],
        ))

        self._add(Capability(
            id="agent:tools",
            summary="List and execute safe engine-native agent tools through the v2 tool pipeline",
            mode="both",
            api_methods=["AgentAPI.list_agent_tools", "AgentAPI.send_agent_message"],
            cli_command="motor agent message send <session> /tools",
            example=CapabilityExample(
                description="Ask the session to list available tools",
                api_calls=[
                    {"method": "list_agent_tools", "args": {}},
                ],
                expected_outcome="Returns tool specs with permission and preview metadata",
            ),
            notes="Tools validate input, build previews, resolve permissions, execute and map tool_result records.",
            tags=["agent", "experimental", "tools"],
        ))

        self._add(Capability(
            id="agent:permissions",
            summary="Suspend mutating agent tools for approval and resume the same logical turn",
            mode="both",
            api_methods=["AgentAPI.approve_agent_action"],
            cli_command="motor agent action approve <session> <action>",
            example=CapabilityExample(
                description="Approve a pending write and continue the agent turn",
                api_calls=[
                    {
                        "method": "approve_agent_action",
                        "args": {"session_id": "agent-session-id", "action_id": "agent-action-id", "approved": True},
                    },
                ],
                expected_outcome="The action emits a tool_result and the provider receives the result for continuation",
            ),
            notes="Modes are confirm_actions and full_access. Hard guards still apply in both modes.",
            tags=["agent", "experimental", "permissions"],
        ))

        self._add(Capability(
            id="agent:editor_panel",
            summary="Use the Agent panel next to Terminal with a live engine port",
            mode="both",
            api_methods=["AgentAPI.get_agent_session", "AgentAPI.send_agent_message"],
            cli_command="motor agent message send <session> /status",
            example=CapabilityExample(
                description="Inspect agent status from the same session model used by the editor panel",
                api_calls=[
                    {"method": "send_agent_message", "args": {"session_id": "agent-session-id", "message": "/status"}},
                ],
                expected_outcome="Returns session mode, pending actions and provider state",
            ),
            notes="UI capability documented for AI discovery; runtime-bound EngineAPI construction is internal editor tooling, not a core API.",
            tags=["agent", "experimental", "editor", "tooling"],
        ))

    # Capabilities that are planned but not yet implemented.
    # These do NOT have corresponding implementations in the official motor CLI parser.
    # They are API-level capabilities that may be used programmatically but are not
    # exposed through the CLI yet.
    _PLANNED_CAPABILITIES: set[str] = {
        # Scene flow (no CLI commands exist)
        "scene:flow:set_next",
        "scene:flow:load_next",

        # Entity operations beyond create (no CLI commands exist)
        "entity:delete",
        "entity:parent",
        "entity:list",
        "introspect:entity",  # motor entity inspect not in parser

        # Component operations beyond add (no CLI commands exist)
        "component:edit",
        "component:remove",

        # Asset operations beyond list/slice (no CLI commands exist)
        "asset:find",
        "asset:metadata:get",
        "asset:refresh",

        # Project operations beyond info/bootstrap-ai (no CLI commands exist)
        "project:open",
        "project:editor_state",

        # Runtime operations (no CLI commands exist)
        "runtime:play",
        "runtime:stop",
        "runtime:step",
        "runtime:undo",
        "runtime:redo",

        # Physics operations (no CLI commands exist)
        "physics:query:aabb",
        "physics:query:ray",
        "physics:backend:list",

        # Introspection beyond capabilities (no CLI command exists)
        "introspect:status",

    }

    def _add(self, capability: Capability) -> None:
        """Helper to add a capability to the registry with appropriate status."""
        # Determine status based on capability ID
        if capability.id in self._PLANNED_CAPABILITIES:
            # Recreate capability with planned status
            from dataclasses import replace
            capability = replace(capability, status="planned")
        self._registry.register(capability)


class MotorAIBootstrapBuilder:
    """
    Serializes a CapabilityRegistry to motor_ai.json and START_HERE_AI.md.
    """

    def __init__(self, registry: CapabilityRegistry) -> None:
        self._registry = registry

    def build_motor_ai_json(self, project_data: Optional[Dict[str, Any]] = None) -> str:
        """
        Build the motor_ai.json content.

        Args:
            project_data: Optional project-specific data to include (name, root, entrypoints, etc.)
        """
        # Build implemented capabilities list (AI-facing contract)
        implemented_caps = [
            {
                "id": cap.id,
                "summary": cap.summary,
                "mode": cap.mode,
                "status": cap.status,
                "api_methods": cap.api_methods,
                "cli_command": cap.cli_command,
                "example": {
                    "description": cap.example.description,
                    "api_calls": cap.example.api_calls,
                    "expected_outcome": cap.example.expected_outcome,
                },
                "notes": cap.notes,
                "tags": cap.tags,
            }
            for cap in sorted(self._registry.list_implemented(), key=lambda c: c.id)
        ]

        # Build planned capabilities list (roadmap)
        planned_caps = [
            {
                "id": cap.id,
                "summary": cap.summary,
                "mode": cap.mode,
                "status": cap.status,
                "api_methods": cap.api_methods,
                "cli_command": cap.cli_command,
                "example": {
                    "description": cap.example.description,
                    "api_calls": cap.example.api_calls,
                    "expected_outcome": cap.example.expected_outcome,
                },
                "notes": cap.notes,
                "tags": cap.tags,
            }
            for cap in sorted(self._registry.list_planned(), key=lambda c: c.id)
        ]

        data: Dict[str, Any] = {
            "schema_version": 3,  # Updated to 3 for status field and separated capabilities
            "engine": {
                "name": self._registry.engine_name,
                "version": self._registry.engine_version,
                "api_version": "1",
                "capabilities_schema_version": self._registry.schema_version,
            },
            "implemented_capabilities": implemented_caps,
            "planned_capabilities": planned_caps,
            "capability_counts": {
                "implemented": len(implemented_caps),
                "planned": len(planned_caps),
                "total": len(implemented_caps) + len(planned_caps),
            },
        }

        if project_data:
            data["project"] = project_data.get("project", {})
            data["entrypoints"] = project_data.get("entrypoints", {})

        return json.dumps(data, indent=4, ensure_ascii=True, sort_keys=False) + "\n"

    def build_start_here_md(self, project_name: str = "Untitled Project") -> str:
        """Build the START_HERE_AI.md content."""
        lines: List[str] = [
            "# MotorVideojuegosIA - AI Quick Start",
            "",
            f"**Project**: {project_name}",
            f"**Engine Version**: {self._registry.engine_version}",
            "",
            "## Overview",
            "This project uses MotorVideojuegosIA, a 2D game engine designed for AI-assisted development.",
            "",
            "## Implemented Capabilities",
            "",
            "The entries below are available now and are safe to use from the CLI.",
            "",
            "### Most Common Operations",
            "",
        ]

        # Only implemented capabilities - verified to exist in CLI
        common_caps = [
            "scene:load", "scene:save", "scene:create",
            "entity:create",
            "component:add",
            "asset:list", "asset:slice:grid", "asset:slice:list",
            "animator:set_sheet", "animator:state:create", "animator:info",
            "introspect:capabilities",
        ]

        for cap_id in common_caps:
            cap = self._registry.get(cap_id)
            if cap:
                lines.append(f"- **{cap.id}**: {cap.summary}")
                lines.append(f"  - API: `{cap.api_methods[0]}`")
                lines.append(f"  - CLI: `{cap.cli_command}`")
                lines.append("")

        lines.extend([
            "## Capabilities by Category",
            "",
        ])

        categories: Dict[str, List[str]] = {
            "Scene Management": ["scene:"],
            "Entity Operations": ["entity:"],
            "Component Operations": ["component:"],
            "Asset Management": ["asset:"],
            "Animation": ["animator:"],
            "Prefabs": ["prefab:"],
            "Project": ["project:"],
            "Runtime": ["runtime:"],
            "Physics": ["physics:"],
            "Introspection": ["introspect:"],
        }

        for category_name, prefixes in categories.items():
            caps = [
                cap for cap in self._registry.list_implemented()
                if any(cap.id.startswith(p) for p in prefixes)
            ]
            if caps:
                lines.append(f"### {category_name}")
                lines.append("")
                for cap in sorted(caps, key=lambda c: c.id):
                    lines.append(f"- `{cap.id}`: {cap.summary}")
                lines.append("")

        planned = self._registry.list_planned()
        if planned:
            lines.extend([
                "## Coming Soon",
                "",
                "These capabilities are planned but **not yet available** via the CLI.",
                "Do not attempt to use them — the `motor` CLI does not expose them.",
                "They are listed here so an AI knows they exist in the engine",
                "and should not be attempted until they are marked as `implemented`.",
                "",
            ])
            lines.append("| Capability | Summary |")
            lines.append("|-----------|---------|")
            for cap in sorted(planned, key=lambda c: c.id):
                lines.append(f"| `{cap.id}` | {cap.summary} |")
            lines.append("")
            lines.append("> **Note**: Use `motor capabilities --json` to check which are now available.")
            lines.append("")

        lines.extend([
            "## Full Capability Registry",
            "",
            "See `motor_ai.json` for the complete machine-readable registry including:",
            "- All capability IDs and summaries",
            "- Required API methods with signatures",
            "- CLI command templates",
            "- Working examples for each capability",
            "- Mode restrictions (edit/play/both)",
            "- Explicit separation of `implemented` vs `planned` capabilities",
            "",
            "## Getting Started",
            "",
            "### Quick Workflow",
            "",
            "1. **Check project health**:",
            "   ```bash",
            "   motor doctor --project . --json",
            "   ```",
            "",
            "2. **Create a scene**:",
            "   ```bash",
            "   motor scene create \"Level 1\" --project .",
            "   ```",
            "",
            "3. **Create an entity**:",
            "   ```bash",
            "   motor entity create Player --project . --json",
            "   ```",
            "",
            "4. **Add a component**:",
            "   ```bash",
            '   motor component add Player Transform --data \'{"x": 100, "y": 200}\' --project .',
            "   ```",
            "",
            "5. **Slice a sprite sheet**:",
            "   ```bash",
            "   motor asset slice grid assets/player.png --cell-width 32 --cell-height 32 --project .",
            "   ```",
            "",
            "6. **Configure animator**:",
            "   ```bash",
            "   motor animator ensure Player --project .",
            "   motor animator set-sheet Player assets/player.png --project .",
            "   motor animator state create Player idle --slices idle_0,idle_1,idle_2,idle_3 --fps 8 --loop --project .",
            "   ```",
            "",
            "### Regenerate AI Bootstrap Files",
            "",
            "If these files are missing or outdated, regenerate them with:",
            "```bash",
            "motor project bootstrap-ai --project .",
            "```",
            "",
            "### Discover Capabilities",
            "",
            "List all available capabilities:",
            "```bash",
            "motor capabilities --json",
            "```",
            "",
            "## Naming Conventions",
            "",
            "- **Capability IDs**: `scope:action` (e.g., `scene:load`, `entity:create`)",
            "- **CLI Commands**: `motor <scope> <action>` (e.g., `motor scene load`)",
            "- **API Methods**: `ScopeAPI.method_name` (e.g., `SceneWorkspaceAPI.load_level`)",
            "",
            "## Official CLI",
            "",
            "This project uses the official `motor` CLI:",
            "- Entrypoint: `motor [command] [options]`",
            "- Alternative: `python -m motor [command] [options]`",
            "- Legacy: `python -m tools.engine_cli` (deprecated, for compatibility only)",
            "",
        ])

        return "\n".join(lines) + "\n"

    def write_to_project(
        self,
        project_root: Path,
        project_data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Path]:
        """
        Write both motor_ai.json and START_HERE_AI.md to the project root.

        Returns:
            Dict with paths to the written files.
        """
        motor_ai_content = self.build_motor_ai_json(project_data)
        start_here_content = self.build_start_here_md(
            project_data.get("project", {}).get("name", "Untitled Project") if project_data else "Untitled Project"
        )

        motor_ai_path = project_root / "motor_ai.json"
        start_here_path = project_root / "START_HERE_AI.md"

        motor_ai_path.write_text(motor_ai_content, encoding="utf-8")
        start_here_path.write_text(start_here_content, encoding="utf-8")

        return {
            "motor_ai_json": motor_ai_path,
            "start_here_md": start_here_path,
        }


def get_default_registry(engine_version: Optional[str] = None) -> CapabilityRegistry:
    """Get the default, fully populated capability registry."""
    return CapabilityRegistryBuilder(engine_version=engine_version).build()
