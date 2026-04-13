from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
from types import SimpleNamespace

from engine.api import EngineAPI


class FakeSliceAssetService:
    def __init__(self, slices: dict[str, dict]) -> None:
        self._slices = slices

    def get_slice_rect(self, _reference, slice_name: str):
        return self._slices.get(slice_name)

    def load_metadata(self, _asset_path: str):
        return {}


class RegressionProjectHarness:
    def __init__(self) -> None:
        self._temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self._temp_dir.name)
        self.project_root = self.root / "RegressionProject"
        self.global_state_dir = self.root / "global_state"
        self.project_root.mkdir(parents=True, exist_ok=True)
        self.api = EngineAPI(
            project_root=self.project_root.as_posix(),
            global_state_dir=self.global_state_dir.as_posix(),
        )

    def close(self) -> None:
        self.api.shutdown()
        self._temp_dir.cleanup()

    @property
    def fixtures_root(self) -> Path:
        return Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "regression"

    def copy_level_fixture(self, fixture_name: str, *, target_name: str | None = None) -> Path:
        source = self.fixtures_root / fixture_name
        if not source.exists():
            raise FileNotFoundError(source)
        final_name = target_name or fixture_name
        target = self.project_root / "levels" / final_name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        return target

    def load_level_fixture(self, fixture_name: str, *, target_name: str | None = None) -> Path:
        level_path = self.copy_level_fixture(fixture_name, target_name=target_name)
        self.api.load_level(level_path.as_posix())
        return level_path

    def attach_fake_slice_service(self, slices: dict[str, dict]) -> None:
        fake_service = FakeSliceAssetService(slices)
        if self.api.game is None:
            return
        if self.api.game.render_system is not None:
            self.api.game.render_system._asset_service = fake_service

    def attach_fake_texture_loader(self, *, width: int = 128, height: int = 128) -> None:
        if self.api.game is None or self.api.game.render_system is None:
            return
        self.api.game.render_system._load_texture = lambda *_args, **_kwargs: SimpleNamespace(id=1, width=width, height=height)

    def build_render_graph(self) -> dict:
        if self.api.game is None or self.api.game.render_system is None or self.api.game.world is None:
            raise RuntimeError("Render graph unavailable")
        return self.api.game.render_system._public_graph(
            self.api.game.render_system._build_render_graph(self.api.game.world)
        )

    def build_raw_render_graph(self) -> dict:
        if self.api.game is None or self.api.game.render_system is None or self.api.game.world is None:
            raise RuntimeError("Render graph unavailable")
        return self.api.game.render_system._build_render_graph(self.api.game.world)

    def recent_event_names(self) -> list[str]:
        if self.api.game is None or self.api.game.event_bus is None:
            return []
        return [event.name for event in self.api.game.event_bus.get_recent_events()]
