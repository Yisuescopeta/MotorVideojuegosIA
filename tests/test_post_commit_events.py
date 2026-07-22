import unittest

from engine.editor.hierarchy_query_cache import HierarchyQueryCache
from engine.editor.hierarchy_queries import HierarchyQueries
from engine.levels.component_registry import create_default_registry
from engine.scenes.post_commit import DomainEvent, ScenePostCommitEventPublisher
from engine.scenes.refs import EntityRef, OpenDocumentId, OpenSceneRef
from engine.scenes.scene_manager import SceneManager


def _payload() -> dict[str, object]:
    return {
        "name": "Post Commit",
        "entities": [
            {
                "id": "hero-id",
                "name": "Hero",
                "active": True,
                "tag": "Untagged",
                "layer": "Default",
                "components": {},
            }
        ],
        "rules": [],
        "feature_metadata": {},
    }


class PostCommitEventTests(unittest.TestCase):
    def test_publisher_is_typed_and_subscriber_failure_does_not_rewrite_event(self) -> None:
        publisher = ScenePostCommitEventPublisher()
        received: list[DomainEvent] = []
        publisher.subscribe(received.append)
        publisher.subscribe(lambda _event: (_ for _ in ()).throw(RuntimeError("observer")))
        scene = OpenSceneRef(OpenDocumentId.new())
        event = DomainEvent(
            scene=scene,
            scene_revision=3,
            label="Hero.tag",
            changed_entities=(EntityRef(scene, "hero-id"),),
        )

        publisher.publish(event)

        self.assertEqual(publisher.events, (event,))
        self.assertEqual(received, [event])
        self.assertEqual(event.kind, "scene_committed")

    def test_scene_commit_publishes_after_success_and_invalidates_hierarchy_cache(self) -> None:
        manager = SceneManager(create_default_registry())
        manager.load_scene(_payload())
        entry = manager._workspace.get_active_entry()
        assert entry is not None
        events: list[DomainEvent] = []
        manager.post_commit_events.subscribe(events.append)

        cache = HierarchyQueryCache(manager.post_commit_events)
        first_query = HierarchyQueries(entry.scene, entry.open_scene_ref)
        first = cache.snapshot(first_query)
        self.assertIs(first, cache.snapshot(first_query))

        self.assertTrue(manager.update_entity_property_by_id("hero-id", "tag", "Player"))

        self.assertEqual(len(events), 1)
        event = events[0]
        self.assertEqual(event.scene, entry.open_scene_ref)
        self.assertEqual(event.label, "Hero.tag")
        self.assertEqual(
            event.changed_entities,
            (EntityRef(entry.open_scene_ref, "hero-id"),),
        )
        self.assertEqual(cache.invalidation_count, 1)

        second_query = HierarchyQueries(entry.scene, entry.open_scene_ref)
        second = cache.snapshot(second_query)
        self.assertIsNot(first, second)
        self.assertEqual(second.scene_revision, entry.scene.revision)

    def test_rejected_mutation_does_not_publish(self) -> None:
        manager = SceneManager(create_default_registry())
        manager.load_scene(_payload())
        events: list[DomainEvent] = []
        manager.post_commit_events.subscribe(events.append)

        self.assertFalse(manager.update_entity_property_by_id("missing-id", "tag", "Player"))

        self.assertEqual(events, [])


if __name__ == "__main__":
    unittest.main()
