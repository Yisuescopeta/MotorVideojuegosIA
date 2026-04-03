from __future__ import annotations

from typing import Any, Dict, Optional

from engine.api._context import EngineAPIComponent
from engine.api.types import ActionResult


class AssetsProjectAPI(EngineAPIComponent):
    """Project and asset management endpoints exposed by EngineAPI."""

    def list_recent_projects(self) -> list[Dict[str, Any]]:
        if self.project_service is None:
            return []
        return self.project_service.list_recent_projects()

    def get_project_manifest(self) -> Dict[str, Any]:
        if self.project_service is None:
            return {}
        return self.project_service.get_project_summary()

    def open_project(self, path: str) -> ActionResult:
        if self.project_service is None or self.game is None:
            return self.fail("Project service not ready")
        success = self.game.open_project(path)
        if not success:
            return self.fail("Open project failed")
        return self.ok("Project opened", {"path": self.project_service.project_root_display.as_posix()})

    def get_editor_state(self) -> Dict[str, Any]:
        if self.project_service is None:
            return {}
        return self.project_service.load_editor_state()

    def save_editor_state(self, data: Dict[str, Any]) -> ActionResult:
        if self.project_service is None:
            return self.fail("Project service not ready")
        self.project_service.save_editor_state(data)
        return self.ok("Editor state saved", self.project_service.load_editor_state())

    def list_project_assets(self, search: str = "") -> list[Dict[str, Any]]:
        if self.asset_service is None:
            return []
        return self.asset_service.list_assets(search=search)

    def list_project_prefabs(self) -> list[str]:
        if self.project_service is None or not self.project_service.has_project:
            return []
        return self.project_service.list_project_prefabs()

    def list_project_scripts(self) -> list[str]:
        if self.project_service is None or not self.project_service.has_project:
            return []
        scripts_root = self.project_service.get_project_path("scripts")
        return [
            self.project_service.to_relative_path(path)
            for path in sorted(scripts_root.rglob("*.py"))
            if path.is_file()
        ]

    def refresh_asset_catalog(self) -> ActionResult:
        if self.asset_service is None:
            return self.fail("Asset service not ready")
        catalog = self.asset_service.refresh_catalog()
        return self.ok("Asset catalog refreshed", {"count": len(catalog.get("assets", [])), "catalog": catalog})

    def build_asset_artifacts(self) -> ActionResult:
        if self.asset_service is None:
            return self.fail("Asset service not ready")
        report = self.asset_service.build_asset_artifacts()
        return self.ok("Asset artifacts built", report)

    def create_asset_bundle(self) -> ActionResult:
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
    ) -> list[Dict[str, Any]]:
        if self.asset_service is None:
            return []
        return self.asset_service.find_assets(search=search, asset_kind=asset_kind, importer=importer, extensions=extensions)

    def get_asset_reference(self, locator: str) -> Dict[str, str]:
        if self.asset_service is None:
            return {"guid": "", "path": ""}
        return self.asset_service.get_asset_reference(locator)

    def move_asset(self, locator: str, destination_path: str) -> ActionResult:
        if self.asset_service is None:
            return self.fail("Asset service not ready")
        moved = self.asset_service.move_asset(locator, destination_path)
        return self.ok("Asset moved", moved) if moved is not None else self.fail("Asset move failed")

    def rename_asset(self, locator: str, new_name: str) -> ActionResult:
        if self.asset_service is None:
            return self.fail("Asset service not ready")
        renamed = self.asset_service.rename_asset(locator, new_name)
        return self.ok("Asset renamed", renamed) if renamed is not None else self.fail("Asset rename failed")

    def reimport_asset(self, locator: str) -> ActionResult:
        if self.asset_service is None:
            return self.fail("Asset service not ready")
        reimported = self.asset_service.reimport_asset(locator)
        return self.ok("Asset reimported", reimported) if reimported is not None else self.fail("Asset reimport failed")

    def get_asset_metadata(self, asset_path: str) -> Dict[str, Any]:
        if self.asset_service is None:
            return {}
        return self.asset_service.load_metadata(asset_path)

    def save_asset_metadata(self, asset_path: str, metadata: Dict[str, Any]) -> ActionResult:
        if self.asset_service is None:
            return self.fail("Asset service not ready")
        saved = self.asset_service.save_metadata(asset_path, metadata)
        return self.ok("Asset metadata saved", saved)

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
        if self.asset_service is None:
            return self.fail("Asset service not ready")
        metadata = self.asset_service.generate_grid_slices(
            asset_path,
            cell_width=cell_width,
            cell_height=cell_height,
            margin=margin,
            spacing=spacing,
            pivot_x=pivot_x,
            pivot_y=pivot_y,
            naming_prefix=naming_prefix,
        )
        return self.ok("Grid slices created", metadata)

    def list_asset_slices(self, asset_path: str) -> list[Dict[str, Any]]:
        if self.asset_service is None:
            return []
        return self.asset_service.list_slices(asset_path)
