"""Drives the real control panel (hidden window) against a real running tray app.

Run:  python tests/live_panel.py
"""
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOME = Path(tempfile.mkdtemp(prefix="dw_panel_"))
os.environ.update(DW_HOME=str(HOME), DW_INSTANCE="panel%d" % os.getpid(),
                  DW_HEADLESS="1", PYTHONPATH=str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "src"))

import tkinter as tk  # noqa: E402
from wellness import config, control, panel  # noqa: E402

results = []


def check(name, ok, detail=""):
    results.append(ok)
    print(("PASS  " if ok else "FAIL  ") + name + (("  -> " + detail) if detail else ""), flush=True)


def pump(root, seconds):
    end = time.time() + seconds
    while time.time() < end:
        root.update()
        time.sleep(0.05)


def main():
    root = tk.Tk()
    root.withdraw()
    p = panel.Panel(root)
    pump(root, 0.5)
    check("panel shows 'not running' when the app is off", "ไม่ได้ทำงาน" in p.status.cget("text"))

    app = subprocess.Popen([sys.executable, "-m", "wellness"], cwd=str(ROOT), creationflags=0x08000000)
    try:
        for _ in range(100):
            if control.is_running() and config.read_state():
                break
            time.sleep(0.1)
        pump(root, 1.5)
        check("panel shows 'running'", "กำลังทำงาน" in p.status.cget("text"), p.status.cget("text"))
        cd = p.countdown["eyes"].cget("text")
        check("panel shows a countdown for eyes", cd.startswith("เตือนอีก 19:") or cd.startswith("เตือนอีก 20:"), cd)

        p.on_toggle()                      # pause
        pump(root, 1.5)
        check("pause button -> panel shows paused", "หยุดชั่วคราว" in p.status.cget("text"), p.status.cget("text"))
        check("button now offers resume", "เริ่ม" in p.toggle.cget("text"), p.toggle.cget("text"))

        p.on_toggle()                      # resume
        pump(root, 1.5)
        check("resume button -> panel shows running again", "กำลังทำงาน" in p.status.cget("text"))

        p.minutes["eyes"].set("7")
        p.save()
        pump(root, 1.5)
        check("saving interval updates the live countdown",
              p.countdown["eyes"].cget("text").startswith("เตือนอีก 06:") or
              p.countdown["eyes"].cget("text").startswith("เตือนอีก 07:"),
              p.countdown["eyes"].cget("text"))
        check("saved config has the new value", config.load()["eyes"]["minutes"] == 7)

        p.minutes["eyes"].set("abc")
        p.save()
        check("invalid interval is rejected with a message", "ตัวเลข" in p.msg.cget("text"))
        check("invalid interval is not saved", config.load()["eyes"]["minutes"] == 7)

        control.send_command(control.ID_EXIT)
        app.wait(timeout=5)
        pump(root, 1.5)
        check("panel notices the app was closed", "ไม่ได้ทำงาน" in p.status.cget("text"))
    finally:
        if app.poll() is None:
            app.kill()
        root.destroy()
    print("\n%d checks, %d failed" % (len(results), results.count(False)))
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
