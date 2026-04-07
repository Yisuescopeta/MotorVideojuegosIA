from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from cli.headless_game import HeadlessGame
from engine.core.game import Game
from engine.events.event_bus import EventBus
from engine.events.rule_system import RuleSystem
from engine.levels.component_registry import create_default_registry
from engine.physics.box2d_backend import Box2DPhysicsBackend
from engine.project.build_settings import BuildManifest, BuildTargetPlatform, utc_now_iso
from engine.scenes.scene_manager import SceneManager
from engine.systems.animation_system import AnimationSystem
from engine.systems.audio_system import AudioSystem
from engine.systems.character_controller_system import CharacterControllerSystem
from engine.systems.collision_system import CollisionSystem
from engine.systems.input_system import InputSystem
from engine.systems.physics_system import PhysicsSystem
from engine.systems.player_controller_system import PlayerControllerSystem
from engine.systems.render_system import RenderSystem
from engine.systems.script_behaviour_system import ScriptBehaviourSystem
from engine.systems.selection_system import SelectionSystem
from engine.systems.ui_render_system import UIRenderSystem
from engine.systems.ui_system import UISystem


@dataclass(frozen=True)
class RuntimeBootstrapDiagnostic:
    severity: str
    code: str
    message: str
    path: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "severity": self.severity,
            "code": self.code,
            "message": self.message,
            "path": self.path,
        }


class RuntimeBootstrapError(RuntimeError):
    def __init__(self, diagnostics: list[RuntimeBootstrapDiagnostic]) -> None:
        self.diagnostics = list(diagnostics)
        super().__init__(self._build_message(self.diagnostics))

    @staticmethod
    def _build_message(diagnostics: list[RuntimeBootstrapDiagnostic]) -> str:
        if not diagnostics:
            return "Runtime bootstrap failed"
        return " | ".join(
            f"{item.code}: {item.message}" if not item.path else f"{item.code}: {item.message} [{item.path}]"
            for item in diagnostics
        )


@dataclass(frozen=True)
class RuntimeManifest:
    SCHEMA_NAME = "motorvideojuegosia.runtime_manifest"
    SCHEMA_VERSION = 1
    RUNTIME_DIR = "runtime"
    FILE_NAME = "runtime_manifest.json"
    DEFAULT_CONTENT_ROOT = "runtime/content"
    DEFAULT_METADATA_ROOT = "runtime/metadata"
    DEFAULT_BUILD_MANIFEST_PATH = "runtime/metadata/build_manifest.json"

    schema: str
    schema_version: int
    generated_at_utc: str
    target_platform: BuildTargetPlatform
    startup_scene: str
    content_root: str
    metadata_root: str
    build_manifest_path: str
    selected_content_summary: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "schema_version": self.schema_version,
            "generated_at_utc": self.generated_at_utc,
            "target_platform": self.target_platform.value,
            "startup_scene": self.startup_scene,
            "content_root": self.content_root,
            "metadata_root": self.metadata_root,
            "build_manifest_path": self.build_manifest_path,
            "selected_content_summary": {
                key: int(self.selected_content_summary.get(key, 0))
                for key in ("scenes", "prefabs", "scripts", "assets", "metadata")
            },
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RuntimeManifest":
        if not isinstance(data, dict):
            raise ValueError("Runtime manifest must be a JSON object")
        schema = str(data.get("schema", "")).strip()
        if schema != cls.SCHEMA_NAME:
            raise ValueError("Unsupported runtime manifest schema")
        try:
            schema_version = int(data.get("schema_version", 0))
        except (TypeError, ValueError) as exc:
            raise ValueError("Runtime manifest schema_version must be an integer") from exc
        if schema_version != cls.SCHEMA_VERSION:
            raise ValueError("Unsupported runtime manifest schema_version")
        try:
            target_platform = BuildTargetPlatform(str(data.get("target_platform", "")).strip())
        except ValueError as exc:
            raise ValueError("Unsupported runtime manifest target platform") from exc
        raw_summary = data.get("selected_content_summary", {})
        summary = dict(raw_summary) if isinstance(raw_summary, dict) else {}
        return cls(
            schema=schema,
            schema_version=schema_version,
            generated_at_utc=str(data.get("generated_at_utc", "")).strip(),
            target_platform=target_platform,
            startup_scene=_normalize_manifest_relative_path(
                data.get("startup_scene", ""),
                purpose="startup_scene",
            ),
            content_root=_normalize_manifest_relative_path(
                data.get("content_root", cls.DEFAULT_CONTENT_ROOT),
                purpose="content_root",
            ),
            metadata_root=_normalize_manifest_relative_path(
                data.get("metadata_root", cls.DEFAULT_METADATA_ROOT),
                purpose="metadata_root",
            ),
            build_manifest_path=_normalize_manifest_relative_path(
                data.get("build_manifest_path", cls.DEFAULT_BUILD_MANIFEST_PATH),
                purpose="build_manifest_path",
            ),
            selected_content_summary={
                str(key): int(value)
                for key, value in sorted(summary.items(), key=lambda item: str(item[0]).lower())
                if str(key).strip()
            },
        )


