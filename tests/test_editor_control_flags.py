from __future__ import annotations

import os
import unittest

from engine.editor.editor_control_flags import (
    EditorControlFeatureFlagManager,
    EditorControlFeatureFlags,
    _coerce_bool,
    _env_bool,
    default_editor_control_feature_flags,
    editor_control_feature_env_overrides,
    editor_control_feature_flag_names,
    editor_control_feature_flags_from_preferences,
    editor_control_feature_flags_to_dict,
)


class CoerceBoolTests(unittest.TestCase):
    def test_bool_true_passes_through(self) -> None:
        self.assertTrue(_coerce_bool(True))

    def test_bool_false_passes_through(self) -> None:
        self.assertFalse(_coerce_bool(False))

    def test_string_true_values(self) -> None:
        for val in ("1", "true", "yes", "on", "  true  ", "YES", "ON"):
            self.assertTrue(_coerce_bool(val), f"Expected True for {val!r}")

    def test_string_false_values(self) -> None:
        for val in ("0", "false", "no", "off", "  FALSE  ", "NO"):
            self.assertFalse(_coerce_bool(val), f"Expected False for {val!r}")

    def test_unknown_returns_default(self) -> None:
        self.assertFalse(_coerce_bool("unknown"))
        self.assertTrue(_coerce_bool("unknown", default=True))

    def test_int_zero_returns_default(self) -> None:
        self.assertFalse(_coerce_bool(0))
        self.assertTrue(_coerce_bool(0, default=True))

    def test_none_returns_default(self) -> None:
        self.assertFalse(_coerce_bool(None))
        self.assertTrue(_coerce_bool(None, default=True))


class EnvBoolTests(unittest.TestCase):
    def setUp(self) -> None:
        self._saved: dict[str, str] = {}
        for var in ("MOTOR_EDITOR_CONTROL_CONSOLE", "MOTOR_TEST_UNSET"):
            if var in os.environ:
                self._saved[var] = os.environ[var]
                del os.environ[var]

    def tearDown(self) -> None:
        for var in ("MOTOR_EDITOR_CONTROL_CONSOLE", "MOTOR_TEST_UNSET"):
            if var in os.environ:
                del os.environ[var]
            if var in self._saved:
                os.environ[var] = self._saved[var]

    def test_unset_env_returns_default(self) -> None:
        self.assertFalse(_env_bool("MOTOR_TEST_UNSET"))
        self.assertTrue(_env_bool("MOTOR_TEST_UNSET", default=True))

    def test_env_set_true_returns_true(self) -> None:
        os.environ["MOTOR_TEST_UNSET"] = "1"
        self.assertTrue(_env_bool("MOTOR_TEST_UNSET"))
        os.environ["MOTOR_TEST_UNSET"] = "true"
        self.assertTrue(_env_bool("MOTOR_TEST_UNSET"))
        os.environ["MOTOR_TEST_UNSET"] = "YES"
        self.assertTrue(_env_bool("MOTOR_TEST_UNSET"))

    def test_env_set_false_returns_false(self) -> None:
        os.environ["MOTOR_EDITOR_CONTROL_CONSOLE"] = "0"
        self.assertFalse(_env_bool("MOTOR_EDITOR_CONTROL_CONSOLE"))
        os.environ["MOTOR_EDITOR_CONTROL_CONSOLE"] = "false"
        self.assertFalse(_env_bool("MOTOR_EDITOR_CONTROL_CONSOLE"))


class DefaultFlagsTests(unittest.TestCase):
    def test_default_flags_all_false(self) -> None:
        flags = default_editor_control_feature_flags()
        self.assertFalse(flags.console_panel)
        self.assertFalse(flags.asset_browser)
        self.assertFalse(flags.popup_controls)

    def test_flag_names_known_set(self) -> None:
        names = editor_control_feature_flag_names()
        self.assertIn("console_panel", names)
        self.assertIn("asset_browser", names)
        self.assertIn("popup_controls", names)


class FlagsFromPreferencesTests(unittest.TestCase):
    def test_empty_prefs_yields_defaults(self) -> None:
        flags = editor_control_feature_flags_from_preferences({})
        self.assertFalse(flags.console_panel)

    def test_none_prefs_yields_defaults(self) -> None:
        flags = editor_control_feature_flags_from_preferences(None)
        self.assertFalse(flags.console_panel)

    def test_prefs_enable_console(self) -> None:
        prefs = {"editor_feature_flags": {"console_panel": True}}
        flags = editor_control_feature_flags_from_preferences(prefs)
        self.assertTrue(flags.console_panel)
        self.assertFalse(flags.asset_browser)

    def test_prefs_with_string_values(self) -> None:
        prefs = {"editor_feature_flags": {"console_panel": "1", "asset_browser": "true"}}
        flags = editor_control_feature_flags_from_preferences(prefs)
        self.assertTrue(flags.console_panel)
        self.assertTrue(flags.asset_browser)
        self.assertFalse(flags.popup_controls)

    def test_unknown_key_ignored(self) -> None:
        prefs = {"editor_feature_flags": {"unknown_flag": True}}
        flags = editor_control_feature_flags_from_preferences(prefs)
        self.assertFalse(flags.console_panel)


