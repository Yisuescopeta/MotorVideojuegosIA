import tempfile
import unittest
from dataclasses import FrozenInstanceError
from pathlib import Path

from engine.core.composition_root import EditorHost, EngineCompositionRoot, RuntimeHost
from engine.scenes.scene_manager import SceneManager


class EngineCompositionRootTests(unittest.TestCase):
    def test_runtime_graph_is_built_once_and_host_is_immutable(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = EngineCompositionRoot.compose_runtime(
                Path(temp_dir),
                auto_ensure_project=False,
            )

        self.assertIsInstance(root, EngineCompositionRoot)
        self.assertIsInstance(root.runtime_host, RuntimeHost)
        self.assertIsInstance(root.runtime_host.scene_manager, SceneManager)
        self.assertIsNone(root.editor_host)
        with self.assertRaises(FrozenInstanceError):
            root.runtime_host = None

    def test_editor_host_is_explicit_and_not_a_service_locator(self) -> None:
        application = object()
        shell = object()
        platform = object()

        root = EngineCompositionRoot.compose_editor(
            application=application,
            shell=shell,
            platform=platform,
        )

        self.assertIsInstance(root.editor_host, EditorHost)
        self.assertIs(root.editor_host.application, application)
        self.assertIs(root.editor_host.shell, shell)
        self.assertIs(root.editor_host.platform, platform)
        self.assertIsNone(root.runtime_host)
        self.assertFalse(hasattr(root, "resolve"))


if __name__ == "__main__":
    unittest.main()