@dataclass(frozen=True)
class BootstrappedRuntime:
    game: Game
    scene_manager: SceneManager
    runtime_manifest: RuntimeManifest
    build_manifest: BuildManifest
    content_resolver: "PackagedContentResolver"
    startup_scene_path: str


def runtime_manifest_from_build_manifest(
    build_manifest: BuildManifest,
    *,
    generated_at_utc: str | None = None,
    startup_scene: str,
    content_root: str = RuntimeManifest.DEFAULT_CONTENT_ROOT,
    metadata_root: str = RuntimeManifest.DEFAULT_METADATA_ROOT,
    build_manifest_path: str = RuntimeManifest.DEFAULT_BUILD_MANIFEST_PATH,
    selected_content_summary: dict[str, int] | None = None,
) -> RuntimeManifest:
    return RuntimeManifest(
        schema=RuntimeManifest.SCHEMA_NAME,
        schema_version=RuntimeManifest.SCHEMA_VERSION,
        generated_at_utc=generated_at_utc or utc_now_iso(),
        target_platform=build_manifest.target_platform,
        startup_scene=_normalize_manifest_relative_path(startup_scene, purpose="startup_scene"),
        content_root=_normalize_manifest_relative_path(content_root, purpose="content_root"),
        metadata_root=_normalize_manifest_relative_path(metadata_root, purpose="metadata_root"),
        build_manifest_path=_normalize_manifest_relative_path(build_manifest_path, purpose="build_manifest_path"),
        selected_content_summary=dict(selected_content_summary or {}),
    )


class PackagedContentResolver:
    def __init__(self, build_root: str | Path, runtime_manifest: RuntimeManifest) -> None:
        self._build_root = Path(build_root).expanduser().resolve()
        self._runtime_manifest = runtime_manifest
        self._content_root = self.resolve_build_path(runtime_manifest.content_root)
        self._metadata_root = self.resolve_build_path(runtime_manifest.metadata_root)

    @property
    def build_root(self) -> Path:
        return self._build_root

    @property
    def content_root(self) -> Path:
        return self._content_root

    @property
    def metadata_root(self) -> Path:
        return self._metadata_root

    @property
    def scripts_root(self) -> Path:
        return self._content_root / "scripts"

    def resolve_build_path(self, relative_path: str | Path) -> Path:
        return self._resolve_within(self._build_root, relative_path, purpose="build path")

    def resolve_content_path(self, relative_path: str | Path) -> Path:
        return self._resolve_within(self._content_root, relative_path, purpose="content path")

    def resolve_metadata_path(self, relative_path: str | Path) -> Path:
        return self._resolve_within(self._metadata_root, relative_path, purpose="metadata path")

    def resolve_entry(self, locator: Any) -> dict[str, Any] | None:
        relative_path = self._locator_path(locator)
        if not relative_path:
            return None
        try:
            absolute_path = self.resolve_content_path(relative_path)
        except ValueError:
            return None
        if not absolute_path.exists() or not absolute_path.is_file():
            return None
        return {
            "path": relative_path,
            "absolute_path": absolute_path.as_posix(),
            "guid": "",
            "reference": {
                "guid": "",
                "path": relative_path,
            },
        }

    def resolve_path(self, locator: Any) -> str:
        relative_path = self._locator_path(locator)
        if not relative_path:
            return ""
        try:
            return self.resolve_content_path(relative_path).as_posix()
        except ValueError:
            return ""

    def resolve_module_name(self, locator: Any) -> str:
        relative_path = self._locator_path(locator)
        if not relative_path:
            if isinstance(locator, str):
                return str(locator).strip().replace("\\", "/").strip("/").replace("/", ".")
            return ""
        module_path = relative_path
        if module_path.endswith(".py"):
            if module_path.startswith("scripts/"):
                module_path = module_path[len("scripts/") :]
            module_path = module_path[:-3]
        return module_path.replace("\\", "/").strip("/").replace("/", ".")

    def _locator_path(self, locator: Any) -> str:
        if isinstance(locator, dict):
            path = str(locator.get("path", "")).strip()
        else:
            path = str(locator or "").strip()
        if not path:
            return ""
        if path.endswith(".py") or "/" in path or "\\" in path or "." in Path(path).name:
            return _normalize_manifest_relative_path(path, purpose="asset locator")
        return path

    def _resolve_within(self, root: Path, relative_path: str | Path, *, purpose: str) -> Path:
        normalized = _normalize_manifest_relative_path(relative_path, purpose=purpose)
        candidate = (root / normalized).resolve()
        try:
            candidate.relative_to(root)
        except ValueError as exc:
            raise ValueError(f"Runtime {purpose} escapes packaged root") from exc
        return candidate


