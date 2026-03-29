import unittest

from engine.ecs.entity import Entity
from engine.systems.physics_system import PhysicsSystem


class PhysicsSystemTests(unittest.TestCase):
    def test_record_swept_contact_deduplicates_pairs_while_preserving_first_seen_order(self) -> None:
        physics_system = PhysicsSystem()
        entity_a = Entity("A")
        entity_b = Entity("B")
        entity_c = Entity("C")

        physics_system._record_swept_contact(entity_a, entity_b)
        physics_system._record_swept_contact(entity_b, entity_a)
        physics_system._record_swept_contact(entity_a, entity_c)

        self.assertEqual(
            physics_system.consume_swept_contacts(),
            [
                tuple(sorted((entity_a.id, entity_b.id))),
                tuple(sorted((entity_a.id, entity_c.id))),
            ],
        )


if __name__ == "__main__":
    unittest.main()
