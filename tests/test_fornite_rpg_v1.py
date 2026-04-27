from __future__ import annotations

import importlib
import sys
import tempfile
import unittest
from pathlib import Path

from engine.api import EngineAPI


class ForniteRPGSharedTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.project_root = Path(__file__).resolve().parents[1] / "projects" / "Fornite"
        cls.scripts_dir = cls.project_root / "scripts"
        cls._original_sys_path = list(sys.path)
        if str(cls.scripts_dir) not in sys.path:
            sys.path.insert(0, str(cls.scripts_dir))
        cls.rpg_shared = importlib.import_module("rpg_shared")

    @classmethod
    def tearDownClass(cls) -> None:
        sys.path[:] = cls._original_sys_path

    def setUp(self) -> None:
        self.rpg_shared.reset_run_state()

    def test_enemy_catalog_has_five_expected_enemies(self) -> None:
        catalog = self.rpg_shared.ENEMY_CATALOG
        self.assertEqual(set(catalog.keys()), {"frog", "mummy", "ogre", "slime", "wizard"})
        for enemy_id, profile in catalog.items():
            self.assertEqual(profile["id"], enemy_id)
            self.assertTrue(profile["battle_frames"])
            self.assertGreater(profile["max_hp"], 0)
            self.assertTrue(profile["attack_pool"])

    def test_damage_respects_physical_and_magical_defenses(self) -> None:
        ogre = self.rpg_shared.ENEMY_CATALOG["ogre"]
        wizard = self.rpg_shared.ENEMY_CATALOG["wizard"]

        sword_vs_ogre = self.rpg_shared.compute_damage(30, ogre["physical_defense"])
        magic_vs_ogre = self.rpg_shared.compute_damage(30, ogre["magic_defense"])
        sword_vs_wizard = self.rpg_shared.compute_damage(30, wizard["physical_defense"])
        magic_vs_wizard = self.rpg_shared.compute_damage(30, wizard["magic_defense"])

        self.assertLess(sword_vs_ogre, magic_vs_ogre)
        self.assertGreater(sword_vs_wizard, magic_vs_wizard)

    def test_player_heal_and_mana_restore_clamp_to_maximums(self) -> None:
        enemy_profile = self.rpg_shared.ENEMY_CATALOG["slime"]
        enemy_state = {"hp": enemy_profile["max_hp"], "mp": 0}
        player_state = {"hp": 70, "mp": 55}

        self.rpg_shared.perform_player_action("curar", player_state, enemy_state, enemy_profile)
        self.assertEqual(player_state["hp"], 120)
        self.assertEqual(enemy_state["hp"], enemy_profile["max_hp"])

        player_state = {"hp": 120, "mp": 50}
        mana = self.rpg_shared.perform_player_action("curar_mana", player_state, enemy_state, enemy_profile)
        self.assertEqual(player_state["mp"], 60)
        self.assertGreaterEqual(mana["restored"], 0)

    def test_explosion_spends_mana_and_targets_magic_defense(self) -> None:
        enemy_profile = self.rpg_shared.ENEMY_CATALOG["mummy"]
        enemy_state = {"hp": enemy_profile["max_hp"], "mp": 0}
        player_state = {"hp": 120, "mp": 30}

        result = self.rpg_shared.perform_player_action("explosion", player_state, enemy_state, enemy_profile)

        self.assertEqual(player_state["mp"], 14)
        expected_damage = self.rpg_shared.compute_damage(
            self.rpg_shared.PLAYER_ACTIONS["explosion"]["power"],
            enemy_profile["magic_defense"],
        )
        self.assertEqual(result["damage"], expected_damage)
        self.assertEqual(enemy_state["hp"], enemy_profile["max_hp"] - expected_damage)

    def test_defeated_enemy_state_persists_in_run_state(self) -> None:
        self.rpg_shared.mark_enemy_defeated("frog")
        self.assertTrue(self.rpg_shared.is_enemy_defeated("frog"))
        self.assertFalse(self.rpg_shared.is_enemy_defeated("wizard"))

    def test_enemy_attacks_are_chosen_from_declared_pool(self) -> None:
        enemy_profile = self.rpg_shared.ENEMY_CATALOG["wizard"]
        samples = {self.rpg_shared.choose_enemy_attack(enemy_profile)["name"] for _ in range(20)}
        self.assertTrue(samples.issubset({attack["name"] for attack in enemy_profile["attack_pool"]}))
        self.assertTrue(samples)


class ForniteRPGSceneLoadTests(unittest.TestCase):
    def setUp(self) -> None:
        self.project_root = Path(__file__).resolve().parents[1] / "projects" / "Fornite"
        self._temp_dir = tempfile.TemporaryDirectory()
        self.global_state_dir = Path(self._temp_dir.name) / "global_state"
        self.api = EngineAPI(
            project_root=self.project_root.as_posix(),
            global_state_dir=self.global_state_dir.as_posix(),
            sandbox_paths=False,
        )

    def tearDown(self) -> None:
        self.api.shutdown()
        self._temp_dir.cleanup()

    def test_main_scene_loads_and_contains_expected_entities(self) -> None:
        self.api.load_level("levels/main_scene.json")
        self.assertEqual(self.api.get_active_scene()["name"], "Main Scene")
        self.assertEqual(self.api.get_entity("Player")["name"], "Player")
        self.assertEqual(self.api.get_entity("EnemyWizard")["name"], "EnemyWizard")
        self.assertEqual(self.api.get_entity("WorldDirector")["name"], "WorldDirector")

    def test_battle_scene_loads_and_exposes_expected_connections(self) -> None:
        self.api.load_level("levels/battle_scene.json")
        self.assertEqual(self.api.get_active_scene()["name"], "Battle Scene")
        self.assertEqual(self.api.get_entity("BattleDirector")["name"], "BattleDirector")
        self.assertEqual(self.api.get_entity("EnemyBattler")["name"], "EnemyBattler")
        self.assertEqual(self.api.get_entity("ActionExplosion")["name"], "ActionExplosion")
        self.assertEqual(self.api.get_scene_connections()["previous_scene"], "levels/main_scene.json")


if __name__ == "__main__":
    unittest.main()
