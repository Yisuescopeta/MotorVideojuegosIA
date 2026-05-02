from __future__ import annotations

from pathlib import Path
from typing import Any, Union, List, Dict, Dict, Optional

from engine.api._context import EngineAPIComponent
from engine.api.types import ActionResult


class AssetsProjectAPI(EngineAPIComponent):
    """Project and asset management endpoints exposed by EngineAPI."""

    def list_recent_projects(self) -> list[Dict[str, Union[str, int, float, bool, list, dict, None]]]:
        """List recently opened project directories.

        Returns:
            List of project summary dictionaries, or empty list if no project
            service is available.
        """
        if self.project_service is None:
            return []
        return self.project_service.list_recent_projects()

    def get_project_manifest(self) -> Dict[str, Any]:
        """Get the current project's manifest summary.

        Returns:
            Dictionary with project metadata (name, root path, scene list, etc.),
            or empty dict if no project is loaded.
        """
        if self.project_service is None:
            return {}
        return self.project_service.get_project_summary()

    def open_project(self, path: str) -> ActionResult:
        """Open a project directory, loading its manifest and settings.

        Args:
            path: Path to the project root directory.

        Returns:
            ActionResult with the project root path, or failure if the project
            could not be opened.
        """
        if self.project_service is None or self.game is None:
            return self.fail("Project service not ready")
        success = self.game.open_project(path)
        if not success:
            return self.fail("Open project failed")
        return self.ok("Project opened", {"path": self.project_service.project_root_display.as_posix()})

    def get_editor_state(self) -> Dict[str, Any]:
        """Load the persisted editor state for the current project.

        Returns:
            Dictionary with editor state data (active_scene, last_scene,
            open tabs, window layout, etc.), or empty dict if unavailable.
        """
        if self.project_service is None:
            return {}
        return self.project_service.load_editor_state()

    def list_project_scenes(self) -> list[Dict[str, Union[str, int, float, bool, list, dict, None]]]:
        """List all scene files available in the project.

        Returns:
            List of scene info dictionaries (name, path, key, etc.), or empty
            list if no project is loaded.
        """
        if self.project_service is None or not self.project_service.has_project:
            return []
        return self.project_service.list_project_scenes()

    def to_project_relative_path(self, path: str) -> str:
        """Convert an absolute path to a project-relative path.

        Args:
            path: Absolute or relative file path.

        Returns:
            Project-relative path with forward slashes, or the original path
            normalized if no project is loaded.
        """
        if self.project_service is None:
            return str(path or "").replace("\\", "/")
        return self.project_service.to_relative_path(path).replace("\\", "/")

    def resolve_project_path(self, path: str) -> Dict[str, Any]:
        """Resolve a path relative to the project root to an absolute path.

        Args:
            path: Relative or absolute path.

        Returns:
            Dictionary with keys: path (absolute posix), exists, is_file, and
            relative_path.
        """
        if self.project_service is None:
            resolved = Path(path).expanduser().resolve()
        else:
            resolved = self.project_service.resolve_path(path)
        return {
            "path": resolved.as_posix(),
            "exists": resolved.exists(),
            "is_file": resolved.is_file(),
            "relative_path": self.to_project_relative_path(resolved.as_posix()),
        }

    def get_startup_scene(self) -> str:
        """Get the startup scene configured in project settings.

        Returns:
            Project-relative path to the startup scene, or empty string if
            not configured.
        """
        if self.project_service is None:
            return ""
        return str(self.project_service.load_project_settings().get("startup_scene", "") or "")

    def set_startup_scene(self, path: str) -> ActionResult:
        """Set the startup scene in project settings.

        Args:
            path: Project-relative path to the scene.

        Returns:
            ActionResult with the updated startup_scene value.
        """
        if self.project_service is None:
            return self.fail("Project service not ready")
        settings = self.project_service.load_project_settings()
        settings["startup_scene"] = self.project_service.to_relative_path(path) if path else ""
        self.project_service.save_project_settings(settings)
        return self.ok("Startup scene updated", {"startup_scene": settings["startup_scene"]})

    def migrate_project_bootstrap(self, project_root: Optional[str] = None) -> Dict[str, Any]:
        """Generate AI bootstrap files (motor_ai.json and START_HERE_AI.md).

        Args:
            project_root: Optional project root path override.

        Returns:
            Dictionary with motor_ai.json data.
        """
        if self.project_service is None:
            return {}
        from pathlib import Path
        root = Path(project_root) if project_root else None
        return self.project_service.migrate_project_bootstrap(root)

    def run_ai_compliance(self, strict: bool = False) -> Dict[str, Any]:
        """Run AI compliance checks on the current project.

        Args:
            strict: If True, uses stricter validation rules.

        Returns:
            Dictionary with compliance results including success, strict_pass,
            external_runtime_blocking, errors, and warnings.
        """
        if self.project_service is None:
            return {
                "success": False,
                "strict_pass": False,
                "external_runtime_blocking": True,
                "errors": [{"code": "project_service_unavailable", "message": "Project service not ready"}],
                "warnings": [],
            }
        from engine.ai.compliance import run_ai_compliance

        return run_ai_compliance(self.project_service.project_root, strict=bool(strict))

    def save_editor_state(self, data: Dict[str, Union[str, int, float, bool, list, dict, None]]) -> ActionResult:
        """Persist editor state data for the current project.

        Args:
            data: Editor state dictionary to save.

        Returns:
            ActionResult with the saved editor state.
        """
        if self.project_service is None:
            return self.fail("Project service not ready")
        self.project_service.save_editor_state(data)
        return self.ok("Editor state saved", self.project_service.load_editor_state())

    def list_project_assets(self, search: str = "") -> list[Dict[str, Union[str, int, float, bool, list, dict, None]]]:
        """List all assets registered in the project's asset catalog.

        Args:
            search: Optional search string to filter assets by name or path.

        Returns:
            List of asset info dictionaries.
        """
        if self.asset_service is None:
            return []
        return self.asset_service.list_assets(search=search)

    def list_project_prefabs(self) -> list[str]:
        """List all prefab file paths in the project.

        Returns:
            List of project-relative prefab paths.
        """
        if self.project_service is None or not self.project_service.has_project:
            return []
        return self.project_service.list_project_prefabs()

    def list_project_scripts(self) -> list[str]:
        """List all Python script files in the project's scripts directory.

        Returns:
            List of project-relative .py file paths.
        """
        if self.project_service is None or not self.project_service.has_project:
            return []
        scripts_root = self.project_service.get_project_path("scripts")
        return [
            self.project_service.to_relative_path(path)
            for path in sorted(scripts_root.rglob("*.py"))
            if path.is_file()
        ]

    def refresh_asset_catalog(self) -> ActionResult:
        """Scan the project assets directory and rebuild the asset catalog.

        Returns:
            ActionResult with the updated catalog count and data.
        """
        if self.asset_service is None:
            return self.fail("Asset service not ready")
        catalog = self.asset_service.refresh_catalog()
        return self.ok("Asset catalog refreshed", {"count": len(catalog.get("assets", [])), "catalog": catalog})

    def build_asset_artifacts(self) -> ActionResult:
        """Build pipeline artifacts (processed textures, atlases) for all assets.

        Returns:
            ActionResult with the build report.
        """
        if self.asset_service is None:
            return self.fail("Asset service not ready")
        report = self.asset_service.build_asset_artifacts()
        return self.ok("Asset artifacts built", report)

    def create_asset_bundle(self) -> ActionResult:
        """Package all project assets into a deployable bundle.

        Returns:
            ActionResult with the bundle creation report.
        """
        if self.asset_service is None:
            return self.fail("Asset service not ready")
        report = self.asset_service.create_bundle()
        return self.ok("Asset bundle created", report)

    def find_assets(
        self,
        search: str = "",
        asset_kind: str = "",
        importer: str = "",
        extensions: Optional[list[str]] = None,
    ) -> list[Dict[str, Union[str, int, float, bool, list, dict, None]]]:
        """Search for assets with flexible filtering criteria.

        Args:
            search: Text search in asset name or path.
            asset_kind: Filter by asset kind (e.g. "sprite", "audio").
            importer: Filter by importer name.
            extensions: Filter by file extensions (e.g. [".png", ".jpg"]).

        Returns:
            List of matching asset info dictionaries.
        """
        if self.asset_service is None:
            return []
        return self.asset_service.find_assets(search=search, asset_kind=asset_kind, importer=importer, extensions=extensions)

    def get_asset_reference(self, locator: str) -> Dict[str, str]:
        """Resolve an asset locator (path or GUID) to a canonical reference.

        Args:
            locator: Asset path, GUID, or name.

        Returns:
            Dictionary with "guid" and "path" keys, or empty values if not found.
        """
        if self.asset_service is None:
            return {"guid": "", "path": ""}
        return self.asset_service.get_asset_reference(locator)

    def move_asset(self, locator: str, destination_path: str) -> ActionResult:
        """Move an asset to a new location within the project.

        Args:
            locator: Current asset path or GUID.
            destination_path: New path for the asset.

        Returns:
            ActionResult with the new asset info, or failure if the move failed.
        """
        if self.asset_service is None:
            return self.fail("Asset service not ready")
        moved = self.asset_service.move_asset(locator, destination_path)
        return self.ok("Asset moved", moved) if moved is not None else self.fail("Asset move failed")

    def rename_asset(self, locator: str, new_name: str) -> ActionResult:
        """Rename an asset in the project.

        Args:
            locator: Current asset path or GUID.
            new_name: New name for the asset.

        Returns:
            ActionResult with the renamed asset info, or failure if the rename failed.
        """
        if self.asset_service is None:
            return self.fail("Asset service not ready")
        renamed = self.asset_service.rename_asset(locator, new_name)
        return self.ok("Asset renamed", renamed) if renamed is not None else self.fail("Asset rename failed")

    def reimport_asset(self, locator: str) -> ActionResult:
        """Re-import an asset, reprocessing it through its importer pipeline.

        Args:
            locator: Asset path or GUID.

        Returns:
            ActionResult with the reimported asset info.
        """
        if self.asset_service is None:
            return self.fail("Asset service not ready")
        reimported = self.asset_service.reimport_asset(locator)
        return self.ok("Asset reimported", reimported) if reimported is not None else self.fail("Asset reimport failed")

    def get_sprite_metadata(self, asset_path: str) -> Dict[str, Union[str, int, float, bool, list, dict, None]]:
        """Get metadata for a sprite asset, including slices and image info.

        Args:
            asset_path: Path or GUID of the sprite asset.

        Returns:
            Dictionary with sprite metadata (slices, dimensions, etc.), or empty
            dict if not found.
        """
        if self.asset_service is None:
            return {}
        return self.asset_service.get_sprite_metadata(asset_path)

    def get_asset_metadata(self, asset_path: str) -> Dict[str, Any]:
        """Alias for get_sprite_metadata. Gets metadata for an asset.

        Args:
            asset_path: Path or GUID of the asset.

        Returns:
            Dictionary with asset metadata.
        """
        return self.get_sprite_metadata(asset_path)

    def save_asset_metadata(self, asset_path: str, metadata: Dict[str, Union[str, int, float, bool, list, dict, None]]) -> ActionResult:
        """Persist custom metadata for an asset.

        Args:
            asset_path: Path or GUID of the asset.
            metadata: Metadata dictionary to save.

        Returns:
            ActionResult with the saved metadata.
        """
        if self.asset_service is None:
            return self.fail("Asset service not ready")
        saved = self.asset_service.save_metadata(asset_path, metadata)
        return self.ok("Asset metadata saved", saved)

    def generate_sprite_grid_slices(
        self,
        asset_path: str,
        cell_width: int,
        cell_height: int,
        margin: int = 0,
        spacing: int = 0,
        pivot_x: float = 0.5,
        pivot_y: float = 0.5,
        naming_prefix: Optional[str] = None,
    ) -> ActionResult:
        """Auto-slice a sprite sheet using a uniform grid layout.

        Args:
            asset_path: Path or GUID of the sprite asset.
            cell_width: Width of each cell in pixels.
            cell_height: Height of each cell in pixels.
            margin: Margin pixels from the edges.
            spacing: Spacing pixels between cells.
            pivot_x: Normalized pivot x (0.0 to 1.0) for all slices.
            pivot_y: Normalized pivot y (0.0 to 1.0) for all slices.
            naming_prefix: Optional prefix for generated slice names.

        Returns:
            ActionResult with the generated slice metadata.
        """
        if self.asset_service is None:
            return self.fail("Asset service not ready")
        metadata = self.asset_service.generate_sprite_grid_slices(
            asset_path,
            cell_width=cell_width,
            cell_height=cell_height,
            margin=margin,
            spacing=spacing,
            pivot_x=pivot_x,
            pivot_y=pivot_y,
            naming_prefix=naming_prefix,
        )
        return self.ok("Sprite grid slices created", metadata)

    def create_grid_slices(
        self,
        asset_path: str,
        cell_width: int,
        cell_height: int,
        margin: int = 0,
        spacing: int = 0,
        pivot_x: float = 0.5,
        pivot_y: float = 0.5,
        naming_prefix: Optional[str] = None,
    ) -> ActionResult:
        """Alias for generate_sprite_grid_slices. Creates uniform grid slices.

        Args:
            asset_path: Path or GUID of the sprite asset.
            cell_width: Cell width in pixels.
            cell_height: Cell height in pixels.
            margin: Margin from edges.
            spacing: Spacing between cells.
            pivot_x: Normalized pivot x.
            pivot_y: Normalized pivot y.
            naming_prefix: Prefix for slice names.

        Returns:
            ActionResult with the generated slice metadata.
        """
        return self.generate_sprite_grid_slices(
            asset_path=asset_path,
            cell_width=cell_width,
            cell_height=cell_height,
            margin=margin,
            spacing=spacing,
            pivot_x=pivot_x,
            pivot_y=pivot_y,
            naming_prefix=naming_prefix,
        )

    def list_sprite_slices(self, asset_path: str) -> list[Dict[str, Union[str, int, float, bool, list, dict, None]]]:
        """List all sprite slices defined for an asset.

        Args:
            asset_path: Path or GUID of the sprite asset.

        Returns:
            List of slice definition dictionaries.
        """
        if self.asset_service is None:
            return []
        return self.asset_service.list_sprite_slices(asset_path)

    def list_asset_slices(self, asset_path: str) -> list[Dict[str, Union[str, int, float, bool, list, dict, None]]]:
        """Alias for list_sprite_slices. Lists all slices for an asset.

        Args:
            asset_path: Path or GUID of the asset.

        Returns:
            List of slice definition dictionaries.
        """
        return self.list_sprite_slices(asset_path)

    def get_sprite_slice_rect(self, asset_path: str, slice_name: str) -> Optional[Dict[str, Union[str, int, float, bool, list, dict, None]]]:
        """Get the pixel rectangle for a named sprite slice.

        Args:
            asset_path: Path or GUID of the sprite asset.
            slice_name: Name of the slice.

        Returns:
            Dictionary with x, y, width, height keys, or None if not found.
        """
        if self.asset_service is None:
            return None
        return self.asset_service.get_sprite_slice_rect(asset_path, slice_name)

    def preview_auto_slices(
        self,
        asset_path: str,
        pivot_x: float = 0.5,
        pivot_y: float = 0.5,
        naming_prefix: Optional[str] = None,
        alpha_threshold: int = 1,
        color_tolerance: int = 12,
    ) -> list[Dict[str, Union[str, int, float, bool, list, dict, None]]]:
        """Preview auto-detected slices without saving them.

        Args:
            asset_path: Path or GUID of the sprite asset.
            pivot_x: Normalized pivot x for detected slices.
            pivot_y: Normalized pivot y for detected slices.
            naming_prefix: Optional prefix for generated slice names.
            alpha_threshold: Alpha value threshold for empty pixel detection.
            color_tolerance: Color difference tolerance for region detection.

        Returns:
            List of detected slice region dictionaries.
        """
        if self.asset_service is None:
            return []
        return self.asset_service.preview_auto_slices(
            asset_path,
            pivot_x=pivot_x,
            pivot_y=pivot_y,
            naming_prefix=naming_prefix,
            alpha_threshold=alpha_threshold,
            color_tolerance=color_tolerance,
        )

    def generate_sprite_auto_slices(
        self,
        asset_path: str,
        pivot_x: float = 0.5,
        pivot_y: float = 0.5,
        naming_prefix: Optional[str] = None,
        alpha_threshold: int = 1,
    ) -> ActionResult:
        """Auto-detect and save sprite slices using transparency analysis.

        Args:
            asset_path: Path or GUID of the sprite asset.
            pivot_x: Normalized pivot x for detected slices.
            pivot_y: Normalized pivot y for detected slices.
            naming_prefix: Optional prefix for generated slice names.
            alpha_threshold: Alpha value threshold for empty pixel detection.

        Returns:
            ActionResult with the generated slice metadata.
        """
        if self.asset_service is None:
            return self.fail("Asset service not ready")
        try:
            metadata = self.asset_service.generate_sprite_auto_slices(
                asset_path,
                pivot_x=pivot_x,
                pivot_y=pivot_y,
                naming_prefix=naming_prefix,
                alpha_threshold=alpha_threshold,
            )
            return self.ok("Sprite auto slices created", metadata)
        except Exception as exc:
            return self.fail(f"Sprite auto slice generation failed: {exc}")

    def create_auto_slices(
        self,
        asset_path: str,
        pivot_x: float = 0.5,
        pivot_y: float = 0.5,
        naming_prefix: Optional[str] = None,
        alpha_threshold: int = 1,
    ) -> ActionResult:
        """Alias for generate_sprite_auto_slices. Creates auto-detected slices.

        Args:
            asset_path: Path or GUID of the sprite asset.
            pivot_x: Normalized pivot x.
            pivot_y: Normalized pivot y.
            naming_prefix: Prefix for slice names.
            alpha_threshold: Alpha threshold for empty pixel detection.

        Returns:
            ActionResult with the generated slice metadata.
        """
        return self.generate_sprite_auto_slices(
            asset_path=asset_path,
            pivot_x=pivot_x,
            pivot_y=pivot_y,
            naming_prefix=naming_prefix,
            alpha_threshold=alpha_threshold,
        )

    def save_sprite_manual_slices(
        self,
        asset_path: str,
        slices: list[Dict[str, Union[str, int, float, bool, list, dict, None]]],
        pivot_x: float = 0.5,
        pivot_y: float = 0.5,
        naming_prefix: Optional[str] = None,
    ) -> ActionResult:
        """Manually define and save sprite slices for an asset.

        Args:
            asset_path: Path or GUID of the sprite asset.
            slices: List of slice definition dictionaries, each with x, y, width,
                height, and optionally name.
            pivot_x: Default normalized pivot x.
            pivot_y: Default normalized pivot y.
            naming_prefix: Prefix for slice names.

        Returns:
            ActionResult with the saved slice metadata.
        """
        if self.asset_service is None:
            return self.fail("Asset service not ready")
        try:
            metadata = self.asset_service.save_sprite_manual_slices(
                asset_path,
                slices=slices,
                pivot_x=pivot_x,
                pivot_y=pivot_y,
                naming_prefix=naming_prefix,
            )
            return self.ok("Sprite manual slices saved", metadata)
        except Exception as exc:
            return self.fail(f"Sprite manual slice save failed: {exc}")

    def save_manual_slices(
        self,
        asset_path: str,
        slices: list[Dict[str, Union[str, int, float, bool, list, dict, None]]],
        pivot_x: float = 0.5,
        pivot_y: float = 0.5,
        naming_prefix: Optional[str] = None,
    ) -> ActionResult:
        """Alias for save_sprite_manual_slices. Saves manually-defined slices.

        Args:
            asset_path: Path or GUID of the sprite asset.
            slices: List of slice definition dictionaries.
            pivot_x: Default normalized pivot x.
            pivot_y: Default normalized pivot y.
            naming_prefix: Prefix for slice names.

        Returns:
            ActionResult with the saved slice metadata.
        """
        return self.save_sprite_manual_slices(
            asset_path=asset_path,
            slices=slices,
            pivot_x=pivot_x,
            pivot_y=pivot_y,
            naming_prefix=naming_prefix,
        )

    def get_capability_registry(self) -> Dict[str, Any]:
        """Get the full AI capability registry as a dictionary.

        Returns:
            Dictionary with schema_version, engine info, and capabilities list.
        """
        from engine.ai import get_default_registry

        return get_default_registry().to_dict()

    def _get_capability_registry_object(self):
        """Get the raw CapabilityRegistry object (internal use for diagnostics)."""
        from engine.ai import get_default_registry

        return get_default_registry()

    def list_recipes(self) -> list[Dict[str, Any]]:
        """List all bundled declarative AI recipes.

        Returns:
            List of recipe summary dictionaries (id, version, description, etc.).
        """
        from engine.recipes import list_recipes as _list_recipes

        return _list_recipes()

    def get_recipe(self, recipe_id: str) -> Dict[str, Any]:
        """Get a single bundled declarative AI recipe by id.

        Args:
            recipe_id: The recipe identifier string.

        Returns:
            Recipe payload dictionary.

        Raises:
            RecipeNotFoundError: If the recipe id is unknown.
        """
        from engine.recipes import get_recipe as _get_recipe

        return _get_recipe(recipe_id)

    def run_recipe(self, recipe_id: str) -> Dict[str, Any]:
        """Run a bundled declarative AI recipe against the current project.

        Args:
            recipe_id: The recipe identifier string.

        Returns:
            Dictionary with execution results (steps, validations, events, etc.).

        Raises:
            RecipeNotFoundError: If the recipe id is unknown.
            RecipeValidationError: If the recipe commands are not allowlisted.
        """
        from engine.recipes import run_recipe as _run_recipe

        project_root = Path(self.project_service.project_root) if self.project_service else Path.cwd()
        return _run_recipe(recipe_id, project_root)

    def get_sprite_image_size(self, asset_path: str) -> Dict[str, int]:
        """Get the pixel dimensions of a sprite asset.

        Args:
            asset_path: Path or GUID of the sprite asset.

        Returns:
            Dictionary with "width" and "height" keys, or zeros if not found.
        """
        if self.asset_service is None:
            return {"width": 0, "height": 0}
        width, height = self.asset_service.get_sprite_image_size(asset_path)
        return {"width": width, "height": height}

    def get_asset_image_size(self, asset_path: str) -> Dict[str, int]:
        """Alias for get_sprite_image_size. Gets image dimensions for an asset.

        Args:
            asset_path: Path or GUID of the asset.

        Returns:
            Dictionary with "width" and "height" keys.
        """
        return self.get_sprite_image_size(asset_path)

    def import_sprite_asset(self, source_path: str, target_folder: str = "", overwrite: bool = False) -> ActionResult:
        """Import an external image file as a sprite asset into the project.

        Args:
            source_path: Path to the source image file.
            target_folder: Destination folder within the project assets directory.
            overwrite: If True, overwrite existing files.

        Returns:
            ActionResult with the imported asset path.
        """
        if self.asset_service is None:
            return self.fail("Asset service not ready")
        try:
            imported_path = self.asset_service.import_sprite_asset(
                source_path,
                target_folder=target_folder,
                overwrite=overwrite,
            )
            return self.ok("Sprite asset imported", {"path": imported_path})
        except Exception as exc:
            return self.fail(f"Sprite import failed: {exc}")
