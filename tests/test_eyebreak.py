import copy
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from wellness import config  # noqa: E402
from wellness import eyebreak, tray_app  # noqa: E402
from wellness.eyebreak import EyeBreakTimer, Session  # noqa: E402
from wellness.scheduler import Scheduler  # noqa: E402


def session(auto=True, sound=True):
    t = [0.0]
    sounds, closed = [], []
    tm = EyeBreakTimer(clock=lambda: t[0], offer_timeout=eyebreak.OFFER_TIMEOUT if auto else None)
    s = Session(tm, sound, lambda: sounds.append(1), lambda: closed.append(1))
    return s, t, sounds, closed


def cfg(**over):
    c = copy.deepcopy(config.DEFAULTS)
    c.update(over)
    return c


def fake_tray(running=False):
    """TrayApp without Win32 setup, spawn_module replaced by a recorder."""
    app = object.__new__(tray_app.TrayApp)
    app._eyebreak = mock.Mock(poll=lambda: None) if running else None
    app.notify = mock.Mock()
    app._now = lambda: 0.0
    return app


class ReminderWindowTests(unittest.TestCase):
    def test_texts(self):
        self.assertEqual(eyebreak.TITLE, "ถึงเวลาพักสายตา")
        self.assertEqual(eyebreak.WINDOW_TITLE, "ผู้ช่วยสุขภาพดิจิทัล")
        self.assertEqual(eyebreak.INSTRUCTION, "มองไกลประมาณ 6 เมตร เป็นเวลา 20 วินาที")

    def test_place_stays_inside_work_area(self):
        area = (0, 0, 1920, 1032)                      # taskbar excluded (1080 - 48)
        x, y, h = eyebreak.place(360, 300, area)
        self.assertEqual((x, y + h), (1920 - 360 - 16, 1032 - 16))
        for scale_h in (200, 300, 420, 5000):          # reminder / countdown / huge (high DPI)
            x, y, h = eyebreak.place(450, scale_h, area)
            self.assertTrue(x >= 0 and y >= 0 and y + h <= 1032 - 16 and x + 450 <= 1920 - 16)
        x, y, h = eyebreak.place(360, 300, (1920, 0, 3840, 1000))  # work area not at origin
        self.assertGreaterEqual(x, 1920)

    def test_place_counts_title_bar_and_borders(self):
        area = (0, 0, 1368, 864)                       # e.g. Surface Pro work area
        frame = (16, 39)
        for h in (200, 330, 5000):
            x, y, h2 = eyebreak.place(360, h, area, frame=frame)
            self.assertLessEqual(y + frame[1] + h2, 864 - 16)    # outer bottom above margin
            self.assertLessEqual(x + 360 + frame[0], 1368 - 16)
            self.assertGreaterEqual(y, 0)
        x, y, h2 = eyebreak.place(360, 300, area, frame=frame)
        self.assertEqual(y + frame[1] + h2, 864 - 16)

    def test_countdown_not_automatic(self):
        s, t, sounds, closed = session()
        t[0] = 10
        s.step()
        self.assertEqual(s.timer.state, "idle")
        self.assertEqual(s.timer.remaining(), 20.0)

    def test_start_runs_20_seconds(self):
        s, t, sounds, closed = session()
        s.on_start()
        t[0] += 19.5
        self.assertAlmostEqual(s.step(), 0.5)
        self.assertEqual(closed, [])
        t[0] += 0.6
        s.step()
        self.assertEqual(closed, [1])

    def test_skip_closes_silently(self):
        s, t, sounds, closed = session()
        s.on_skip()
        t[0] = 100
        s.step()
        self.assertEqual((closed, sounds), ([1], []))

    def test_no_response_closes_after_15s(self):
        s, t, sounds, closed = session()
        t[0] = 14.9
        s.step()
        self.assertEqual(closed, [])
        t[0] = 15.0
        s.step()
        self.assertEqual((closed, sounds), ([1], []))

    def test_manual_has_no_timeout(self):
        s, t, sounds, closed = session(auto=False)
        t[0] = 3600
        s.step()
        self.assertEqual(closed, [])

    def test_timeout_cannot_interrupt_countdown(self):
        s, t, sounds, closed = session()
        t[0] = 14
        s.on_start()
        t[0] = 16
        s.step()
        t[0] = 30
        s.step()
        self.assertEqual(closed, [])
        t[0] = 34.1
        s.step()
        self.assertEqual((closed, sounds), ([1], [1]))

    def test_cancel_no_sound(self):
        s, t, sounds, closed = session()
        s.on_start()
        t[0] += 5
        s.on_cancel()
        t[0] += 60
        s.step()
        self.assertEqual((closed, sounds), ([1], []))

    def test_one_sound_only(self):
        s, t, sounds, closed = session()
        s.on_start()
        s.on_start()                     # repeated Start must not restart
        t[0] += 21
        for _ in range(5):
            s.step()
        self.assertEqual(sounds, [1])

    def test_sound_disabled(self):
        s, t, sounds, closed = session(sound=False)
        s.on_start()
        t[0] += 21
        s.step()
        self.assertEqual((closed, sounds), ([1], []))

    def test_x_acts_as_skip_or_cancel(self):
        s, *_ = session()
        s.on_x()
        self.assertEqual(s.timer.state, "skipped")
        s, *_ = session()
        s.on_start()
        s.on_x()
        self.assertEqual(s.timer.state, "cancelled")