class StandaloneRuntimeBootstrap:
    def bootstrap(self, build_root: str | Path, *, headless: bool = True) -> BootstrappedRuntime:
        root = Path(build_root).expanduser().resolve()
        runtime_manifest_path = root / RuntimeManifest.RUNTIME_DIR / RuntimeManifest.FILE_NAME
        runtime_manifest = self._load_runtime_manifest(runtime_manifest_path)
        if runtime_manifest.target_platform is not BuildTargetPlatform.WINDOWS_DESKTOP:
            self._raise(
                RuntimeBootstrapDiagnostic(
                    severity="error",
                    code="runtime_manifest.unsupported_target",
                    message="Standalone runtime bootstrap only supports windows_desktop.",
                    path=runtime_manifest_path.as_posix(),
                )
            )
        resolver = PackagedContentResolver(root, runtime_manifest)
        if not resolver.content_root.exists() or not resolver.content_root.is_dir():
            self._raise(
                RuntimeBootstrapDiagnostic(
                    severity="error",
                    code="packaged_content.content_root_missing",
                    message="Packaged runtime content root was not found.",
                    path=resolver.content_root.as_posix(),
                )
            )
        build_manifest_path = resolver.resolve_build_path(runtime_manifest.build_manifest_path)
        build_manifest = self._load_build_manifest(build_manifest_path)
        startup_scene_path = resolver.resolve_content_path(runtime_manifest.startup_scene)
        if not startup_scene_path.exists() or not startup_scene_path.is_file():
            self._raise(
                RuntimeBootstrapDiagnostic(
                    severity="error",
                    code="packaged_content.startup_scene_missing",
                    message="Packaged startup scene was not found.",
                    path=startup_scene_path.as_posix(),
                )
            )

        game = self._create_game(runtime_manifest, resolver, headless=headless)
        scene_manager = game._scene_manager  # type: ignore[attr-defined]
        if scene_manager is None:
            self._raise(
                RuntimeBootstrapDiagnostic(
                    severity="error",
                    code="runtime.scene_manager_missing",
                    message="Runtime scene manager was not initialized.",
                )
            )

        try:
            payload = json.loads(startup_scene_path.read_text(encoding="utf-8"))
        except Exception as exc:
            self._raise(
                RuntimeBootstrapDiagnostic(
                    severity="error",
                    code="packaged_content.startup_scene_unreadable",
                    message=f"Packaged startup scene is unreadable: {exc}",
                    path=startup_scene_path.as_posix(),
                )
            )

        try:
            world = scene_manager.load_scene(payload, source_path=startup_scene_path.as_posix(), activate=True)
        except Exception as exc:
            self._raise(
                RuntimeBootstrapDiagnostic(
                    severity="error",
                    code="packaged_content.startup_scene_invalid",
                    message=f"Packaged startup scene failed to load: {exc}",
                    path=startup_scene_path.as_posix(),
                )
            )

        game.set_world(world)
        game.play()
        return BootstrappedRuntime(
            game=game,
            scene_manager=scene_manager,
            runtime_manifest=runtime_manifest,
            build_manifest=build_manifest,
            content_resolver=resolver,
            startup_scene_path=startup_scene_path.as_posix(),
        )

    def _load_runtime_manifest(self, path: Path) -> RuntimeManifest:
        if not path.exists():
            self._raise(
                RuntimeBootstrapDiagnostic(
                    severity="error",
                    code="runtime_manifest.missing",
                    message="Runtime manifest was not found.",
                    path=path.as_posix(),
                )
            )
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            return RuntimeManifest.from_dict(payload)
        except Exception as exc:
            self._raise(
                RuntimeBootstrapDiagnostic(
                    severity="error",
                    code="runtime_manifest.invalid",
                    message=f"Runtime manifest could not be loaded: {exc}",
                    path=path.as_posix(),
                )
            )

    def _load_build_manifest(self, path: Path) -> BuildManifest:
        if not path.exists():
            self._raise(
                RuntimeBootstrapDiagnostic(
                    severity="error",
                    code="build_manifest.missing",
                    message="Build manifest was not found for the packaged runtime.",
                    path=path.as_posix(),
                )
            )
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            return BuildManifest.from_dict(payload)
        except Exception as exc:
            self._raise(
                RuntimeBootstrapDiagnostic(
                    severity="error",
                    code="build_manifest.invalid",
                    message=f"Build manifest could not be loaded: {exc}",
                    path=path.as_posix(),
                )
            )

    def _create_game(self, manifest: RuntimeManifest, resolver: PackagedContentResolver, *, headless: bool) -> Game:
        _ = manifest
        game: Game = HeadlessGame() if headless else Game(title="Motor 2D")
        registry = create_default_registry()
        scene_manager = SceneManager(registry)
        event_bus = EventBus()  # type: ignore
        render_system = RenderSystem()
        physics_system = PhysicsSystem(gravity=600)
        collision_system = CollisionSystem(event_bus)
        animation_system = AnimationSystem(event_bus)
        audio_system = AudioSystem()
        input_system = InputSystem()
        player_controller_system = PlayerControllerSystem()
        character_controller_system = CharacterControllerSystem()
        script_behaviour_system = ScriptBehaviourSystem()
        selection_system = SelectionSystem()
        ui_system = UISystem()
        ui_render_system = UIRenderSystem()
        rule_system = RuleSystem(event_bus)

        render_system.set_content_resolver(resolver)
        audio_system.set_content_resolver(resolver)
        script_behaviour_system.set_content_resolver(resolver)

        game.hot_reload_manager.scripts_dir = resolver.scripts_root.as_posix()
        game.hot_reload_manager.scan_directory()

        game.set_scene_manager(scene_manager)
        game.set_render_system(render_system)
        game.set_physics_system(physics_system)
        game.set_collision_system(collision_system)
        game.set_animation_system(animation_system)
        game.set_audio_system(audio_system)
        game.set_input_system(input_system)
        game.set_character_controller_system(character_controller_system)
        game.set_player_controller_system(player_controller_system)
        game.set_script_behaviour_system(script_behaviour_system)
        game.set_event_bus(event_bus)
        game.set_rule_system(rule_system)
        game.set_selection_system(selection_system)
        game.set_ui_system(ui_system)
        game.set_ui_render_system(ui_render_system)
        self._register_optional_box2d_backend(game, gravity=physics_system.gravity, event_bus=event_bus)
        return game

    def _register_optional_box2d_backend(self, game: Game, *, gravity: float, event_bus: EventBus) -> None:
        try:
            backend = Box2DPhysicsBackend(gravity=gravity, event_bus=event_bus)
            game.set_physics_backend(backend, backend_name="box2d")
        except Exception as exc:
            game.set_physics_backend_unavailable("box2d", str(exc))

    def _raise(self, *diagnostics: RuntimeBootstrapDiagnostic) -> None:
        raise RuntimeBootstrapError(list(diagnostics))


