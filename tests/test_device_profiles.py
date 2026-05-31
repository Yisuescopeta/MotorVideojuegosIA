import unittest

from engine.utils.device_profiles import (
    FIT_PANEL_PROFILE_ID,
    get_device_profile,
    list_device_profiles,
    next_device_profile_id,
    resolve_preview_size,
    resolve_window_config,
)


class DeviceProfileTests(unittest.TestCase):
    def test_catalog_contains_expected_profiles(self) -> None:
        profile_ids = [profile.id for profile in list_device_profiles()]

        self.assertEqual(profile_ids[0], FIT_PANEL_PROFILE_ID)
        self.assertIn("mobile_portrait", profile_ids)
        self.assertIn("desktop_ultrawide", profile_ids)

    def test_unknown_profile_falls_back_to_fit_panel(self) -> None:
        profile = get_device_profile("unknown")

        self.assertEqual(profile.id, FIT_PANEL_PROFILE_ID)
        self.assertEqual(resolve_preview_size("unknown", 500, 300), (500, 300))

    def test_fixed_profile_resolves_preview_size(self) -> None:
        self.assertEqual(resolve_preview_size("mobile_portrait", 500, 300), (390, 844))

    def test_next_profile_cycles_from_fit_panel(self) -> None:
        self.assertEqual(next_device_profile_id(FIT_PANEL_PROFILE_ID), "mobile_portrait")

    def test_window_config_uses_device_profile_and_explicit_override(self) -> None:
        profile_window = resolve_window_config({"device_profile": "mobile_portrait"})
        override_window = resolve_window_config(
            {"device_profile": "mobile_portrait", "width": 800}
        )

        self.assertEqual(profile_window["width"], 390)
        self.assertEqual(profile_window["height"], 844)
        self.assertEqual(override_window["width"], 800)
        self.assertEqual(override_window["height"], 844)
        self.assertTrue(profile_window["resizable"])
        self.assertFalse(profile_window["fullscreen"])


if __name__ == "__main__":
    unittest.main()
