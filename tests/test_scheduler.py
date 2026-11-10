import copy
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from wellness import config  # noqa: E402
from wellness.scheduler import Scheduler, MIN_GAP  # noqa: E402


def cfg(**over):
    c = copy.deepcopy(config.DEFAULTS)
    c.update(over)
    return c


def run(sched, start, end, step=15, **kw):
    """Tick from start to end; return list of (time, key)."""
    out = []
    t = start
    while t <= end:
        k = sched.tick(t, **kw)
        if k:
            out.append((t, k))
        t += step
    return out


class SchedulerTests(unittest.TestCase):
    def test_nothing_before_interval(self):
        s = Scheduler(cfg(), 0)
        self.assertIsNone(s.tick(10 * 60, False))

    def test_fires_after_interval_with_priority(self):
        c = cfg()
        c["eyes"]["minutes"] = c["stand"]["minutes"] = c["posture"]["minutes"] = 10
        s = Scheduler(c, 0)
        self.assertEqual(s.tick(600, False), "stand")
        self.assertIsNone(s.tick(610, False))      # min gap
        self.assertEqual(s.tick(661, False), "eyes")
        self.assertEqual(s.tick(722, False), "posture")
        self.assertIsNone(s.tick(783, False))

    def test_repeats(self):
        s = Scheduler(cfg(), 0)
        eyes = [t for t, k in run(s, 0, 61 * 60) if k == "eyes"]
        self.assertEqual(eyes, [20 * 60, 40 * 60, 60 * 60])

    def test_pause_resume(self):
        s = Scheduler(cfg(), 0)
        s.pause(100)
        self.assertEqual(run(s, 100, 5000), [])        # nothing while paused
        s.resume(5000)
        self.assertEqual(run(s, 5000, 5000 + 19 * 60), [])   # timers restarted
        self.assertEqual(run(s, 5000 + 19 * 60 + 15, 5000 + 21 * 60),
                         [(5000 + 20 * 60, "eyes")])

    def test_timed_pause_expires(self):
        s = Scheduler(cfg(), 0)
        s.pause(0, minutes=30)
        self.assertEqual(run(s, 0, 30 * 60), [])       # silent until it ends
        self.assertFalse(s.paused)                      # resumed on its own
        eyes = [t for t, k in run(s, 30 * 60 + 15, 60 * 60) if k == "eyes"]
        self.assertEqual(eyes, [50 * 60])               # 20 min after resuming

    def test_fullscreen_defers_then_fires(self):
        s = Scheduler(cfg(), 0)
        self.assertIsNone(s.tick(25 * 60, True))
        self.assertEqual(s.tick(25 * 60 + 15, False), "eyes")

    def test_fullscreen_ignored_when_disabled(self):
        s = Scheduler(cfg(skip_fullscreen=False), 0)
        self.assertEqual(s.tick(20 * 60, True), "eyes")

    def test_disabled_reminder(self):
        c = cfg()
        c["eyes"]["enabled"] = False
        s = Scheduler(c, 0)
        self.assertNotIn("eyes", s.next_due)

    def test_apply_config_keeps_unchanged_timers(self):
        s = Scheduler(cfg(), 0)
        c = cfg()
        c["eyes"]["minutes"] = 5
        s.apply_config(c, 100)
        self.assertEqual(s.next_due["eyes"], 100 + 300)
        self.assertEqual(s.next_due["stand"], 45 * 60)

    def test_reenabled_reminder_restarts(self):
        s = Scheduler(cfg(), 0)
        off = cfg(); off["eyes"]["enabled"] = False
        s.apply_config(off, 100)
        s.apply_config(cfg(), 500)
        self.assertEqual(s.next_due["eyes"], 500 + 20 * 60)

    def test_apply_config_while_paused_keeps_pause(self):
        s = Scheduler(cfg(), 0)
        s.pause(0)
        c = cfg(); c["eyes"]["minutes"] = 1
        s.apply_config(c, 10)
        self.assertTrue(s.paused)
        self.assertEqual(run(s, 15, 3600), [])

    # --- exact intervals / duplicates over a long run ---
    def test_intervals_exact_over_one_day(self):
        s = Scheduler(cfg(), 0)
        events = run(s, 0, 24 * 3600)
        for key, minutes in (("eyes", 20), ("stand", 45), ("posture", 30)):
            times = [t for t, k in events if k == key]
            self.assertGreater(len(times), 0)
            for a, b in zip(times, times[1:]):
                # interval + at most tick step + collision stagger
                self.assertGreaterEqual(b - a, minutes * 60)
                self.assertLessEqual(b - a, minutes * 60 + 3 * MIN_GAP)
        # never two notifications closer than MIN_GAP
        ts = [t for t, _ in events]
        self.assertTrue(all(b - a >= MIN_GAP for a, b in zip(ts, ts[1:])))

    def test_no_duplicate_same_tick(self):
        c = cfg()
        for k in ("eyes", "stand", "posture"):
            c[k]["minutes"] = 1
        s = Scheduler(c, 0)
        events = run(s, 0, 3600, step=15)
        ts = [t for t, _ in events]
        self.assertEqual(len(ts), len(set(ts)))
        self.assertTrue(all(b - a >= MIN_GAP for a, b in zip(ts, ts[1:])))

    # --- locked screen / sleep ---
    def test_locked_screen_resets_timers_on_return(self):
        s = Scheduler(cfg(), 0)
        self.assertEqual(run(s, 0, 19 * 60, away=False), [])
        self.assertEqual(run(s, 19 * 60 + 15, 3 * 3600, away=True), [])
        back = 3 * 3600 + 15
        self.assertIsNone(s.tick(back, away=False))        # no burst on unlock
        self.assertEqual(run(s, back + 15, back + 19 * 60), [])
        self.assertEqual(s.tick(back + 20 * 60, away=False), "eyes")

    def test_sleep_gap_resets_timers_without_burst(self):
        s = Scheduler(cfg(), 0)
        run(s, 0, 600)
        wake = 600 + 8 * 3600       # no ticks for 8 hours
        self.assertIsNone(s.tick(wake))
        self.assertEqual(run(s, wake + 15, wake + 19 * 60), [])
        self.assertEqual(s.tick(wake + 20 * 60), "eyes")

    def test_normal_tick_jitter_is_not_sleep(self):
        s = Scheduler(cfg(), 0)
        run(s, 0, 600)
        s.tick(600 + 100)           # one slow tick, under GAP_LIMIT
        evs = run(s, 700 + 10, 20 * 60 + 15, step=10)
        self.assertEqual(evs, [(20 * 60, "eyes")])      # original schedule kept

    def test_remaining(self):
        s = Scheduler(cfg(), 100)
        self.assertEqual(s.remaining(160)["eyes"], 20 * 60 - 60)


