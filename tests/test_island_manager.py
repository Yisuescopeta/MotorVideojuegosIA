"""Tests para IslandBuilder2D — construccion de islas fisicas por BFS."""
import unittest

from engine.physics.contact_solver import ContactConstraint2D
from engine.physics.island_manager import Island2D, IslandBuilder2D


def _make_constraint(a_id: int, b_id: int) -> ContactConstraint2D:
    """Helper: crea un constraint de contacto simple entre dos cuerpos."""
    return ContactConstraint2D(
        entity_a_id=a_id, entity_b_id=b_id,
        normal_x=0.0, normal_y=1.0,
        tangent_x=-1.0, tangent_y=0.0,
        depth=0.5, mass_normal=1.0, mass_tangent=1.0,
        restitution=0.0, friction=1.0, bias=0.0,
    )


class TestIslandBuilder2D_BFS(unittest.TestCase):
    """Tests de conectividad BFS para construccion de islas."""

    def test_single_body_no_constraints(self):
        """1 cuerpo sin constraints ni joints — 1 isla, 0 constraints."""
        islands = IslandBuilder2D.build_islands([], [], {1})
        self.assertEqual(len(islands), 1)
        self.assertEqual(islands[0].body_ids, {1})
        self.assertEqual(len(islands[0].constraints), 0)

    def test_two_bodies_with_contact(self):
        """2 cuerpos con 1 constraint — 1 isla con ambos cuerpos."""
        c = _make_constraint(1, 2)
        islands = IslandBuilder2D.build_islands([c], [], {1, 2})
        self.assertEqual(len(islands), 1)
        self.assertEqual(islands[0].body_ids, {1, 2})
        self.assertEqual(len(islands[0].constraints), 1)

    def test_two_disjoint_pairs(self):
        """4 cuerpos en 2 pares sin conexion — 2 islas."""
        c1 = _make_constraint(1, 2)
        c2 = _make_constraint(3, 4)
        islands = IslandBuilder2D.build_islands([c1, c2], [], {1, 2, 3, 4})
        self.assertEqual(len(islands), 2)
        ids_0 = islands[0].body_ids
        ids_1 = islands[1].body_ids
        self.assertTrue(ids_0 == {1, 2} or ids_0 == {3, 4})
        self.assertTrue(ids_1 == {1, 2} or ids_1 == {3, 4})
        self.assertNotEqual(ids_0, ids_1)

    def test_chain_of_three_bodies(self):
        """A—B—C conectados por constraints — 1 isla."""
        c1 = _make_constraint(1, 2)
        c2 = _make_constraint(2, 3)
        islands = IslandBuilder2D.build_islands([c1, c2], [], {1, 2, 3})
        self.assertEqual(len(islands), 1)
        self.assertEqual(islands[0].body_ids, {1, 2, 3})
        self.assertEqual(len(islands[0].constraints), 2)

    def test_joint_connects_bodies(self):
        """A y B sin contacts pero con joint — 1 isla."""
        islands = IslandBuilder2D.build_islands([], [(1, 2)], {1, 2})
        self.assertEqual(len(islands), 1)
        self.assertEqual(islands[0].body_ids, {1, 2})
        self.assertEqual(len(islands[0].constraints), 0)

    def test_mixed_contacts_and_joints(self):
        """Grafo con contactos y joints mezclados — 1 isla conectada."""
        c1 = _make_constraint(1, 2)
        # 2 y 3 conectados por joint
        c2 = _make_constraint(3, 4)
        # Todo: 1-2-3-4 deberia ser una isla
        islands = IslandBuilder2D.build_islands([c1, c2], [(2, 3)], {1, 2, 3, 4})
        self.assertEqual(len(islands), 1)
        self.assertEqual(islands[0].body_ids, {1, 2, 3, 4})

    def test_empty_input(self):
        """Sin constraints, joints ni bodies — lista vacia."""
        islands = IslandBuilder2D.build_islands([], [], set())
        self.assertEqual(len(islands), 0)

    def test_bodies_without_any_connection(self):
        """3 cuerpos sueltos — 3 islas de 1 cuerpo."""
        islands = IslandBuilder2D.build_islands([], [], {10, 20, 30})
        self.assertEqual(len(islands), 3)
        all_ids = set()
        for island in islands:
            self.assertEqual(len(island.body_ids), 1)
            all_ids.update(island.body_ids)
        self.assertEqual(all_ids, {10, 20, 30})

    def test_bodies_not_in_all_body_ids_still_included(self):
        """Bodies en constraints pero no en all_body_ids se incluyen igual."""
        c = _make_constraint(5, 6)
        # all_body_ids vacio — los bodies de los constraints se agregan
        islands = IslandBuilder2D.build_islands([c], [], set())
        self.assertEqual(len(islands), 1)
        self.assertIn(5, islands[0].body_ids)
        self.assertIn(6, islands[0].body_ids)

    def test_island_size_property(self):
        """size y constraint_count propiedades son correctas."""
        island = Island2D(body_ids={1, 2, 3}, constraints=[_make_constraint(1, 2)])
        self.assertEqual(island.size, 3)
        self.assertEqual(island.constraint_count, 1)

    def test_island_sleeping_defaults(self):
        """Isla recien creada no esta dormida."""
        island = Island2D()
        self.assertFalse(island.sleeping)
        self.assertEqual(island.sleep_timer, 0.0)


if __name__ == "__main__":
    unittest.main()
