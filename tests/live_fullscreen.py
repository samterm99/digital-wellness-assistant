"""Does Windows report 'busy' when a real full-screen window is shown?

Opens a black full-screen window for ~5 s (the screen briefly goes black), and
reads what SHQueryUserNotificationState says before / during / after.
Run:  python tests/live_fullscreen.py
"""
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from wellness import fullscreen  # noqa: E402


def child():
    import ctypes
    import tkinter as tk
    root = tk.Tk()
    root.configure(bg="black")
    root.attributes("-fullscreen", True)
    root.attributes("-topmost", True)
    root.update()
    root.focus_force()
    root.update()
    # Windows only classifies a window as full-screen if it is the foreground window
    user32 = ctypes.windll.user32
    user32.SetForegroundWindow(user32.GetParent(root.winfo_id()) or root.winfo_id())
    root.after(5500, root.destroy)
    root.mainloop()


def main():
    names = fullscreen.NAMES
    before = fullscreen.user_state()
    print("before :", names.get(before, before))
    p = subprocess.Popen([sys.executable, __file__, "--child"])
    seen = []
    for _ in range(9):
        time.sleep(0.5)
        seen.append(fullscreen.user_state())
    print("during :", [names.get(s, s) for s in seen])
    p.wait()
    time.sleep(1)
    after = fullscreen.user_state()
    print("after  :", names.get(after, after))
    busy_seen = any(fullscreen.is_busy(s) for s in seen)
    ok = busy_seen and not fullscreen.is_busy(before) and not fullscreen.is_busy(after)
    print("RESULT :", "PASS - fullscreen window detected as busy, and cleared afterwards" if ok
          else "NOT CONFIRMED - see states above")
    return 0 if ok else 1


if __name__ == "__main__":
    if "--child" in sys.argv:
        child()
    else:
        sys.exit(main())