class ConfigTests(unittest.TestCase):
    def test_roundtrip_and_sanitize(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "c.json")
            config.save({"eyes": {"enabled": True, "minutes": 999}}, p)
            c = config.load(p)
            self.assertEqual(c["eyes"]["minutes"], 480)
            self.assertEqual(c["stand"]["minutes"], 45)

    def test_corrupt_file_falls_back(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "c.json")
            with open(p, "w") as f:
                f.write("{not json")
            self.assertEqual(config.load(p), config.DEFAULTS)

    def test_garbage_values_fall_back(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "c.json")
            config.save({"eyes": {"enabled": True, "minutes": "abc"},
                         "stand": {"enabled": False, "minutes": -5}}, p)
            c = config.load(p)
            self.assertEqual(c["eyes"]["minutes"], 20)
            self.assertEqual(c["stand"]["minutes"], 1)
            self.assertFalse(c["stand"]["enabled"])

    def test_v11_flags_default_and_persist(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "c.json")
            # an old (v1.0) config without the new keys keeps the panel at startup
            with open(p, "w") as f:
                f.write('{"eyes": {"enabled": true, "minutes": 10}}')
            c = config.load(p)
            self.assertTrue(c["show_panel_on_startup"])
            self.assertTrue(c["eye_break_sound"])
            self.assertNotIn("readable_notifications", c)
            # a legacy key in an old config.json is ignored, not an error
            config.save({"show_panel_on_startup": False, "readable_notifications": True,
                         "eye_break_sound": False}, p)
            c = config.load(p)
            self.assertFalse(c["show_panel_on_startup"])
            self.assertFalse(c["eye_break_sound"])
            self.assertNotIn("readable_notifications", c)

    def test_eye_break_timer(self):
        from wellness.eyebreak import EyeBreakTimer
        t = [100.0]
        tm = EyeBreakTimer(clock=lambda: t[0])
        self.assertEqual(tm.state, "idle")      # never starts by itself
        self.assertFalse(tm.poll())
        self.assertTrue(tm.start())
        self.assertFalse(tm.start())            # no overlapping timer
        t[0] += 19.9
        self.assertFalse(tm.poll())
        t[0] += 0.2
        self.assertTrue(tm.poll())              # sound cue fires once
        self.assertFalse(tm.poll())
        self.assertEqual(tm.state, "done")

    def test_eye_break_cancel_is_silent(self):
        from wellness.eyebreak import EyeBreakTimer
        t = [0.0]
        tm = EyeBreakTimer(clock=lambda: t[0])
        tm.start()
        t[0] += 5
        tm.cancel()
        t[0] += 60
        self.assertFalse(tm.poll())             # cancelled => never signals
        self.assertEqual(tm.state, "cancelled")

    def test_panel_wanted(self):
        on, off = {"show_panel_on_startup": True}, {"show_panel_on_startup": False}
        self.assertTrue(config.panel_wanted(on, True, None))
        self.assertTrue(config.panel_wanted(on, False, 5))
        self.assertFalse(config.panel_wanted(off, True, None))   # explicit startup
        self.assertFalse(config.panel_wanted(off, False, 30))    # legacy shortcut at login
        self.assertTrue(config.panel_wanted(off, False, 5000))   # manual, long after login
        self.assertTrue(config.panel_wanted(off, False, None))   # unknown => open

    def test_state_roundtrip(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "s.json")
            self.assertIsNone(config.read_state(p))
            config.write_state({"paused": True}, p)
            self.assertEqual(config.read_state(p), {"paused": True})


if __name__ == "__main__":
    unittest.main()

