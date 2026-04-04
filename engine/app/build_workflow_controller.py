from __future__ import annotations

import json
from typing import Any, Callable


class BuildWorkflowController:
    """Owns editor-facing build-settings workflows without duplicating build logic."""

    LAST_REPORT_FILE_NAME = "player_build_report.json"

    def __init__(
        self,
        *,
        get_project_service: Callable[[], Any],
        get_build_settings_modal: Callable[[], Any],
        refresh_project_scene_entries: Callable[[], None],
        log_info: Callable[[str], None],
        log_err: Callable[[str], None],
    ) -> None:
        self._get_project_service = get_project_service
        self._get_build_settings_modal = get_build_settings_modal
        self._refresh_project_scene_entries = refresh_project_scene_entries
        self._log_info = log_info
        self._log_err = log_err

    def open_build_settings(self) -> bool:
        project_service = self._get_project_service()
        modal = self._get_build_settings_modal()
        if project_service is None or modal is None or not getattr(project_service, "has_project", False):
            return False
        self._refresh_project_scene_entries()
        modal.open(
            project_service.load_build_settings().to_dict(),
            project_service.list_project_scenes(),
            build_report=self._load_last_build_report(project_service),
        )
        return True

    def handle_modal_requests(self) -> None:
        modal = self._get_build_settings_modal()
        project_service = self._get_project_service()
        if modal is None or project_service is None or not modal.is_open:
            return

        if modal.consume_close_request():
            modal.close()
            return

        if modal.consume_save_request():
            self._save_modal_settings()

        if modal.consume_build_request():
            self._save_modal_settings()
            self._run_build_player()

    def _save_modal_settings(self) -> None:
        modal = self._get_build_settings_modal()
        project_service = self._get_project_service()
        if modal is None or project_service is None:
            return
        try:
            project_service.save_build_settings(modal.build_settings_payload())
            settings = project_service.load_build_settings()
            modal.apply_settings(settings.to_dict(), project_service.list_project_scenes())
            modal.set_status("Build settings saved.")
            self._log_info("Build settings updated.")
        except Exception as exc:
            modal.set_status(f"Build settings save failed: {exc}", is_error=True)
            self._log_err(f"Build settings save failed: {exc}")

    def _run_build_player(self) -> None:
        modal = self._get_build_settings_modal()
        project_service = self._get_project_service()
        if modal is None or project_service is None:
            return
        try:
            from engine.project.build_player import BuildPlayerService

            report = BuildPlayerService(project_service).build_player()
            payload = report.to_dict()
            modal.set_build_report(payload)
            if report.status == "succeeded":
                self._log_info(f"Build Player succeeded: {report.output_path}")
            else:
                error_items = payload.get("errors", [])
                first_error = dict(error_items[0]) if isinstance(error_items, list) and error_items else {}
                self._log_err(first_error.get("message", "Build Player failed"))
        except Exception as exc:
            modal.set_status(f"Build Player failed: {exc}", is_error=True)
            self._log_err(f"Build Player failed: {exc}")

    def _load_last_build_report(self, project_service: Any) -> dict[str, Any] | None:
        build_root = project_service.get_project_path("build")
        report_path = build_root / self.LAST_REPORT_FILE_NAME
        if not report_path.exists():
            return None
        try:
            payload = json.loads(report_path.read_text(encoding="utf-8"))
        except Exception:
            return None
        return dict(payload) if isinstance(payload, dict) else None
