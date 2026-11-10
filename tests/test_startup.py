import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from wellness import __main__ as entry  # noqa: E402
from wellness import config, control  # noqa: E402

OFF = dict(config.DEFAULTS, show_panel_on_startup=False)


def panel_opened(args, cfg, since):
    with mock.patch.object(config, "load", return_value=cfg), \
         mock.patch.object(control, "seconds_since_logon", return_value=since), \
         mock.patch("wellness.panel.main") as panel:
        entry._auto_panel(args)
    return panel.called


class AutoPanelTest(unittest.TestCase):
    def test_startup_shortcut_respects_option(self):
        self.assertFalse(panel_opened(["--launch", "--startup"], OFF, 5))
        self.assertTrue(panel_opened(["--launch", "--startup"], config.DEFAULTS, 5))

    def test_manual_launch_right_after_login_shows_panel(self):
        # Desktop / Start Menu shortcut (--launch only) is never treated as a login start
        self.assertTrue(panel_opened(["--launch"], OFF, 5))

    def test_legacy_auto_panel_keeps_logon_fallback(self):
        self.assertFalse(panel_opened(["--auto-panel"], OFF, 5))
        self.assertTrue(panel_opened(["--auto-panel"], OFF, 5000))

    def test_packaged_start_uses_logon_fallback(self):
        # MSIX: Start tile and start-up task both run with no flags (--packaged)
        self.assertFalse(panel_opened(["--launch", "--packaged"], OFF, 5))
        self.assertTrue(panel_opened(["--launch", "--packaged"], OFF, 5000))
        self.assertTrue(panel_opened(["--launch", "--packaged"], config.DEFAULTS, 5))


if __name__ == "__main__":
    unittest.main()
