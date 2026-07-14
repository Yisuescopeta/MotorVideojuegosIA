import unittest
from unittest.mock import patch

from engine.editor.undo_redo import UndoRedoManager
from engine.levels.component_registry import create_default_registry
from engine.scenes.scene import Scene
from engine.scenes.scene_flow import SceneFlowPolicy
from engine.scenes.scene_manager import SceneManager

_MISSING = object()


def _scene_link(flow_key: str, target_path: object = _MISSING) -> dict[str, object]:
    link: dict[str, object] = {
        "enabled": True,
        "target_entity_name": "",
        "flow_key": flow_key,
        "preview_label": flow_key,
        "link_mode": "",
        "target_entry_id": "",
    }
    if target_path is not _MISSING:
        link["target_path"] = target_path
    return link


def _scene_payload(
    *,
    name: str = "FlowProbe",
    metadata: dict[str, str] | None = None,
    links: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    entities = [
        {
            "name": f"Portal_{index}",
            "active": True,
            "tag": "Untagged",
            "layer": "Default",
            "components": {"SceneLink": link},
        }
        for index, link in enumerate(links or [])
    ]
    feature_metadata = {"scene_flow": dict(metadata)} if metadata is not None else {}
    return {
        "name": name,
        "entities": entities,
        "rules": [],
        "feature_metadata": feature_metadata,
    }


class SceneFlowContractTests(unittest.TestCase):
    def _load(
        self,
        *,
        metadata: dict[str, str] | None = None,
        links: list[dict[str, object]] | None = None,
    ) -> SceneManager:
        manager = SceneManager(create_default_registry())
        manager.load_scene(_scene_payload(metadata=metadata, links=links))
        return manager

    def test_effective_flow_precedence_matrix(self) -> None:
        cases = (
            ("metadata_base", {"route": "levels/metadata.json"}, [], {"route": "levels/metadata.json"}, False),
            (
                "link_over_metadata",
                {"route": "levels/metadata.json"},
                [_scene_link("route", "levels/link.json")],
                {"route": "levels/link.json"},
                False,
            ),
            (
                "last_duplicate_link_wins",
                {"route": "levels/metadata.json"},
                [_scene_link("route", "levels/first.json"), _scene_link("route", "levels/last.json")],
                {"route": "levels/last.json"},
                False,
            ),
            (
                "explicit_empty_link_removes_metadata_key",
                {"route": "levels/metadata.json"},
                [_scene_link("route", "")],
                {},
                True,
            ),
            (
                "metadata_without_link_is_preserved",
                {"orphan": "levels/orphan.json"},
                [_scene_link("other", "levels/other.json")],
                {"orphan": "levels/orphan.json", "other": "levels/other.json"},
                False,
            ),
            ("empty_link_without_metadata_adds_nothing", None, [_scene_link("route", "")], {}, True),
        )

        for name, metadata, links, expected, invalid in cases:
            with self.subTest(name=name):
                manager = self._load(metadata=metadata, links=links)

                self.assertEqual(manager.get_scene_flow(), expected)
                self.assertEqual(manager.list_open_scenes()[0]["has_invalid_links"], invalid)

    def test_missing_target_path_is_filled_when_metadata_is_set(self) -> None:
        manager = self._load(
            metadata={"route": "levels/metadata.json"},
            links=[_scene_link("route", "levels/original.json")],
        )
        self.assertTrue(manager.current_scene.replace_component_data("Portal_0", "SceneLink", _scene_link("route")))

        self.assertTrue(manager.set_scene_flow_target("route", "levels/updated.json"))

        stored_link = manager.find_entity_data("Portal_0")["components"]["SceneLink"]

        self.assertEqual(stored_link["target_path"], "levels/updated.json")
        self.assertEqual(manager.get_scene_flow(), {"route": "levels/updated.json"})
        self.assertFalse(manager.list_open_scenes()[0]["has_invalid_links"])

    def test_scene_flow_target_preserves_undo_redo_history(self) -> None:
        manager = self._load(metadata={"route": "levels/original.json"})
        history = UndoRedoManager()
        manager.set_history_manager(history)

        self.assertTrue(
            manager.set_scene_flow_target(
                "route",
                "levels/updated.json",
            )
        )
        self.assertEqual(
            manager.get_scene_flow(),
            {"route": "levels/updated.json"},
        )

        self.assertTrue(history.undo())
        self.assertEqual(
            manager.get_scene_flow(),
            {"route": "levels/original.json"},
        )

        self.assertTrue(history.redo())
        self.assertEqual(
            manager.get_scene_flow(),
            {"route": "levels/updated.json"},
        )

    def test_present_empty_target_path_is_not_treated_as_missing_when_metadata_is_set(self) -> None:
        manager = self._load(
            metadata={"route": "levels/metadata.json"},
            links=[_scene_link("route", "")],
        )

        self.assertTrue(manager.set_scene_flow_target("route", "levels/updated.json"))

        stored_link = manager.find_entity_data("Portal_0")["components"]["SceneLink"]

        self.assertEqual(stored_link["target_path"], "")
        self.assertEqual(manager.get_scene_flow(), {})
        self.assertNotIn("route", manager.current_scene.feature_metadata.get("scene_flow", {}))
        self.assertTrue(manager.list_open_scenes()[0]["has_invalid_links"])

    def test_explicit_empty_target_removes_only_its_metadata_key(self) -> None:
        manager = self._load(
            metadata={"route": "levels/metadata.json", "orphan": "levels/orphan.json"},
            links=[_scene_link("route", "levels/link.json")],
        )

        self.assertTrue(manager.replace_component_data("Portal_0", "SceneLink", _scene_link("route", "")))

        self.assertEqual(
            manager.current_scene.feature_metadata["scene_flow"],
            {"orphan": "levels/orphan.json"},
        )
        self.assertEqual(
            manager.get_scene_flow(),
            {"orphan": "levels/orphan.json"},
        )
        self.assertTrue(manager.list_open_scenes()[0]["has_invalid_links"])

    def test_inactive_scene_flow_sync_does_not_depend_on_active_scene(self) -> None:
        manager = self._load(metadata={"primary": "levels/primary.json"})
        primary_key = manager.active_scene_key
        manager.load_scene(
            _scene_payload(
                name="Secondary",
                metadata={"route": "levels/metadata.json"},
                links=[_scene_link("route", "levels/initial.json")],
            ),
            source_path="secondary.json",
            activate=False,
        )
        secondary = next(entry for entry in manager.list_open_scenes() if entry["name"] == "Secondary")

        self.assertTrue(
            manager.upsert_component_for_scene(
                secondary["key"],
                "Portal_0",
                "SceneLink",
                _scene_link("route", "levels/updated.json"),
            )
        )
        secondary_entry = manager.resolve_entry(secondary["key"])

        self.assertEqual(manager.active_scene_key, primary_key)
        self.assertEqual(manager.get_scene_flow(), {"primary": "levels/primary.json"})
        self.assertEqual(
            secondary_entry.scene.feature_metadata["scene_flow"],
            {"route": "levels/updated.json"},
        )

        self.assertIsNotNone(manager.activate_scene(secondary["key"]))
        self.assertEqual(manager.get_scene_flow(), {"route": "levels/updated.json"})

    def test_explicit_empty_target_has_active_inactive_parity(self) -> None:
        manager = self._load(
            metadata={"route": "levels/metadata.json"},
            links=[_scene_link("route", "levels/initial.json")],
        )
        active_key = manager.active_scene_key
        manager.load_scene(
            _scene_payload(
                name="Secondary",
                metadata={"route": "levels/metadata.json"},
                links=[_scene_link("route", "levels/initial.json")],
            ),
            source_path="secondary-empty.json",
            activate=False,
        )
        secondary = next(entry for entry in manager.list_open_scenes() if entry["name"] == "Secondary")
        empty_target_link = _scene_link("route", "")
        active_entry = manager.resolve_entry(active_key)
        secondary_entry = manager.resolve_entry(secondary["key"])

        self.assertEqual(
            active_entry.scene.feature_metadata["scene_flow"],
            secondary_entry.scene.feature_metadata["scene_flow"],
        )
        self.assertEqual(
            active_entry.scene.find_entity("Portal_0")["components"]["SceneLink"]["target_path"],
            secondary_entry.scene.find_entity("Portal_0")["components"]["SceneLink"]["target_path"],
        )

        self.assertTrue(
            manager.upsert_component_for_scene(
                active_key,
                "Portal_0",
                "SceneLink",
                empty_target_link,
            )
        )
        self.assertEqual(manager.get_scene_flow(), {})

        self.assertTrue(
            manager.upsert_component_for_scene(
                secondary["key"],
                "Portal_0",
                "SceneLink",
                empty_target_link,
            )
        )
        self.assertEqual(manager.active_scene_key, active_key)
        self.assertEqual(
            active_entry.scene.feature_metadata.get("scene_flow", {}),
            secondary_entry.scene.feature_metadata.get("scene_flow", {}),
        )
        self.assertEqual(active_entry.scene.feature_metadata.get("scene_flow", {}), {})
        self.assertTrue(next(entry for entry in manager.list_open_scenes() if entry["name"] == "FlowProbe")["has_invalid_links"])

        self.assertIsNotNone(manager.activate_scene(secondary["key"]))
        self.assertEqual(manager.get_scene_flow(), {})
        self.assertTrue(next(entry for entry in manager.list_open_scenes() if entry["name"] == "Secondary")["has_invalid_links"])


class SceneFlowPolicyTests(unittest.TestCase):
    def test_sync_removes_empty_scene_flow_and_preserves_unrelated_metadata(self) -> None:
        policy = SceneFlowPolicy()
        scene = Scene.from_dict(
            {
                **_scene_payload(links=[_scene_link("stale", "")]),
                "feature_metadata": {
                    "scene_flow": {"stale": "levels/stale.json"},
                    "signals": {"connections": []},
                },
            }
        )

        self.assertEqual(policy.sync_metadata_from_links(scene), {})
        self.assertNotIn("scene_flow", scene.feature_metadata)
        self.assertEqual(
            scene.feature_metadata["signals"],
            {"connections": []},
        )

    def test_metadata_lookup_does_not_serialize_scene(self) -> None:
        policy = SceneFlowPolicy()
        scene = Scene.from_dict(
            _scene_payload(
                metadata={"route": "levels/metadata.json"},
                links=[],
            )
        )

        with patch.object(scene, "to_dict", side_effect=AssertionError("scene serialization is forbidden")):
            prepared = policy.prepare_component(scene, _scene_link("route"))

        self.assertEqual(prepared["target_path"], "levels/metadata.json")

    def test_prepare_payload_completes_absent_target_but_preserves_explicit_empty(self) -> None:
        policy = SceneFlowPolicy()
        payload = _scene_payload(
            metadata={"route": "levels/metadata.json"},
            links=[_scene_link("route"), _scene_link("route", "")],
        )

        prepared = policy.prepare_payload(payload)
        links = [entity["components"]["SceneLink"] for entity in prepared["entities"]]

        self.assertEqual(links[0]["target_path"], "levels/metadata.json")
        self.assertEqual(links[1]["target_path"], "")

    def test_policy_uses_serialized_order_and_last_duplicate_wins(self) -> None:
        policy = SceneFlowPolicy()
        payload = policy.prepare_payload(
            _scene_payload(
                metadata={"route": "levels/metadata.json", "orphan": "levels/orphan.json"},
                links=[
                    _scene_link("route", "levels/first.json"),
                    _scene_link("route", "levels/last.json"),
                ],
            )
        )
        scene = Scene.from_dict(payload)

        self.assertEqual(
            policy.get_effective_flow(scene),
            {"route": "levels/last.json", "orphan": "levels/orphan.json"},
        )

        self.assertTrue(scene.replace_component_data("Portal_1", "SceneLink", _scene_link("route", "")))
        self.assertEqual(policy.sync_metadata_from_links(scene), {"orphan": "levels/orphan.json"})
        self.assertEqual(scene.feature_metadata["scene_flow"], {"orphan": "levels/orphan.json"})


if __name__ == "__main__":
    unittest.main()