class TrayIntegrationTests(unittest.TestCase):
    def test_scheduled_eyes_opens_interactive_window_only(self):
        app = fake_tray()
        with mock.patch.object(tray_app, "spawn_module") as sp, \
                mock.patch.object(tray_app, "HEADLESS", False):
            app._dispatch("eyes")
        sp.assert_called_once_with("wellness", "--eyebreak", "--auto")
        app.notify.assert_not_called()            # no old balloon as well

    def test_duplicate_event_no_second_window(self):
        app = fake_tray(running=True)
        with mock.patch.object(tray_app, "spawn_module") as sp, \
                mock.patch.object(tray_app, "HEADLESS", False):
            app._dispatch("eyes")
        sp.assert_not_called()

    def test_manual_launch_has_no_auto_flag(self):
        app = fake_tray()
        with mock.patch.object(tray_app, "spawn_module") as sp:
            app._start_eye_break()
        sp.assert_called_once_with("wellness", "--eyebreak")

    def test_posture_and_walking_still_use_notifications(self):
        for key in ("posture", "stand"):
            app = fake_tray()
            with mock.patch.object(tray_app, "spawn_module") as sp:
                app._dispatch(key)
            app.notify.assert_called_once_with(*config.MESSAGES[key])
            sp.assert_not_called()


class PackagedModeTests(unittest.TestCase):
    def test_frozen_spawn_uses_exe_not_python(self):
        with mock.patch.object(config, "FROZEN", True), \
                mock.patch.object(tray_app.subprocess, "Popen") as po:
            tray_app.spawn_module("wellness", "--eyebreak", "--auto")
        self.assertEqual(po.call_args[0][0], [sys.executable, "--eyebreak", "--auto"])

    def test_dev_spawn_unchanged(self):
        with mock.patch.object(config, "FROZEN", False), \
                mock.patch.object(tray_app.subprocess, "Popen") as po:
            tray_app.spawn_module("wellness", "--panel")
        cmd = po.call_args[0][0]
        self.assertEqual(cmd[1:], ["-m", "wellness", "--panel"])

    def test_save_creates_missing_data_dir(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "new", "config.json")
            config.save({}, p)
            self.assertEqual(config.load(p), config.DEFAULTS)


class SchedulingTests(unittest.TestCase):
    def test_fullscreen_suppresses_eyes_window(self):
        s = Scheduler(cfg(), 0)
        self.assertIsNone(s.tick(20 * 60, busy=True))      # nothing to open
        s2 = Scheduler(cfg(skip_fullscreen=False), 0)
        self.assertEqual(s2.tick(20 * 60, busy=True), "eyes")

    def test_pause_prevents_scheduled_window(self):
        for minutes in (None, 30, 60):
            s = Scheduler(cfg(), 0)
            s.pause(0, minutes)
            self.assertIsNone(s.tick(20 * 60 + 15))

    def test_simultaneous_eyes_and_posture_both_advance(self):
        """Regression: posture (1 min) starved by eyes (1 min) -> stuck 'overdue'."""
        c = cfg()
        c["eyes"]["minutes"] = c["posture"]["minutes"] = 1
        s = Scheduler(c, 0)
        fired = []
        for t in range(0, 1201, 15):
            k = s.tick(t)
            if k:
                fired.append(k)
        self.assertGreater(fired.count("posture"), 3)
        self.assertGreater(fired.count("eyes"), 3)
        for r in s.remaining(1200).values():
            self.assertGreater(r, -150)                    # nothing left permanently overdue

    def test_all_three_due_together_all_advance(self):
        c = cfg()
        for k in ("eyes", "stand", "posture"):
            c[k]["minutes"] = 10
        s = Scheduler(c, 0)
        got = [k for t in range(600, 1000, 15) if (k := s.tick(t))]
        self.assertEqual(sorted(got), ["eyes", "posture", "stand"])   # one each, no burst


if __name__ == "__main__":
    unittest.main()