class EnvOverrideTests(unittest.TestCase):
    def setUp(self) -> None:
        self._saved: dict[str, str] = {}
        for var in ("MOTOR_EDITOR_CONTROL_CONSOLE", "MOTOR_EDITOR_CONTROL_ASSET_BROWSER", "MOTOR_EDITOR_CONTROL_POPUP"):
            if var in os.environ:
                self._saved[var] = os.environ[var]
                del os.environ[var]

    def tearDown(self) -> None:
        for var in ("MOTOR_EDITOR_CONTROL_CONSOLE", "MOTOR_EDITOR_CONTROL_ASSET_BROWSER", "MOTOR_EDITOR_CONTROL_POPUP"):
            if var in os.environ:
                del os.environ[var]
            if var in self._saved:
                os.environ[var] = self._saved[var]

    def test_env_override_wins_over_prefs(self) -> None:
        os.environ["MOTOR_EDITOR_CONTROL_CONSOLE"] = "1"
        prefs = {"editor_feature_flags": {"console_panel": False}}
        flags = editor_control_feature_flags_from_preferences(prefs)
        self.assertTrue(flags.console_panel)

    def test_env_override_not_set_when_env_missing(self) -> None:
        overrides = editor_control_feature_env_overrides()
        self.assertNotIn("console_panel", overrides)

    def test_env_override_set_when_env_present(self) -> None:
        os.environ["MOTOR_EDITOR_CONTROL_CONSOLE"] = "1"
        overrides = editor_control_feature_env_overrides()
        self.assertIn("console_panel", overrides)
        self.assertEqual(overrides["console_panel"], "MOTOR_EDITOR_CONTROL_CONSOLE")


class FlagsToDictTests(unittest.TestCase):
    def test_all_false_roundtrip(self) -> None:
        flags = EditorControlFeatureFlags()
        d = editor_control_feature_flags_to_dict(flags)
        self.assertEqual(d, {"console_panel": False, "asset_browser": False, "popup_controls": False})

    def test_mixed_roundtrip(self) -> None:
        flags = EditorControlFeatureFlags(console_panel=True, popup_controls=True)
        d = editor_control_feature_flags_to_dict(flags)
        self.assertTrue(d["console_panel"])
        self.assertFalse(d["asset_browser"])
        self.assertTrue(d["popup_controls"])


class FeatureFlagManagerTests(unittest.TestCase):
    def test_from_preferences_creates_manager(self) -> None:
        mgr = EditorControlFeatureFlagManager.from_preferences(None)
        self.assertFalse(mgr.flags.console_panel)

    def test_from_preferences_with_data(self) -> None:
        prefs = {"editor_feature_flags": {"console_panel": True}}
        mgr = EditorControlFeatureFlagManager.from_preferences(prefs)
        self.assertTrue(mgr.flags.console_panel)

    def test_apply_preferences_updates_flags(self) -> None:
        mgr = EditorControlFeatureFlagManager()
        self.assertFalse(mgr.flags.console_panel)
        prefs = {"editor_feature_flags": {"console_panel": True}}
        mgr.apply_preferences(prefs)
        self.assertTrue(mgr.flags.console_panel)

    def test_update_partial(self) -> None:
        mgr = EditorControlFeatureFlagManager()
        mgr.update({"console_panel": True})
        self.assertTrue(mgr.flags.console_panel)
        self.assertFalse(mgr.flags.asset_browser)

    def test_update_with_string_values(self) -> None:
        mgr = EditorControlFeatureFlagManager()
        mgr.update({"asset_browser": "1"})
        self.assertTrue(mgr.flags.asset_browser)

    def test_update_unknown_key_no_effect(self) -> None:
        mgr = EditorControlFeatureFlagManager()
        before = editor_control_feature_flags_to_dict(mgr.flags)
        mgr.update({"unknown_key": True})
        self.assertEqual(editor_control_feature_flags_to_dict(mgr.flags), before)


if __name__ == "__main__":
    unittest.main()
