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
            engine_name="OpenGame",
            engine_version=engine_version or ENGINE_VERSION,
        )

    def build(self) -> CapabilityRegistry:
        """Build and return the full capability registry."""
        self._register_scene_capabilities()
        self._register_game_capabilities()
        self._register_entity_capabilities()
        self._register_component_capabilities()
        self._register_asset_capabilities()
        self._register_slicing_capabilities()
        self._register_animator_capabilities()
        self._register_prefab_capabilities()
        self._register_ai_capabilities()
        self._register_project_capabilities()
        self._register_recipe_capabilities()
        self._register_runtime_capabilities()
        self._register_physics_capabilities()
        self._register_introspection_capabilities()
        self._register_agent_capabilities()
        self._register_signal_capabilities()
        self._register_ui_capabilities()
        self._register_mobile_capabilities()
        self._register_export_capabilities()
        self._register_editor_capabilities()
        self._register_debug_capabilities()
        self._register_service_capabilities()
        self._register_entity_group_capabilities()
        return self._registry

    def _register_export_capabilities(self) -> None:
        self._add(Capability(
            id="export:presets:list",
            summary="List export presets configured for the project",
            mode="both",
            api_methods=["ExportAPI.list_export_presets"],
            cli_command="motor export presets list [--project <path>] [--json]",
            example=CapabilityExample(
                description="List export presets",
                api_calls=[{"method": "list_export_presets", "args": {}}],
                expected_outcome="Returns configured export presets",
            ),
            notes="Reads export_presets.motor.json from the project root.",
            tags=["export", "build", "presets"],
        ))

        self._add(Capability(
            id="export:presets:validate",
            summary="Validate export presets and project paths",
            mode="both",
            api_methods=["ExportAPI.validate_export_preset"],
            cli_command="motor export presets validate [--project <path>] [--json]",
            example=CapabilityExample(
                description="Validate all export presets",
                api_calls=[{"method": "validate_export_preset", "args": {}}],
                expected_outcome="Returns actionable preset validation errors or success",
            ),
            notes="Validates schema, entry scene, output path and platform options.",
            tags=["export", "validation", "presets"],
        ))

        self._add(Capability(
            id="export:doctor",
            summary="Check export toolchains and external SDK availability",
            mode="both",
            api_methods=["ExportAPI.export_doctor"],
            cli_command="motor export doctor [--project <path>] [--json]",
            example=CapabilityExample(
                description="Check export environment",
                api_calls=[{"method": "export_doctor", "args": {}}],
                expected_outcome="Reports PyInstaller, Android SDK, Java, Gradle and OS data",
            ),
            notes="Read-only diagnostic; warnings are not build success claims.",
            tags=["export", "doctor", "toolchain"],
        ))

        self._add(Capability(
            id="export:pack",
            summary="Build deterministic content pack for an export preset",
            mode="both",
            api_methods=["ExportAPI.export_pack"],
            cli_command="motor export pack <preset> [--project <path>] [--json]",
            example=CapabilityExample(
                description="Pack Windows Desktop content",
                api_calls=[{"method": "export_pack", "args": {"name": "Windows Desktop"}}],
                expected_outcome="Writes game.manifest.json, game.pak and staged content",
            ),
            notes="Uses reachable content graph unless debug/include_all_assets is enabled.",
            tags=["export", "content", "pack"],
        ))

        self._add(Capability(
            id="export:build",
            summary="Build a playable export artifact for one preset",
            mode="both",
            api_methods=["ExportAPI.build_export"],
            cli_command="motor export build <preset> [--project <path>] [--json]",
            example=CapabilityExample(
                description="Build Windows Desktop export",
                api_calls=[{"method": "build_export", "args": {"name": "Windows Desktop"}}],
                expected_outcome="Builds artifact or returns TOOLCHAIN_UNAVAILABLE with report",
            ),
            notes="Does not use main.py editor as exported game entrypoint.",
            tags=["export", "build", "runtime"],
        ))

        self._add(Capability(
            id="export:build-all",
            summary="Build all configured export presets",
            mode="both",
            api_methods=["ExportAPI.build_all_exports"],
            cli_command="motor export build-all [--project <path>] [--json]",
            example=CapabilityExample(
                description="Build all exports",
                api_calls=[{"method": "build_all_exports", "args": {}}],
                expected_outcome="Returns per-preset build results and reports",
            ),
            notes="Overall command fails if any preset build fails.",
            tags=["export", "build", "automation"],
        ))

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
            cli_command="motor scene flow set-link <source_scene> <target_scene>",
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
            mode="play",
            api_methods=["SceneWorkspaceAPI.load_next_scene"],
            cli_command="motor scene flow next",
            example=CapabilityExample(
                description="Load the next scene",
                api_calls=[
                    {"method": "load_next_scene", "args": {}},
                ],
                expected_outcome="Next scene is loaded as the active world",
            ),
            notes="Uses next_scene key from feature_metadata.scene_flow. Fails if not configured.",
            tags=["scene", "flow", "navigation", "runtime"],
        ))

        self._add(Capability(
            id="scene:flow:menu",
            summary="Load the menu scene configured in the scene flow",
            mode="play",
            api_methods=["SceneWorkspaceAPI.load_menu_scene"],
            cli_command="motor scene flow menu",
            example=CapabilityExample(
                description="Load the menu scene",
                api_calls=[
                    {"method": "load_menu_scene", "args": {}},
                ],
                expected_outcome="Menu scene is loaded as the active world",
            ),
            notes="Uses menu_scene key from feature_metadata.scene_flow. Fails if not configured.",
            tags=["scene", "flow", "navigation", "runtime"],
        ))

    def _register_game_capabilities(self) -> None:
        self._add(Capability(
            id="game:platformer:create",
            summary="Create a minimal native 2D platformer scene scaffold",
            mode="edit",
            api_methods=["SceneWorkspaceAPI.create_scene", "AuthoringAPI.create_entity", "AuthoringAPI.create_camera2d"],
            cli_command="motor game platformer create <name> [--project <path>]",
            example=CapabilityExample(
                description="Create a minimal platformer scene called 'Level 1'",
                api_calls=[
                    {"method": "create_scene", "args": {"name": "Level 1"}},
                    {"method": "create_entity", "args": {"name": "Player"}},
                    {"method": "create_camera2d", "args": {"name": "MainCamera"}},
                ],
                expected_outcome="Creates levels/level_1.json with Player, Ground, Goal and MainCamera, then updates startup_scene",
            ),
            notes="Uses only public EngineAPI authoring surfaces. Creates Player with Transform, Collider, RigidBody, InputMap and PlayerController2D. Uses entity-based Ground and Goal instead of Tilemap or scripts.",
            tags=["game", "platformer", "authoring", "scaffold"],
        ))

        self._add(Capability(
            id="game:platformer:add-player",
            summary="Create or update the native platformer Player in the selected scene",
            mode="edit",
            api_methods=["AuthoringAPI.create_entity", "AuthoringAPI.replace_component_data", "SceneWorkspaceAPI.save_scene"],
            cli_command="motor game platformer add-player [--x <px>] [--y <px>] [--project <path>]",
            example=CapabilityExample(
                description="Ensure Player at pixel position (100, 300)",
                api_calls=[
                    {"method": "create_entity", "args": {"name": "Player"}},
                    {"method": "save_scene", "args": {}},
                ],
                expected_outcome="Selected scene contains Player with Transform, Collider, RigidBody, InputMap and PlayerController2D",
            ),
            notes="Selects active scene, editor_state.active_scene, startup_scene or first loadable levels scene. Does not use last_scene.",
            tags=["game", "platformer", "authoring"],
        ))

        self._add(Capability(
            id="game:platformer:add-ground",
            summary="Create or update native platformer Ground in the selected scene",
            mode="edit",
            api_methods=["AuthoringAPI.create_entity", "AuthoringAPI.replace_component_data", "SceneWorkspaceAPI.save_scene"],
            cli_command="motor game platformer add-ground [--from-x <cell>] [--to-x <cell>] [--y <cell>] [--name <entity>] [--project <path>]",
            example=CapabilityExample(
                description="Ensure ground from grid cell 0 to 20 at row 8",
                api_calls=[
                    {"method": "create_entity", "args": {"name": "Ground"}},
                    {"method": "save_scene", "args": {}},
                ],
                expected_outcome="Selected scene contains Ground with Transform and non-trigger Collider",
            ),
            notes="Grid units use 64 pixels. from-x/to-x form a half-open range [from-x,to-x). Without --name, creates the next Ground_###. With --name, updates that entity if it exists.",
            tags=["game", "platformer", "authoring"],
        ))

        self._add(Capability(
            id="game:platformer:add-platform",
            summary="Create or update native platformer Platform in the selected scene",
            mode="edit",
            api_methods=["AuthoringAPI.create_entity", "AuthoringAPI.replace_component_data", "SceneWorkspaceAPI.save_scene"],
            cli_command="motor game platformer add-platform [--x <cell>] [--y <cell>] [--width <cells>] [--name <entity>] [--project <path>]",
            example=CapabilityExample(
                description="Ensure a platform at grid cell x=5 y=6 width=3",
                api_calls=[
                    {"method": "create_entity", "args": {"name": "Platform"}},
                    {"method": "save_scene", "args": {}},
                ],
                expected_outcome="Selected scene contains Platform with Transform and non-trigger Collider",
            ),
            notes="Grid units use 64 pixels. x is the left grid cell and width is measured in grid cells. Without --name, creates the next Platform_###. With --name, updates that entity if it exists.",
            tags=["game", "platformer", "authoring"],
        ))

        self._add(Capability(
            id="game:platformer:add-goal",
            summary="Create or update native platformer Goal in the selected scene",
            mode="edit",
            api_methods=["AuthoringAPI.create_entity", "AuthoringAPI.replace_component_data", "SceneWorkspaceAPI.save_scene"],
            cli_command="motor game platformer add-goal [--x <px>] [--y <px>] [--name <entity>] [--project <path>]",
            example=CapabilityExample(
                description="Ensure Goal at pixel position (1100, 200)",
                api_calls=[
                    {"method": "create_entity", "args": {"name": "Goal"}},
                    {"method": "save_scene", "args": {}},
                ],
                expected_outcome="Selected scene contains Goal with Transform, trigger Collider and Goal2D",
            ),
            notes="Uses no concrete asset references. Without --name, creates Goal when missing, otherwise the next Goal_###. With --name, updates that entity if it exists.",
            tags=["game", "platformer", "authoring"],
        ))

        self._add(Capability(
            id="game:platformer:add-coin",
            summary="Create or update native platformer Coin in the selected scene",
            mode="edit",
            api_methods=["AuthoringAPI.create_entity", "AuthoringAPI.replace_component_data", "SceneWorkspaceAPI.save_scene"],
            cli_command="motor game platformer add-coin [--x <px>] [--y <px>] [--points <int>] [--name <entity>] [--project <path>]",
            example=CapabilityExample(
                description="Ensure Coin at pixel position (320, 200)",
                api_calls=[
                    {"method": "create_entity", "args": {"name": "Coin"}},
                    {"method": "save_scene", "args": {}},
                ],
                expected_outcome="Selected scene contains Coin with Transform, trigger Collider and Collectible2D",
            ),
            notes="Uses semantic Collectible2D data; no external scripts. Without --name, creates the next Coin_###. With --name, updates that entity if it exists.",
            tags=["game", "platformer", "authoring"],
        ))

        self._add(Capability(
            id="game:platformer:add-hazard",
            summary="Create or update native platformer Hazard in the selected scene",
            mode="edit",
            api_methods=["AuthoringAPI.create_entity", "AuthoringAPI.replace_component_data", "SceneWorkspaceAPI.save_scene"],
            cli_command="motor game platformer add-hazard [--x <px>] [--y <px>] [--damage <int>] [--name <entity>] [--project <path>]",
            example=CapabilityExample(
                description="Ensure Hazard at pixel position (640, 300)",
                api_calls=[
                    {"method": "create_entity", "args": {"name": "Hazard"}},
                    {"method": "save_scene", "args": {}},
                ],
                expected_outcome="Selected scene contains Hazard with Transform, trigger Collider and Hazard2D",
            ),
            notes="Uses semantic Hazard2D data; no external scripts. Without --name, creates the next Hazard_###. With --name, updates that entity if it exists.",
            tags=["game", "platformer", "authoring"],
        ))

        self._add(Capability(
            id="game:platformer:add-respawn",
            summary="Create or update native platformer RespawnPoint in the selected scene",
            mode="edit",
            api_methods=["AuthoringAPI.create_entity", "AuthoringAPI.replace_component_data", "SceneWorkspaceAPI.save_scene"],
            cli_command="motor game platformer add-respawn [--x <px>] [--y <px>] [--id <id>] [--project <path>]",
            example=CapabilityExample(
                description="Ensure default respawn point at pixel position (100, 300)",
                api_calls=[
                    {"method": "create_entity", "args": {"name": "Respawn_default"}},
                    {"method": "save_scene", "args": {}},
                ],
                expected_outcome="Selected scene contains Respawn_default with Transform and RespawnPoint2D",
            ),
            notes="Entity name is Respawn_<id> using a safe id suffix. Uses no external scripts.",
            tags=["game", "platformer", "authoring"],
        ))

        self._add(Capability(
            id="game:platformer:add-moving-platform",
            summary="Create or update a named native moving platform in the selected scene",
            mode="edit",
            api_methods=["AuthoringAPI.create_entity", "AuthoringAPI.replace_component_data", "SceneWorkspaceAPI.save_scene"],
            cli_command="motor game platformer add-moving-platform --name <entity> --x <px> --y <px> --width <px> --height <px> --to-x <px> --to-y <px> --speed <px_per_sec> [--project <path>]",
            example=CapabilityExample(
                description="Ensure Lift_A moves between two pixel positions",
                api_calls=[
                    {"method": "create_entity", "args": {"name": "Lift_A"}},
                    {"method": "save_scene", "args": {}},
                ],
                expected_outcome="Selected scene contains Lift_A with Transform, Collider and MovingPlatform2D",
            ),
            notes="Requires --name for idempotent authoring. Runtime-supported by Gameplay2DSemanticSystem: moves along the serialized path, emits moving_platform_started, moving_platform_reached_point and moving_platform_completed, and can carry Player when Player Collider rests on the platform Collider before frame movement. Rider support is minimal, Player-focused, Collider/AABB-based, and does not persist runtime progress. moving_platform_rider_attached, moving_platform_rider_moved and moving_platform_rider_detached are planned, not current public events.",
            tags=["game", "platformer", "authoring"],
        ))

        self._add(Capability(
            id="game:platformer:add-enemy-patrol",
            summary="Create or update a named native enemy patrol in the selected scene",
            mode="edit",
            api_methods=["AuthoringAPI.create_entity", "AuthoringAPI.replace_component_data", "SceneWorkspaceAPI.save_scene"],
            cli_command="motor game platformer add-enemy-patrol --name <entity> --x <px> --y <px> --point <x,y> [--point <x,y> ...] --damage <int> --speed <px_per_sec> [--project <path>]",
            example=CapabilityExample(
                description="Ensure Slime_A has two patrol points",
                api_calls=[
                    {"method": "create_entity", "args": {"name": "Slime_A"}},
                    {"method": "save_scene", "args": {}},
                ],
                expected_outcome="Selected scene contains Slime_A with Transform, trigger Collider and EnemyPatrol2D",
            ),
            notes="Requires --name. Patrol points use x,y pixel pairs. Runtime-supported by Gameplay2DSemanticSystem: EnemyPatrol2D patrols cyclically through patrol_points when entity active + component enabled + 2+ points + speed > 0. Emits enemy_patrol_started and enemy_patrol_reached_point. On contact with Player emits enemy_touched, then respawns Player using session checkpoint/runtime respawn or first active RespawnPoint2D; if none exists emits enemy_respawn_missing. If EnemyPatrol2D and Hazard2D coexist on the same entity, EnemyPatrol2D (when enabled) absorbs the interaction to avoid double damage/double respawn. No health or advanced pathfinding.",
            tags=["game", "platformer", "authoring"],
        ))

        self._add(Capability(
            id="game:platformer:add-checkpoint",
            summary="Create or update a named native checkpoint in the selected scene",
            mode="edit",
            api_methods=["AuthoringAPI.create_entity", "AuthoringAPI.replace_component_data", "SceneWorkspaceAPI.save_scene"],
            cli_command="motor game platformer add-checkpoint --name <entity> --x <px> --y <px> --id <id> [--project <path>]",
            example=CapabilityExample(
                description="Ensure Checkpoint_A uses checkpoint id cp_a",
                api_calls=[
                    {"method": "create_entity", "args": {"name": "Checkpoint_A"}},
                    {"method": "save_scene", "args": {}},
                ],
                expected_outcome="Selected scene contains Checkpoint_A with Transform, trigger Collider, Checkpoint2D and RespawnPoint2D",
            ),
            notes="Requires --name. Runtime-supported by Gameplay2DSemanticSystem: touching Player emits checkpoint event and can activate a session respawn. Adds RespawnPoint2D with the same id for simple gameplay2d compatibility.",
            tags=["game", "platformer", "authoring"],
        ))

        self._add(Capability(
            id="game:platformer:add-killzone",
            summary="Create or update a named native killzone in the selected scene",
            mode="edit",
            api_methods=["AuthoringAPI.create_entity", "AuthoringAPI.replace_component_data", "SceneWorkspaceAPI.save_scene"],
            cli_command="motor game platformer add-killzone --name <entity> --x <px> --y <px> --width <px> --height <px> --damage <int> [--project <path>]",
            example=CapabilityExample(
                description="Ensure Pit_A is a killzone trigger",
                api_calls=[
                    {"method": "create_entity", "args": {"name": "Pit_A"}},
                    {"method": "save_scene", "args": {}},
                ],
                expected_outcome="Selected scene contains Pit_A with Transform, trigger Collider and KillZone2D",
            ),
            notes="Requires --name. Runtime-supported by Gameplay2DSemanticSystem: touching Player emits killzone event and can respawn at the active checkpoint or first active RespawnPoint2D.",
            tags=["game", "platformer", "authoring"],
        ))

        self._add(Capability(
            id="game:platformer:set-camera-follow",
            summary="Create or update Camera2D follow settings in the selected platformer scene",
            mode="edit",
            api_methods=["AuthoringAPI.create_entity", "AuthoringAPI.replace_component_data", "SceneWorkspaceAPI.save_scene"],
            cli_command="motor game platformer set-camera-follow --name <camera> --target <entity> [--offset-x <px>] [--offset-y <px>] [--dead-zone-width <px>] [--dead-zone-height <px>] [--zoom <float>] [--project <path>]",
            example=CapabilityExample(
                description="Make MainCamera follow Player",
                api_calls=[
                    {"method": "replace_component_data", "args": {"entity_name": "MainCamera", "component_name": "Camera2D"}},
                    {"method": "save_scene", "args": {}},
                ],
                expected_outcome="Selected scene has MainCamera Camera2D.follow_entity set to Player",
            ),
            notes="Uses existing Camera2D fields instead of adding a CameraFollowTarget2D component.",
            tags=["game", "platformer", "authoring", "camera"],
        ))

        self._add(Capability(
            id="game:platformer:set-bounds",
            summary="Create or update native platformer level bounds in the selected scene",
            mode="edit",
            api_methods=["AuthoringAPI.create_entity", "AuthoringAPI.replace_component_data", "SceneWorkspaceAPI.save_scene"],
            cli_command="motor game platformer set-bounds --name <entity> --left <px> --right <px> --top <px> --bottom <px> [--camera <camera>] [--project <path>]",
            example=CapabilityExample(
                description="Set level bounds and clamp MainCamera",
                api_calls=[
                    {"method": "create_entity", "args": {"name": "LevelBounds"}},
                    {"method": "save_scene", "args": {}},
                ],
                expected_outcome="Selected scene contains LevelBounds2D and optional Camera2D clamp values",
            ),
            notes="Requires --name. Runtime-supported by Gameplay2DSemanticSystem: Player exits emit level_bounds_exited, horizontal exits clamp x, and bottom exits respawn or emit level_bounds_respawn_missing. If --camera is provided, Camera2D clamp fields are synchronized.",
            tags=["game", "platformer", "authoring", "camera"],
        ))

        self._add(Capability(
            id="game:platformer:validate",
            summary="Validate selected native platformer scene contract",
            mode="both",
            api_methods=["SceneWorkspaceAPI.load_scene_for_runtime_inspection", "RuntimeAPI.list_entities", "AssetsProjectAPI.run_ai_compliance"],
            cli_command="motor game platformer validate [--project <path>]",
            example=CapabilityExample(
                description="Validate the selected platformer scene",
                api_calls=[
                    {"method": "list_entities", "args": {}},
                ],
                expected_outcome="Reports scene, Player, terrain, Goal, loadability and strict compliance checks",
            ),
            notes="Read-only. Uses same scene target rule as incremental platformer authoring commands.",
            tags=["game", "platformer", "validation", "read-only"],
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
            cli_command="motor entity set-parent <entity_id> <parent_id>",
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
            id="entity:create-child",
            summary="Create a child entity under a parent",
            mode="edit",
            api_methods=["AuthoringAPI.create_child_entity"],
            cli_command="motor entity create-child <parent_id> --name <name>",
            example=CapabilityExample(
                description="Create a Hitbox child under Player",
                api_calls=[
                    {"method": "create_child_entity", "args": {"parent_name": "Player", "name": "Hitbox"}},
                ],
                expected_outcome="Hitbox entity created as child of Player",
            ),
            notes="Auto-saves scene after creation. Child inherits parent transform hierarchy.",
            tags=["entity", "hierarchy", "authoring"],
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

    def _register_ai_capabilities(self) -> None:
        self._add(Capability(
            id="ai:start",
            summary="Show the compact AI entrypoint contract for this project",
            mode="both",
            api_methods=["CapabilityRegistry.cmd_ai_start"],
            cli_command="motor ai start [--project <path>] [--json]",
            example=CapabilityExample(
                description="Load the project contract an AI assistant should follow first",
                api_calls=[
                    {"method": "cmd_ai_start", "args": {"project_path": ".", "json_output": True}},
                ],
                expected_outcome="Returns engine identity, official CLI/API, scene context, initial commands, workflows and anti-runtime rules",
            ),
            notes="Read-only. This is the recommended first command for AI assistants working on a project.",
            tags=["ai", "introspection", "bootstrap", "contract"],
        ))

        self._add(Capability(
            id="ai:compliance",
            summary="Validate whether a project follows the AI-native engine contract",
            mode="both",
            api_methods=["AssetsProjectAPI.run_ai_compliance"],
            cli_command="motor ai compliance [--project <path>] [--strict] [--json]",
            example=CapabilityExample(
                description="Run strict AI compliance checks after a change",
                api_calls=[
                    {"method": "run_ai_compliance", "args": {"strict": True}},
                ],
                expected_outcome="Returns native score, strict status, runtime warnings and next actions",
            ),
            notes="Read-only. Strict mode fails on suspicious external runtimes or missing native loadable scenes.",
            tags=["ai", "introspection", "validation", "compliance"],
        ))

        self._add(Capability(
            id="ai:self-test",
            summary="Run a controlled AI self-test workflow in a temporary project by default",
            mode="both",
            api_methods=["CapabilityRegistry.cmd_ai_self_test"],
            cli_command="motor ai self-test [--project <path>] [--profile platformer] [--in-place] [--json]",
            example=CapabilityExample(
                description="Run the platformer AI self-test without mutating the real project",
                api_calls=[
                    {"method": "cmd_ai_self_test", "args": {
                        "project_path": ".",
                        "profile": "platformer",
                        "in_place": False,
                        "json_output": True,
                    }},
                ],
                expected_outcome="Creates a temporary platformer project, validates authoring/runtime/compliance, reports JSON, then removes the temporary workspace",
            ),
            notes="Uses the bundled platformer-basic recipe through allowlisted motor commands. By default it creates a temporary project under .motor/tmp, runs validations, and removes that workspace. It does not mutate the real project unless --in-place is provided.",
            tags=["ai", "validation", "self-test", "ci", "workflow"],
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

    def _register_recipe_capabilities(self) -> None:
        self._add(Capability(
            id="recipe:list",
            summary="List bundled declarative AI recipes",
            mode="both",
            api_methods=["RecipeRegistry.list_recipes"],
            cli_command="motor recipe list [--project <path>]",
            example=CapabilityExample(
                description="List available bundled recipes",
                api_calls=[
                    {"method": "list_recipes", "args": {}},
                ],
                expected_outcome="Returns bundled recipe metadata including platformer-basic and platformer-advanced",
            ),
            notes="Read-only. Recipes are bundled under engine/recipes and are not loaded from arbitrary project files.",
            tags=["recipe", "ai", "workflow", "tooling"],
        ))

        self._add(Capability(
            id="recipe:show",
            summary="Show a bundled declarative AI recipe",
            mode="both",
            api_methods=["RecipeRegistry.get_recipe"],
            cli_command="motor recipe show <id> [--project <path>]",
            example=CapabilityExample(
                description="Show the platformer-advanced recipe",
                api_calls=[
                    {"method": "get_recipe", "args": {"recipe_id": "platformer-advanced"}},
                ],
                expected_outcome="Returns recipe version, expected capabilities, steps and validation commands",
            ),
            notes="Read-only. Does not mutate project files.",
            tags=["recipe", "ai", "workflow", "tooling", "query"],
        ))

        self._add(Capability(
            id="recipe:run",
            summary="Run a bundled declarative AI recipe through allowlisted motor commands",
            mode="edit",
            api_methods=["RecipeRunner.run_recipe"],
            cli_command="motor recipe run <id> [--project <path>]",
            example=CapabilityExample(
                description="Run the platformer-advanced recipe",
                api_calls=[
                    {"method": "run_recipe", "args": {"recipe_id": "platformer-advanced"}},
                ],
                expected_outcome="Mutates the target project through official authoring commands, then validates an advanced native platformer vertical slice",
            ),
            notes="Runs only validated argv-list recipe steps through the official motor CLI in-process; no shell, no temporary scripts and no external runtime. It does mutate the target --project because bundled authoring commands save scene, editor_state and startup_scene changes.",
            tags=["recipe", "ai", "workflow", "tooling", "authoring"],
        ))

    def _register_runtime_capabilities(self) -> None:
        self._add(Capability(
            id="runtime:play",
            summary="Start play mode for a stateless headless runtime check",
            mode="edit",
            api_methods=["RuntimeAPI.play"],
            cli_command="motor runtime play [--project <path>] [--headless]",
            example=CapabilityExample(
                description="Start play mode headlessly",
                api_calls=[
                    {"method": "play", "args": {}},
                ],
                expected_outcome="Engine enters PLAY mode in the current CLI process and then cleans up before exit",
            ),
            notes="The official CLI command is stateless: it initializes EngineAPI, loads a scene for headless verification, calls play(), reports status, then stops before process exit without saving authoring state.",
            tags=["runtime", "play"],
        ))

        self._add(Capability(
            id="runtime:stop",
            summary="Stop runtime in the current stateless headless process",
            mode="play",
            api_methods=["RuntimeAPI.stop"],
            cli_command="motor runtime stop [--project <path>]",
            example=CapabilityExample(
                description="Stop runtime in the current process",
                api_calls=[
                    {"method": "stop", "args": {}},
                ],
                expected_outcome="Current process runtime returns to EDIT mode; previous CLI invocations are not affected",
            ),
            notes="The official CLI command is stateless and idempotent. It cannot stop a PLAY session from a previous process and reports that as a warning.",
            tags=["runtime", "play"],
        ))

        self._add(Capability(
            id="runtime:step",
            summary="Run PLAY -> STEP -> STOP headlessly for N frames, optionally with simulated InputMap actions",
            mode="play",
            api_methods=["RuntimeAPI.step", "RuntimeAPI.inject_input_state", "RuntimeAPI.get_recent_events"],
            cli_command="motor runtime step [--project <path>] [--frames <n>] [--input <actions>]",
            example=CapabilityExample(
                description="Advance simulation by 300 frames while holding right and jump",
                api_calls=[
                    {"method": "play", "args": {}},
                    {"method": "inject_input_state", "args": {"entity_name": "Player", "state": {"horizontal": 1.0, "vertical": 0.0, "action_1": 1.0, "action_2": 0.0}, "frames": 300}},
                    {"method": "step", "args": {"frames": 300}},
                    {"method": "get_recent_events", "args": {"count": 50}},
                    {"method": "stop", "args": {}},
                ],
                expected_outcome="World updates with synthetic InputMap state, exposes runtime events, and returns to EDIT without saving runtime mutations",
            ),
            notes="The official CLI command runs the whole validation sequence in one stateless headless process: load scene, play, optional input injection, step, read events, stop. Supported --input tokens are left, right, up, down, jump, action_1 and action_2. Runtime mutations are not persisted as authoring state.",
            tags=["runtime", "play", "input", "events"],
        ))

        self._add(Capability(
            id="runtime:undo",
            summary="Undo the last edit operation",
            mode="edit",
            api_methods=["RuntimeAPI.undo"],
            cli_command="motor runtime undo",
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
            id="runtime:audio:play",
            summary="Play audio from an AudioSource entity",
            mode="play",
            api_methods=["RuntimeAPI.play_audio"],
            cli_command="motor runtime audio play <source_id>",
            example=CapabilityExample(
                description="Play background music",
                api_calls=[
                    {"method": "play_audio", "args": {"entity_name": "BGM_Source"}},
                ],
                expected_outcome="Audio starts playing from the specified source",
            ),
            notes="Requires an entity with AudioSource component. Runtime must be in PLAY mode.",
            tags=["runtime", "audio"],
        ))
        self._add(Capability(
            id="runtime:audio:stop",
            summary="Stop audio from an AudioSource entity",
            mode="play",
            api_methods=["RuntimeAPI.stop_audio"],
            cli_command="motor runtime audio stop <source_id>",
            example=CapabilityExample(
                description="Stop background music",
                api_calls=[
                    {"method": "stop_audio", "args": {"entity_name": "BGM_Source"}},
                ],
                expected_outcome="Audio stops playing",
            ),
            notes="Requires an entity with AudioSource component.",
            tags=["runtime", "audio"],
        ))
        self._add(Capability(
            id="runtime:audio:pause",
            summary="Pause audio from an AudioSource entity",
            mode="play",
            api_methods=["RuntimeAPI.pause_audio"],
            cli_command="motor runtime audio pause <source_id>",
            example=CapabilityExample(
                description="Pause background music",
                api_calls=[
                    {"method": "pause_audio", "args": {"entity_name": "BGM_Source"}},
                ],
                expected_outcome="Audio is paused",
            ),
            notes="Can be resumed later with resume_audio.",
            tags=["runtime", "audio"],
        ))
        self._add(Capability(
            id="runtime:audio:resume",
            summary="Resume paused audio from an AudioSource entity",
            mode="play",
            api_methods=["RuntimeAPI.resume_audio"],
            cli_command="motor runtime audio resume <source_id>",
            example=CapabilityExample(
                description="Resume background music",
                api_calls=[
                    {"method": "resume_audio", "args": {"entity_name": "BGM_Source"}},
                ],
                expected_outcome="Audio resumes from where it was paused",
            ),
            notes="Only works on paused audio sources.",
            tags=["runtime", "audio"],
        ))

        self._add(Capability(
            id="runtime:redo",
            summary="Redo a previously undone operation",
            mode="edit",
            api_methods=["RuntimeAPI.redo"],
            cli_command="motor runtime redo",
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

        self._add(Capability(
            id="runtime:status",
            summary="Read-only runtime status and active scene info",
            mode="both",
            api_methods=["RuntimeAPI.get_status", "SceneWorkspaceAPI.get_active_scene_info"],
            cli_command="motor runtime status [--project <path>]",
            example=CapabilityExample(
                description="Get runtime status and scene info",
                api_calls=[
                    {"method": "get_status", "args": {}},
                    {"method": "get_active_scene_info", "args": {}},
                ],
                expected_outcome="Returns engine state, frame, fps, entity count and active scene metadata",
            ),
            notes="Read-only. Loads a fallback scene for inspection if none is active, without persisting state.",
            tags=["runtime", "introspection"],
        ))

        self._add(Capability(
            id="runtime:entities",
            summary="List entities in the active scene (read-only)",
            mode="both",
            api_methods=["RuntimeAPI.list_entities"],
            cli_command="motor runtime entities [--project <path>] [--tag <tag>] [--layer <layer>] [--active-only]",
            example=CapabilityExample(
                description="List all active entities",
                api_calls=[
                    {"method": "list_entities", "args": {"active": True}},
                ],
                expected_outcome="Returns list of EntityData for matching entities",
            ),
            notes="Read-only. Supports optional filtering by tag, layer and active state.",
            tags=["runtime", "introspection", "entity"],
        ))

        self._add(Capability(
            id="runtime:inspect",
            summary="Inspect a specific entity (read-only)",
            mode="both",
            api_methods=["RuntimeAPI.get_entity"],
            cli_command="motor runtime inspect <entity> [--project <path>]",
            example=CapabilityExample(
                description="Get full data for the Player entity",
                api_calls=[
                    {"method": "get_entity", "args": {"name": "Player"}},
                ],
                expected_outcome="Returns EntityData with all components and values",
            ),
            notes="Read-only. Throws if entity does not exist. Loads a fallback scene for inspection if none is active.",
            tags=["runtime", "introspection", "entity"],
        ))

        self._add(Capability(
            id="runtime:events",
            summary="Return recent runtime events, optionally after a headless step",
            mode="both",
            api_methods=["RuntimeAPI.get_recent_events"],
            cli_command="motor runtime events [--project <path>] [--count <n>] [--step-frames <n>]",
            example=CapabilityExample(
                description="Get last 50 runtime events",
                api_calls=[
                    {"method": "get_recent_events", "args": {"count": 50}},
                ],
                expected_outcome="Returns list of recent events with name and data",
            ),
            notes="Read-only by default. With --step-frames, runs PLAY -> STEP in the same stateless process before reading events and does not persist runtime mutations.",
            tags=["runtime", "introspection", "events"],
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
            id="physics:query:shape-cast",
            summary="Cast a shape through physics world and find intersections",
            mode="both",
            api_methods=["RuntimeAPI.query_physics_shape_cast"],
            cli_command="motor physics query shape-cast <shape_type> <shape_width> <shape_height> <origin_x> <origin_y> <direction_x> <direction_y> <max_distance>",
            example=CapabilityExample(
                description="Cast a box shape from origin (100,100) to the right",
                api_calls=[
                    {"method": "query_physics_shape_cast", "args": {
                        "shape_type": "box", "shape_width": 32, "shape_height": 32,
                        "origin_x": 100, "origin_y": 100,
                        "direction_x": 1, "direction_y": 0,
                        "max_distance": 500,
                    }},
                ],
                expected_outcome="Returns list of hits sorted by distance",
            ),
            notes="Direction is normalized. Supports box, circle, capsule shapes.",
            tags=["physics", "query", "collision"],
        ))
        self._add(Capability(
            id="physics:query:motion",
            summary="Test entity motion against physics world without applying it",
            mode="both",
            api_methods=["RuntimeAPI.query_physics_motion"],
            cli_command="motor physics query motion <entity_name> <motion_x> <motion_y>",
            example=CapabilityExample(
                description="Test if player would collide moving 100px right",
                api_calls=[
                    {"method": "query_physics_motion", "args": {
                        "entity_name": "player", "motion_x": 100, "motion_y": 0,
                        "margin": 0.08,
                    }},
                ],
                expected_outcome="Returns collision info and safe displacement",
            ),
            notes="Non-mutating. Uses active physics backend for motion testing.",
            tags=["physics", "query", "collision", "motion"],
        ))

        self._add(Capability(
            id="physics:backend:list",
            summary="List available physics backends and their status",
            mode="both",
            api_methods=["RuntimeAPI.list_physics_backends", "RuntimeAPI.get_physics_backend_selection"],
            cli_command="motor physics backend list",
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
            cli_command="motor runtime inspect <entity>",
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
            id="agent:providers:login",
            summary="Store provider credentials or delegate managed Codex/OpenAI login",
            mode="both",
            api_methods=["AgentAPI.login_agent_provider"],
            cli_command="motor agent providers login <provider> [--api-key-stdin] [--codex-chatgpt] [--device-auth] [--base-url <url>] [--model <model>]",
            example=CapabilityExample(
                description="Configure an agent provider credential without exposing the key in shell history",
                api_calls=[
                    {
                        "method": "login_agent_provider",
                        "args": {"provider_id": "openai", "credential_source": "user_local"},
                    },
                ],
                expected_outcome="Stores local provider auth metadata or delegates to managed Codex/OpenAI auth",
            ),
            notes="Experimental/tooling. CLI requires --api-key-stdin for raw keys, or --codex-chatgpt/--device-auth for managed login.",
            tags=["agent", "experimental", "providers", "auth"],
        ))

        self._add(Capability(
            id="agent:providers:logout",
            summary="Remove user-local provider credentials",
            mode="both",
            api_methods=["AgentAPI.logout_agent_provider"],
            cli_command="motor agent providers logout <provider>",
            example=CapabilityExample(
                description="Remove a stored provider credential",
                api_calls=[
                    {"method": "logout_agent_provider", "args": {"provider_id": "openai"}},
                ],
                expected_outcome="Provider credential metadata is removed without revealing secrets",
            ),
            notes="Experimental/tooling. Does not remove environment variables or external managed auth state.",
            tags=["agent", "experimental", "providers", "auth"],
        ))

        self._add(Capability(
            id="agent:providers:status",
            summary="Show provider authentication status without revealing secrets",
            mode="both",
            api_methods=["AgentAPI.get_agent_provider_status"],
            cli_command="motor agent providers status [provider]",
            example=CapabilityExample(
                description="Inspect whether OpenAI provider auth is available",
                api_calls=[
                    {"method": "get_agent_provider_status", "args": {"provider_id": "openai"}},
                ],
                expected_outcome="Returns credential source, auth method and runtime readiness without secret values",
            ),
            notes="Experimental/tooling. Omitting provider returns default/provider-wide status.",
            tags=["agent", "experimental", "providers", "auth", "diagnostics"],
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

    def _register_signal_capabilities(self) -> None:
        self._add(Capability(
            id="signal:connect",
            summary="Connect a signal between entities in the active scene",
            mode="edit",
            api_methods=["RuntimeAPI.connect_signal", "AuthoringAPI.add_signal_connection"],
            cli_command="motor signal connect <signal_name> <source_entity> <target_entity>",
            example=CapabilityExample(
                description="Connect death signal from Player to GameOver entity",
                api_calls=[
                    {"method": "add_signal_connection", "args": {"connection_data": {"id": "death_conn", "signal": "on_death", "source": {"kind": "entity", "name": "Player"}, "target": {"kind": "entity", "name": "GameOver"}}}},
                ],
                expected_outcome="Signal connection stored in scene feature metadata",
            ),
            notes="Creates declarative signal connection stored in scene feature metadata.",
            tags=["signal", "authoring"],
        ))
        self._add(Capability(
            id="signal:emit",
            summary="Emit a signal from an entity at runtime",
            mode="play",
            api_methods=["RuntimeAPI.emit_signal"],
            cli_command="motor signal emit <signal_name> [--entity <entity_id>]",
            example=CapabilityExample(
                description="Emit on_death signal",
                api_calls=[
                    {"method": "emit_signal", "args": {"source_id": "Player", "signal_name": "on_death"}},
                ],
                expected_outcome="Returns count of connections executed",
            ),
            notes="Requires runtime to be active. Returns count of executed connections.",
            tags=["signal", "runtime"],
        ))
        self._add(Capability(
            id="signal:disconnect",
            summary="Disconnect a signal between entities",
            mode="edit",
            api_methods=["AuthoringAPI.remove_signal_connection"],
            cli_command="motor signal disconnect <signal_name> <source_entity> <target_entity>",
            example=CapabilityExample(
                description="Disconnect on_death signal",
                api_calls=[
                    {"method": "remove_signal_connection", "args": {"connection_id": "death_conn"}},
                ],
                expected_outcome="Signal connection removed from scene metadata",
            ),
            notes="Removes declarative signal connection from scene metadata.",
            tags=["signal", "authoring"],
        ))
        self._add(Capability(
            id="signal:list",
            summary="List signal connections in the active scene",
            mode="both",
            api_methods=["AuthoringAPI.list_signal_connections_declarative"],
            cli_command="motor signal list",
            example=CapabilityExample(
                description="List all signal connections",
                api_calls=[
                    {"method": "list_signal_connections_declarative", "args": {}},
                ],
                expected_outcome="Returns list of connections with source, target and signal names",
            ),
            notes="Lists declarative signal connections with source, target, and signal metadata.",
            tags=["signal", "query"],
        ))

    def _register_ui_capabilities(self) -> None:
        self._add(Capability(
            id="ui:create_canvas",
            summary="Create a UI canvas entity",
            mode="edit",
            api_methods=["UIAPI.create_canvas"],
            cli_command="motor ui create-canvas --name <name> --width <int> --height <int>",
            example=CapabilityExample(
                description="Create a 800x600 UI canvas",
                api_calls=[
                    {"method": "create_canvas", "args": {"name": "Canvas", "reference_width": 800, "reference_height": 600}},
                ],
                expected_outcome="Canvas entity created with RectTransform",
            ),
            notes="Creates Canvas entity with RectTransform. Acts as root for UI hierarchy.",
            tags=["ui", "authoring"],
        ))
        self._add(Capability(
            id="ui:create_text",
            summary="Create a UI text element",
            mode="edit",
            api_methods=["UIAPI.create_ui_text"],
            cli_command="motor ui create-text --text <text> --parent <canvas> --font-size <int> --color <hex>",
            example=CapabilityExample(
                description="Create 'Hello World' text on canvas",
                api_calls=[
                    {"method": "create_ui_text", "args": {"name": "TitleText", "text": "Hello World", "parent": "Canvas", "font_size": 24}},
                ],
                expected_outcome="UIText child entity created under canvas",
            ),
            notes="Creates child entity under parent canvas with UIText and RectTransform components.",
            tags=["ui", "authoring"],
        ))
        self._add(Capability(
            id="ui:create_button",
            summary="Create a UI button element",
            mode="edit",
            api_methods=["UIAPI.create_ui_button"],
            cli_command="motor ui create-button --text <text> --parent <canvas>",
            example=CapabilityExample(
                description="Create 'Play' button on canvas",
                api_calls=[
                    {"method": "create_ui_button", "args": {"name": "PlayBtn", "label": "Play", "parent": "Canvas"}},
                ],
                expected_outcome="UIButton child entity created under canvas",
            ),
            notes="Creates child entity with UIButton component. Auto-generates name.",
            tags=["ui", "authoring"],
        ))
        self._add(Capability(
            id="ui:create_image",
            summary="Create a UI image element",
            mode="edit",
            api_methods=["UIAPI.create_ui_image"],
            cli_command="motor ui create-image --path <asset_path> --parent <canvas>",
            example=CapabilityExample(
                description="Create image from logo asset on canvas",
                api_calls=[
                    {"method": "create_ui_image", "args": {"name": "LogoImg", "parent": "Canvas", "sprite": "assets/logo.png"}},
                ],
                expected_outcome="UIImage child entity created under canvas",
            ),
            notes="Creates child entity with UIImage component using the specified asset.",
            tags=["ui", "authoring"],
        ))

    def _register_mobile_capabilities(self) -> None:
        self._add(Capability(
            id="mobile:controls:add",
            summary="Add mobile virtual controls to the active scene",
            mode="edit",
            api_methods=["UIAPI.create_mobile_controls"],
            cli_command="motor mobile controls add [--scene <path>] --target <entity> --profile <profile> [--project <path>] [--json]",
            example=CapabilityExample(
                description="Add platformer touch controls for Player",
                api_calls=[
                    {"method": "create_mobile_controls", "args": {"target_entity": "Player", "profile": "platformer"}},
                ],
                expected_outcome="MobileControls2D overlay created and wired to Player InputMap",
            ),
            notes="Creates a serializable internal mobile controls overlay. Use --scene to edit a specific scene and --replace to regenerate an existing overlay.",
            tags=["mobile", "input", "authoring"],
        ))

    def _register_editor_capabilities(self) -> None:
        self._add(Capability(
            id="editor:theme:list",
            summary="List available editor UI themes",
            mode="edit",
            api_methods=["EngineAPI.list_editor_themes", "EngineAPI.get_active_editor_theme"],
            cli_command="motor editor theme list [--project <path>] [--json]",
            example=CapabilityExample(
                description="List built-in and imported editor themes",
                api_calls=[
                    {"method": "list_editor_themes", "args": {}},
                ],
                expected_outcome="Returns available themes and the active theme name",
            ),
            notes="Read-only editor preference query. Does not mutate scene authoring state.",
            tags=["editor", "theme", "query"],
        ))
        self._add(Capability(
            id="editor:theme:active",
            summary="Show the active editor UI theme",
            mode="edit",
            api_methods=["EngineAPI.get_active_editor_theme"],
            cli_command="motor editor theme active [--project <path>] [--json]",
            example=CapabilityExample(
                description="Inspect the active editor theme",
                api_calls=[
                    {"method": "get_active_editor_theme", "args": {}},
                ],
                expected_outcome="Returns the active theme payload",
            ),
            notes="Read-only editor preference query.",
            tags=["editor", "theme", "query"],
        ))
        self._add(Capability(
            id="editor:theme:set",
            summary="Set the active editor UI theme",
            mode="edit",
            api_methods=["EngineAPI.set_active_editor_theme"],
            cli_command="motor editor theme set <name> [--project <path>] [--json]",
            example=CapabilityExample(
                description="Switch the editor to the light Unity-style theme",
                api_calls=[
                    {"method": "set_active_editor_theme", "args": {"name": "unity_light"}},
                ],
                expected_outcome="Editor theme preference is persisted for the project",
            ),
            notes="Persists only editor preferences in .motor/editor_state.json.",
            tags=["editor", "theme", "preferences"],
        ))
        self._add(Capability(
            id="editor:theme:export",
            summary="Export an editor UI theme to JSON",
            mode="edit",
            api_methods=["EngineAPI.export_editor_theme"],
            cli_command="motor editor theme export <path> [--name <theme>] [--project <path>] [--json]",
            example=CapabilityExample(
                description="Export the Unity dark editor theme",
                api_calls=[
                    {"method": "export_editor_theme", "args": {"path": "theme.json", "name": "unity_dark"}},
                ],
                expected_outcome="Theme JSON is written under the project path",
            ),
            notes="Export path is resolved through EngineAPI project path guards.",
            tags=["editor", "theme", "import-export"],
        ))
        self._add(Capability(
            id="editor:theme:import",
            summary="Import an editor UI theme from JSON",
            mode="edit",
            api_methods=["EngineAPI.import_editor_theme"],
            cli_command="motor editor theme import <path> [--no-activate] [--project <path>] [--json]",
            example=CapabilityExample(
                description="Import and activate an editor theme JSON file",
                api_calls=[
                    {"method": "import_editor_theme", "args": {"path": "theme.json"}},
                ],
                expected_outcome="Theme is imported and active unless activation is disabled",
            ),
            notes="Import path is resolved through EngineAPI project path guards.",
            tags=["editor", "theme", "import-export"],
        ))
        self._add(Capability(
            id="editor:feature_flags:list",
            summary="List editor feature flags",
            mode="edit",
            api_methods=["EngineAPI.get_editor_feature_flags"],
            cli_command="motor editor feature-flags list [--project <path>] [--json]",
            example=CapabilityExample(
                description="Inspect editor control migration flags",
                api_calls=[
                    {"method": "get_editor_feature_flags", "args": {}},
                ],
                expected_outcome="Returns schema_version, current flag values, and env overrides",
            ),
            notes="Read-only editor preference query. Env vars can override persisted values at runtime.",
            tags=["editor", "feature-flags", "query"],
        ))
        self._add(Capability(
            id="editor:feature_flags:set",
            summary="Set an editor feature flag",
            mode="edit",
            api_methods=["EngineAPI.set_editor_feature_flag"],
            cli_command="motor editor feature-flags set <name> <true|false> [--project <path>] [--json]",
            example=CapabilityExample(
                description="Enable retained console panel pilot for the project",
                api_calls=[
                    {"method": "set_editor_feature_flag", "args": {"name": "console_panel", "value": True}},
                ],
                expected_outcome="Feature flag preference is persisted for the project",
            ),
            notes="Persists only editor preferences in .motor/editor_state.json. Defaults remain false.",
            tags=["editor", "feature-flags", "preferences"],
        ))

    def _register_debug_capabilities(self) -> None:
        self._add(Capability(
            id="debug:profiler:reset",
            summary="Reset the profiler",
            mode="both",
            api_methods=["DebugAPI.reset_profiler"],
            cli_command="motor debug profiler reset",
            example=CapabilityExample(
                description="Reset the profiler",
                api_calls=[
                    {"method": "reset_profiler", "args": {}},
                ],
                expected_outcome="Profiler data cleared",
            ),
            notes="Resets accumulated profiler data for a fresh measurement.",
            tags=["debug", "profiler"],
        ))
        self._add(Capability(
            id="debug:profiler:report",
            summary="Get the current profiler report",
            mode="both",
            api_methods=["DebugAPI.get_profiler_report"],
            cli_command="motor debug profiler report",
            example=CapabilityExample(
                description="Get the current profiler report",
                api_calls=[
                    {"method": "get_profiler_report", "args": {}},
                ],
                expected_outcome="Returns timing data for subsystems and frames",
            ),
            notes="Returns timing data for subsystems and frames.",
            tags=["debug", "profiler", "query"],
        ))
        self._add(Capability(
            id="debug:overlay",
            summary="Enable or disable the debug overlay",
            mode="play",
            api_methods=["DebugAPI.configure_debug_overlay"],
            cli_command="motor debug overlay <on|off>",
            example=CapabilityExample(
                description="Enable debug overlay with colliders and labels",
                api_calls=[
                    {"method": "configure_debug_overlay", "args": {"draw_colliders": True, "draw_labels": True}},
                ],
                expected_outcome="Debug overlay configuration updated",
            ),
            notes="Toggles draw_colliders and draw_labels debug rendering.",
            tags=["debug", "rendering"],
        ))

    def _register_service_capabilities(self) -> None:
        self._add(Capability(
            id="service:register",
            summary="Register a runtime service",
            mode="play",
            api_methods=["RuntimeAPI.register_service_runtime"],
            cli_command="motor service register <name> <component_name>",
            example=CapabilityExample(
                description="Register a ScoreManager service",
                api_calls=[
                    {"method": "register_service_runtime", "args": {"name": "ScoreManager", "service": "ScoreManager"}},
                ],
                expected_outcome="Service registered for the current PLAY session",
            ),
            notes="Registers a service object for the current PLAY session.",
            tags=["service", "runtime"],
        ))
        self._add(Capability(
            id="service:get",
            summary="Get a registered runtime service",
            mode="play",
            api_methods=["RuntimeAPI.get_service"],
            cli_command="motor service get <name>",
            example=CapabilityExample(
                description="Get the ScoreManager service",
                api_calls=[
                    {"method": "get_service", "args": {"name": "ScoreManager"}},
                ],
                expected_outcome="Returns the service object if registered",
            ),
            notes="Returns the service object if registered.",
            tags=["service", "runtime", "query"],
        ))
        self._add(Capability(
            id="service:has",
            summary="Check if a runtime service is registered",
            mode="play",
            api_methods=["RuntimeAPI.has_service"],
            cli_command="motor service has <name>",
            example=CapabilityExample(
                description="Check if ScoreManager service exists",
                api_calls=[
                    {"method": "has_service", "args": {"name": "ScoreManager"}},
                ],
                expected_outcome="Returns boolean indicating service availability",
            ),
            notes="Returns boolean indicating service availability.",
            tags=["service", "runtime", "query"],
        ))

    def _register_entity_group_capabilities(self) -> None:
        self._add(Capability(
            id="entity:group:add",
            summary="Add an entity to a group",
            mode="edit",
            api_methods=["RuntimeAPI.add_entity_to_group"],
            cli_command="motor entity group add <entity_id> <group_name>",
            example=CapabilityExample(
                description="Add Player to Enemies group",
                api_calls=[
                    {"method": "add_entity_to_group", "args": {"entity_name": "Player", "group_name": "Players"}},
                ],
                expected_outcome="Entity added to group, scene saved",
            ),
            notes="Persists group membership in scene data. Saves scene after mutation.",
            tags=["entity", "group", "authoring"],
        ))
        self._add(Capability(
            id="entity:group:remove",
            summary="Remove an entity from a group",
            mode="edit",
            api_methods=["RuntimeAPI.remove_entity_from_group"],
            cli_command="motor entity group remove <entity_id> <group_name>",
            example=CapabilityExample(
                description="Remove Player from Players group",
                api_calls=[
                    {"method": "remove_entity_from_group", "args": {"entity_name": "Player", "group_name": "Players"}},
                ],
                expected_outcome="Entity removed from group, scene saved",
            ),
            notes="Removes group membership from scene data. Saves scene after mutation.",
            tags=["entity", "group", "authoring"],
        ))
        self._add(Capability(
            id="entity:group:list",
            summary="List entities in a group or all groups",
            mode="both",
            api_methods=["RuntimeAPI.get_entities_in_group"],
            cli_command="motor entity group list [<group_name>]",
            example=CapabilityExample(
                description="List all entities in the Players group",
                api_calls=[
                    {"method": "get_entities_in_group", "args": {"group_name": "Players"}},
                ],
                expected_outcome="Returns list of entity names in the group",
            ),
            notes="Without group_name, lists all groups and their members.",
            tags=["entity", "group", "query"],
        ))

    # Capabilities that are planned but not yet implemented.
    # These do NOT have corresponding implementations in the official motor CLI parser.
    # They are API-level capabilities that may be used programmatically but are not
    # exposed through the CLI yet.
    _PLANNED_CAPABILITIES: set[str] = {
        # Asset operations beyond list/slice (no CLI commands exist)
        "asset:find",
        "asset:metadata:get",
        "asset:refresh",

        # Project operations beyond info/bootstrap-ai (no CLI commands exist)
        "project:open",
        "project:editor_state",

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
            "# OpenGame - AI Quick Start",
            "",
            f"**Project**: {project_name}",
            f"**Engine Version**: {self._registry.engine_version}",
            "",
            "## Overview",
            "This project uses OpenGame, a 2D game engine designed for AI-assisted development.",
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
            "ai:start", "ai:compliance",
            "scene:load", "scene:save", "scene:create",
            "entity:create",
            "component:add",
            "asset:list", "asset:slice:grid", "asset:slice:list",
            "animator:set_sheet", "animator:state:create", "animator:info",
            "runtime:play", "runtime:step", "runtime:stop",
            "runtime:status", "runtime:entities", "runtime:inspect", "runtime:events",
            "game:platformer:create", "game:platformer:add-coin",
            "game:platformer:add-hazard", "game:platformer:add-goal",
            "game:platformer:add-respawn", "game:platformer:add-moving-platform",
            "game:platformer:add-enemy-patrol", "game:platformer:add-checkpoint",
            "game:platformer:add-killzone", "game:platformer:set-camera-follow",
            "game:platformer:set-bounds", "game:platformer:validate",
            "recipe:list", "recipe:show", "recipe:run",
            "export:build", "export:build-all", "export:doctor",
            "export:pack", "export:presets:list", "export:presets:validate",
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
            "AI": ["ai:"],
            "Scene Management": ["scene:"],
            "Entity Operations": ["entity:"],
            "Component Operations": ["component:"],
            "Asset Management": ["asset:"],
            "Animation": ["animator:"],
            "Prefabs": ["prefab:"],
            "Project": ["project:"],
            "Recipes": ["recipe:"],
            "Agent": ["agent:"],
            "Game": ["game:"],
            "Runtime": ["runtime:"],
            "Physics": ["physics:"],
            "Introspection": ["introspect:"],
            "Debug": ["debug:"],
            "Services": ["service:"],
            "Signals": ["signal:"],
            "UI": ["ui:"],
            "Mobile": ["mobile:"],
            "Editor": ["editor:"],
            "Export": ["export:"],
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
            "Start here before making changes:",
            "```bash",
            "motor ai start --project . --json",
            "```",
            "",
            "Rules for AI agents:",
            "- Use OpenGame through `motor`, `EngineAPI` and serialized scenes/components.",
            "- Do not create an external runtime for this project.",
            "- Do not deliver `run_game.py` or an alternate main loop as the main game.",
            "- Treat `MovingPlatform2D` as runtime-supported by `Gameplay2DSemanticSystem`: it moves the platform entity along its path, emits movement events during PLAY, can carry Player when Player Collider rests on the platform Collider before frame movement, and does not persist runtime progress. Rider support is minimal and Player-focused; `moving_platform_rider_attached`, `moving_platform_rider_moved` and `moving_platform_rider_detached` are planned, not current public events.",
            "- Treat `EnemyPatrol2D` as runtime-supported by `Gameplay2DSemanticSystem`: it moves the entity cyclically between patrol points, emits `enemy_patrol_started` and `enemy_patrol_reached_point`, and on Player contact emits `enemy_touched` with damage and respawn (or `enemy_respawn_missing`). If coexisting with `Hazard2D` on the same entity, it absorbs the interaction to avoid duplicate events.",
            "- Treat `Checkpoint2D`, `KillZone2D` and `LevelBounds2D` as runtime-supported semantic gameplay components: `Checkpoint2D` can activate session respawn compatibility via `RespawnPoint2D`, `KillZone2D` can respawn the player from the active checkpoint or first active `RespawnPoint2D`, and `LevelBounds2D` can emit `level_bounds_exited`, clamp horizontal exits and emit `level_bounds_respawn_missing` when bottom exit has no respawn.",
            "- Treat `motor runtime play/step/stop/events` as stateless per invocation; runtime mutations are inspection-only and are not persisted as authoring state.",
            "- Treat `motor recipe run` as allowlisted and shell-safe, but mutating for the target `--project`; bundled platformer recipes include `platformer-basic` and `platformer-advanced`.",
            "- Treat `motor ai self-test` as temporary by default under `.motor/tmp`; use `--in-place` only when real project mutation is intended.",
            "",
            "### Quick Workflow",
            "",
            "1. **Load the AI contract**:",
            "   ```bash",
            "   motor ai start --project . --json",
            "   ```",
            "",
            "2. **Check project health**:",
            "   ```bash",
            "   motor doctor --project . --json",
            "   ```",
            "",
            "3. **Check AI-native compliance**:",
            "   ```bash",
            "   motor ai compliance --project . --strict --json",
            "   ```",
            "",
            "4. **Create a scene**:",
            "   ```bash",
            "   motor scene create \"Level 1\" --project .",
            "   ```",
            "",
            "5. **Create an entity**:",
            "   ```bash",
            "   motor entity create Player --project . --json",
            "   ```",
            "",
            "6. **Add a component**:",
            "   ```bash",
            '   motor component add Player Transform --data \'{"x": 100, "y": 200}\' --project .',
            "   ```",
            "",
            "7. **Slice a sprite sheet**:",
            "   ```bash",
            "   motor asset slice grid assets/player.png --cell-width 32 --cell-height 32 --project .",
            "   ```",
            "",
            "8. **Configure animator**:",
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
