"""Live test of the REAL tray app (real window, real timer, real commands).

Time runs 120x faster (1 real second = 2 reminder-minutes) and notifications are
logged instead of shown, so nothing appears on screen. Takes about 1 minute.
Run:  python tests/live_integration.py
"""
import ctypes
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from ctypes import wintypes as wt
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOME = Path(tempfile.mkdtemp(prefix="dw_live_"))
SCALE = 120
os.environ.update(DW_HOME=str(HOME), DW_INSTANCE="live%d" % os.getpid(),
                  DW_TIME_SCALE=str(SCALE), DW_TICK_MS="100", DW_HEADLESS="1",
                  PYTHONPATH=str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "src"))

from wellness import config, control  # noqa: E402

LOG = HOME / "logs" / "app.log"
results = []


def check(name, ok, detail=""):
    results.append((name, ok, detail))
    print(("PASS  " if ok else "FAIL  ") + name + (("  -> " + detail) if detail else ""), flush=True)


def log_lines():
    try:
        return LOG.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []


def notifies(lines):
    out = []
    for ln in lines:
        m = re.search(r"NOTIFY (\w+) t=([\d.]+)", ln)
        if m:
            out.append((m.group(1), float(m.group(2))))
    return out


def find_t(lines, token, start=0):
    for i in range(start, len(lines)):
        if token in lines[i]:
            m = re.search(r"t=([\d.]+)", lines[i])
            return i, float(m.group(1)) if m else None
    return None, None


def state():
    return config.read_state() or {}


def wait_until(pred, timeout=10):
    end = time.time() + timeout
    while time.time() < end:
        if pred():
            return True
        time.sleep(0.1)
    return False


# --- process resource sampling (handles / memory / cpu) ---
class PMC(ctypes.Structure):
    _fields_ = [("cb", wt.DWORD), ("PageFaultCount", wt.DWORD),
                ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t), ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t)]


def sample(pid):
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    ps = ctypes.WinDLL("psapi", use_last_error=True)
    k32.OpenProcess.restype = wt.HANDLE
    h = k32.OpenProcess(0x1000 | 0x0400, False, pid)  # QUERY_LIMITED | QUERY_INFORMATION
    if not h:
        return None
    try:
        handles = wt.DWORD()
        k32.GetProcessHandleCount(h, ctypes.byref(handles))
        pmc = PMC(); pmc.cb = ctypes.sizeof(PMC)
        ps.GetProcessMemoryInfo(h, ctypes.byref(pmc), pmc.cb)
        c, e, kt, ut = (wt.FILETIME() for _ in range(4))
        k32.GetProcessTimes(h, ctypes.byref(c), ctypes.byref(e), ctypes.byref(kt), ctypes.byref(ut))
        cpu = sum(((f.dwHighDateTime << 32) | f.dwLowDateTime) for f in (kt, ut)) / 1e7
        return handles.value, pmc.WorkingSetSize / 1e6, cpu
    finally:
        k32.CloseHandle(h)