class StandaloneRuntimeLauncher:
    def __init__(self, bootstrap: StandaloneRuntimeBootstrap | None = None) -> None:
        self._bootstrap = bootstrap or StandaloneRuntimeBootstrap()

    def run(
        self,
        build_root: str | Path,
        *,
        headless: bool = True,
        frames: int = 0,
        seed: int | None = None,
    ) -> BootstrappedRuntime:
        runtime = self._bootstrap.bootstrap(build_root, headless=headless)
        if seed is not None:
            runtime.game.set_seed(seed)
        if headless and frames > 0 and hasattr(runtime.game, "step_frame"):
            for _ in range(max(0, int(frames))):
                runtime.game.step_frame()
            return runtime
        runtime.game.run()
        return runtime


def _normalize_manifest_relative_path(value: Any, *, purpose: str) -> str:
    raw = str(value or "").strip().replace("\\", "/")
    if not raw:
        raise ValueError(f"Runtime manifest {purpose} cannot be empty")
    candidate = Path(raw)
    if candidate.is_absolute():
        raise ValueError(f"Runtime manifest {purpose} must be relative")
    normalized = candidate.as_posix().strip("/")
    if not normalized or normalized in {".", ".."}:
        raise ValueError(f"Runtime manifest {purpose} cannot be empty")
    parts = [part for part in normalized.split("/") if part]
    if any(part == ".." for part in parts):
        raise ValueError(f"Runtime manifest {purpose} must stay inside the packaged build")
    return "/".join(parts)
