"""Pure-function tests for editor_qt.panels.animator_panel helpers.

No Qt widget required. Imports gracefully if PySide6 not installed.
"""

import unittest

try:
    import editor_qt.panels.animator_panel as a  # noqa: E402
except ImportError:
    a = None


class AnimatorPureFunctionTests(unittest.TestCase):
    @unittest.skipIf(a is None, "animator_panel unavailable")
    def test_detect_slice_sequences_finds_consecutive_numbered_slices(self) -> None:
        slices = ["player_0", "player_1", "player_2", "enemy_0", "enemy_1", "particle"]
        result = a.detect_slice_sequences(slices)

        self.assertEqual(len(result), 2)
        for seq in result:
            self.assertGreater(len(seq), 1)
            if seq[0].startswith("player"):
                self.assertEqual(seq, ["player_0", "player_1", "player_2"])
            elif seq[0].startswith("enemy"):
                self.assertEqual(seq, ["enemy_0", "enemy_1"])

    @unittest.skipIf(a is None, "animator_panel unavailable")
    def test_detect_slice_sequences_returns_empty_for_no_consecutive_groups(self) -> None:
        slices = ["a_0", "a_2", "a_4", "b_0", "c_0"]
        result = a.detect_slice_sequences(slices)

        self.assertEqual(result, [])

    @unittest.skipIf(a is None, "animator_panel unavailable")
    def test_detect_slice_sequences_sorts_by_largest_first(self) -> None:
        slices = ["small_0", "small_1", "big_0", "big_1", "big_2", "big_3"]
        result = a.detect_slice_sequences(slices)

        self.assertEqual(len(result), 2)
        self.assertEqual(len(result[0]), 4)
        self.assertEqual(len(result[1]), 2)

    @unittest.skipIf(a is None, "animator_panel unavailable")
    def test_detect_slice_groups_groups_by_prefix(self) -> None:
        slices = ["player_0", "player_1", "player_2", "enemy_0", "enemy_1"]
        result = a.detect_slice_groups(slices)

        self.assertEqual(len(result), 2)
        groups_by_name = {g["group_name"]: g for g in result}
        self.assertIn("player", groups_by_name)
        self.assertIn("enemy", groups_by_name)
        self.assertEqual(groups_by_name["player"]["slice_names"],
                         ["player_0", "player_1", "player_2"])
        self.assertEqual(groups_by_name["player"]["count"], 3)

    @unittest.skipIf(a is None, "animator_panel unavailable")
    def test_detect_slice_groups_ignores_singles(self) -> None:
        slices = ["run_0", "run_1", "lone_0"]
        result = a.detect_slice_groups(slices)

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["group_name"], "run")

    @unittest.skipIf(a is None, "animator_panel unavailable")
    def test_normalize_group_match_name_strips_trailing_state_number(self) -> None:
        self.assertEqual(a.normalize_group_match_name("player_1"), "player")
        self.assertEqual(a.normalize_group_match_name("enemy_0"), "enemy")
        self.assertEqual(a.normalize_group_match_name("walk_left"), "walk_left")
        self.assertEqual(a.normalize_group_match_name(""), "")
        self.assertEqual(a.normalize_group_match_name("_123"), "")

    @unittest.skipIf(a is None, "animator_panel unavailable")
    def test_get_recommended_slice_group_matches_normalized_name(self) -> None:
        groups = [
            {"group_name": "idle", "slice_names": ["idle_0", "idle_1"], "count": 2},
            {"group_name": "run", "slice_names": ["run_0", "run_1", "run_2"], "count": 3},
        ]
        result = a.get_recommended_slice_group("run_1", groups)

        self.assertIsNotNone(result)
        self.assertEqual(result["group_name"], "run")
        self.assertEqual(result["count"], 3)

    @unittest.skipIf(a is None, "animator_panel unavailable")
    def test_get_recommended_slice_group_returns_none_for_no_match(self) -> None:
        groups = [
            {"group_name": "idle", "slice_names": ["idle_0", "idle_1"], "count": 2},
        ]
        result = a.get_recommended_slice_group("jump", groups)

        self.assertIsNone(result)

    @unittest.skipIf(a is None, "animator_panel unavailable")
    def test_get_recommended_slice_group_returns_none_for_empty_name(self) -> None:
        groups = [{"group_name": "idle", "slice_names": ["idle_0"], "count": 1}]
        result = a.get_recommended_slice_group("", groups)

        self.assertIsNone(result)

    @unittest.skipIf(a is None, "animator_panel unavailable")
    def test_detect_slice_groups_handles_underscored_prefixes(self) -> None:
        slices = ["walk_left_0", "walk_left_1", "walk_left_2"]
        result = a.detect_slice_groups(slices)

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["group_name"], "walk_left")
        self.assertEqual(result[0]["count"], 3)


if __name__ == "__main__":
    unittest.main()