def main():
    config.save({"eyes": {"enabled": True, "minutes": 2},
                 "stand": {"enabled": True, "minutes": 5},
                 "posture": {"enabled": True, "minutes": 7},
                 "skip_fullscreen": True})
    py = [sys.executable, "-m", "wellness"]
    app = subprocess.Popen(py, cwd=str(ROOT), creationflags=0x08000000)  # no console window
    try:
        check("app starts and shows its window", wait_until(control.is_running, 10))
        wait_until(lambda: state().get("pid") == app.pid, 5)
        check("state.json is written and matches the process", state().get("pid") == app.pid)

        # second instance must exit by itself (no duplicate notifications)
        second = subprocess.Popen(py, cwd=str(ROOT), creationflags=0x08000000)
        try:
            rc = second.wait(timeout=10)
            check("second instance exits immediately (single instance)", rc == 0)
        except subprocess.TimeoutExpired:
            second.kill()
            check("second instance exits immediately (single instance)", False, "still running")

        # ---- A. normal running: 20 s real = 40 reminder-minutes
        time.sleep(1)
        base = sample(app.pid)
        time.sleep(20)
        ev = notifies(log_lines())
        gaps_ok, gap_detail = True, ""
        for key, minutes in (("eyes", 2), ("stand", 5), ("posture", 7)):
            ts = [t for k, t in ev if k == key]
            for a, b in zip(ts, ts[1:]):
                if not (minutes * 60 - 1 <= b - a <= minutes * 60 + 5 * 60):
                    gaps_ok, gap_detail = False, "%s gap %.0fs" % (key, b - a)
            expected = 40 // minutes
            if len(ts) < expected // 2:
                gaps_ok, gap_detail = False, "%s only %d (theory %d)" % (key, len(ts), expected)
        check("A. reminders fire repeatedly at correct intervals", gaps_ok and len(ev) > 0,
              gap_detail or "%d notifications: %s" % (len(ev), {k: sum(1 for x, _ in ev if x == k) for k in ("eyes", "stand", "posture")}))
        ts_all = [t for _, t in ev]
        check("A. never two notifications closer than 60 s (no duplicates)",
              all(b - a >= 59 for a, b in zip(ts_all, ts_all[1:])))

        # ---- B. pause
        n_before = len(notifies(log_lines()))
        control.send_command(control.ID_PAUSE)
        check("B. pause: state shows paused", wait_until(lambda: state().get("paused") is True, 3))
        i_pause, t_pause = find_t(log_lines(), "PAUSE minutes=None")
        n_at_pause = len(notifies(log_lines()))
        time.sleep(6)  # 12 reminder-minutes, longer than every interval
        check("B. pause: no notification while paused", len(notifies(log_lines())) == n_at_pause)

        # ---- C. resume
        control.send_command(control.ID_RESUME)
        check("C. resume: state shows running", wait_until(lambda: state().get("paused") is False, 3))
        lines = log_lines()
        i_res, t_res = find_t(lines, "RESUME")
        time.sleep(6)
        after = [t for k, t in notifies(log_lines()) if t > t_res]
        check("C. resume: timers restart (first reminder >= 2 min after resume, and one does come)",
              bool(after) and min(after) >= t_res + 2 * 60 - 1,
              "first at +%.0fs" % (min(after) - t_res) if after else "no notification")

        # ---- D. settings change takes effect without restart
        config.save({"eyes": {"enabled": True, "minutes": 2},
                     "stand": {"enabled": False, "minutes": 5},
                     "posture": {"enabled": True, "minutes": 7},
                     "skip_fullscreen": True})
        control.send_command(control.ID_RELOAD)
        wait_until(lambda: state()["reminders"]["stand"]["enabled"] is False, 3)
        lines = log_lines()
        i_cfg = max(i for i, ln in enumerate(lines) if "CONFIG reloaded" in ln)
        time.sleep(6)
        later = notifies(log_lines()[i_cfg:])
        check("D. disabling a reminder in settings stops it immediately",
              not any(k == "stand" for k, _ in later) and any(k == "eyes" for k, _ in later),
              str({k: sum(1 for x, _ in later if x == k) for k in ("eyes", "stand", "posture")}))

        # ---- E. timed pause (30 reminder-minutes = 15 s real) ends by itself
        control.send_command(control.ID_PAUSE30)
        check("E. timed pause: state shows paused with an end time",
              wait_until(lambda: state().get("paused") is True and state().get("paused_until"), 3))
        _, t_p30 = find_t(log_lines(), "PAUSE minutes=30")
        check("E. timed pause: resumes by itself",
              wait_until(lambda: state().get("paused") is False, 25), "waited for auto-resume")
        time.sleep(4)
        first = [t for _, t in notifies(log_lines()) if t > t_p30]
        check("E. timed pause: silent for the whole pause, then reminders return",
              bool(first) and min(first) >= t_p30 + 30 * 60 + 2 * 60 - 25,
              "first at +%.0f min" % ((min(first) - t_p30) / 60) if first else "none")

        # ---- F. resources over the whole run (~ 55 s real = ~ 110 reminder-minutes)
        end = sample(app.pid)
        if base and end:
            dh, dmb, dcpu = end[0] - base[0], end[1] - base[1], end[2] - base[2]
            check("F. no handle leak (growth <= 5)", dh <= 5, "handles %d -> %d" % (base[0], end[0]))
            check("F. memory stable (growth < 5 MB)", dmb < 5, "%.1f -> %.1f MB" % (base[1], end[1]))
            check("F. low CPU even at 150x tick rate (< 1.5 s CPU)", dcpu < 1.5, "%.2f s CPU" % dcpu)
        else:
            check("F. resource sampling", False, "could not open process")

        check("no errors in the log",
              not any("Traceback" in ln or "error in window procedure" in ln for ln in log_lines()))

        # ---- G. exit: nothing may be shown afterwards
        pid_before = app.pid
        control.send_command(control.ID_EXIT)
        try:
            app.wait(timeout=5)
            exited = True
        except subprocess.TimeoutExpired:
            exited = False
        check("G. exit command ends the process", exited)
        check("G. tray window is gone", not control.is_running())
        n_exit = len(notifies(log_lines()))
        time.sleep(3)
        check("G. no notifications after exit", len(notifies(log_lines())) == n_exit)
        check("G. 'quit' when not running is handled", control.send_command(control.ID_EXIT) is False)
    finally:
        if app.poll() is None:
            app.kill()

    failed = [r for r in results if not r[1]]
    print("\n%d checks, %d passed, %d failed" % (len(results), len(results) - len(failed), len(failed)))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
