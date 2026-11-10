"""Accelerated long-run test: ~100 hours of reminder time in ~5 minutes.

Run:  python tests/soak.py [real_seconds]
"""
import os
import re
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(__file__))
import live_integration as li  # noqa: E402  (sets up a temp DW_HOME and helpers)

SCALE, TICK_MS = 1200, 50   # 1 real second = 20 reminder-minutes; one tick = 60 reminder-seconds


def main():
    secs = int(sys.argv[1]) if len(sys.argv) > 1 else 300
    li.config.save({"eyes": {"enabled": True, "minutes": 20},
                    "stand": {"enabled": True, "minutes": 45},
                    "posture": {"enabled": True, "minutes": 30},
                    "skip_fullscreen": True})
    env = dict(os.environ, DW_TIME_SCALE=str(SCALE), DW_TICK_MS=str(TICK_MS))
    app = subprocess.Popen([sys.executable, "-m", "wellness"], cwd=str(li.ROOT), env=env,
                           creationflags=0x08000000)
    ok = True
    try:
        li.wait_until(li.control.is_running, 10)
        time.sleep(5)
        s0 = li.sample(app.pid)
        samples = [s0]
        for i in range(4):
            time.sleep((secs - 5) / 4)
            samples.append(li.sample(app.pid))
            print("t=%3ds  handles=%d  mem=%.1fMB  cpu=%.1fs" % ((i + 1) * (secs - 5) // 4, *samples[-1]), flush=True)
        ev = li.notifies(li.log_lines())
        hours = (ev[-1][1] - ev[0][1]) / 3600 if len(ev) > 1 else 0
        print("simulated %.1f hours, %d notifications" % (hours, len(ev)), flush=True)
        for key, minutes in (("eyes", 20), ("stand", 45), ("posture", 30)):
            ts = [t for k, t in ev if k == key]
            gaps = [b - a for a, b in zip(ts, ts[1:])]
            # a tick is 60 s here, so allow interval .. interval + stagger + tick
            bad = [g for g in gaps if not (minutes * 60 - 1 <= g <= minutes * 60 + 5 * 60)]
            li.check("%s: %d events, all intervals within tolerance" % (key, len(ts)), not bad and len(ts) > 5,
                     "bad gaps: %s" % bad[:3] if bad else "")
            ok &= not bad
        allt = [t for _, t in ev]
        li.check("no duplicates (all >= 60 s apart)", all(b - a >= 59 for a, b in zip(allt, allt[1:])))
        li.check("handle count did not grow", samples[-1][0] - samples[0][0] <= 5,
                 "%d -> %d" % (samples[0][0], samples[-1][0]))
        li.check("memory did not grow (< 5 MB)", samples[-1][1] - samples[0][1] < 5,
                 "%.1f -> %.1f MB" % (samples[0][1], samples[-1][1]))
        li.check("no errors in log", not any("Traceback" in l for l in li.log_lines()))
        li.check("app still responsive after the run", li.control.is_running())
        li.control.send_command(li.control.ID_EXIT)
        app.wait(timeout=5)
    finally:
        if app.poll() is None:
            app.kill()
    failed = [r for r in li.results if not r[1]]
    print("%d checks, %d failed" % (len(li.results), len(failed)))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
