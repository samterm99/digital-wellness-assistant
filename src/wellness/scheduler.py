"""Pure reminder scheduling logic (no Windows calls, easy to test).

Times are plain seconds (e.g. time.monotonic()).
"""

PRIORITY = ("stand", "eyes", "posture")
MIN_GAP = 60      # seconds between two notifications
GAP_LIMIT = 120   # a silence between ticks longer than this = computer slept


class Scheduler:
    def __init__(self, cfg, now, gap_limit=GAP_LIMIT):
        self.gap_limit = gap_limit
        self.next_due = {}
        self.paused = False
        self.paused_until = None  # None = paused indefinitely
        self.last_shown = None
        self.last_tick = None
        self._away = False
        self.apply_config(cfg, now)

    def apply_config(self, cfg, now):
        """Keep timers of unchanged reminders; reset changed/new ones."""
        old = getattr(self, "_intervals", {})
        self._intervals = {
            k: cfg[k]["minutes"] * 60 for k in PRIORITY if cfg[k]["enabled"]
        }
        self.skip_fullscreen = cfg["skip_fullscreen"]
        self.next_due = {
            k: (self.next_due[k] if old.get(k) == v and k in self.next_due
                else now + v)
            for k, v in self._intervals.items()
        }

    def _reset(self, now):
        self.next_due = {k: now + v for k, v in self._intervals.items()}

    def pause(self, now, minutes=None):
        self.paused = True
        self.paused_until = None if minutes is None else now + minutes * 60

    def resume(self, now):
        self.paused = False
        self.paused_until = None
        self._reset(now)

    def remaining(self, now):
        """Seconds until each enabled reminder is due (negative = overdue)."""
        return {k: v - now for k, v in self.next_due.items()}

    def tick(self, now, busy=False, away=False):
        """Return the reminder key to show now, or None.

        busy: full-screen / game / presentation (reminder is deferred).
        away: screen locked / screensaver (user is resting; timers restart on return).
        """
        slept = self.last_tick is not None and now - self.last_tick > self.gap_limit
        self.last_tick = now
        if away or slept:
            self._away = True
        if away:
            return None
        if self._away:
            self._away = False
            self._reset(now)
        if self.paused:
            if self.paused_until is not None and now >= self.paused_until:
                self.resume(now)
            return None
        if busy and self.skip_fullscreen:
            return None  # stay due; shown soon after the busy state ends
        if self.last_shown is not None and now - self.last_shown < MIN_GAP:
            return None
        # Most overdue first; PRIORITY only breaks ties. Plain priority order let a
        # reminder whose interval is <= MIN_GAP starve the lower ones forever.
        due = [k for k in PRIORITY if k in self.next_due and now >= self.next_due[k]]
        if due:
            key = min(due, key=lambda k: self.next_due[k])  # min() keeps PRIORITY on ties
            self.next_due[key] = now + self._intervals[key]
            self.last_shown = now
            return key
        return None
