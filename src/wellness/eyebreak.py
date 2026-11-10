"""Interactive 20-second eye-break window.

Runs as its own small process (`python -m wellness --eyebreak [--auto]`).
  --auto  : opened by the tray at a scheduled eye-break time; closes by itself after
            OFFER_TIMEOUT seconds if the user does nothing (no snooze, no repeat).
  (none)  : opened manually (tray menu / control panel); waits for the user.
The countdown only starts when the user clicks Start. A second launch while one
is open exits at once (mutex).
"""
import ctypes
import sys
import time

from . import config

DURATION = 20.0
OFFER_TIMEOUT = 15.0

TITLE = "ถึงเวลาพักสายตา"          # heading inside the popup
WINDOW_TITLE = "ผู้ช่วยสุขภาพดิจิทัล"  # same app name as the Windows notifications
MARGIN = 16
INSTRUCTION = "มองไกลประมาณ 6 เมตร เป็นเวลา 20 วินาที"


class EyeBreakTimer:
    """Pure countdown logic on an injectable monotonic clock (testable)."""

    def __init__(self, clock=time.monotonic, duration=DURATION, offer_timeout=None):
        self.clock, self.duration, self.offer_timeout = clock, duration, offer_timeout
        self.created = clock()
        self.started = None
        # idle (offer) -> running -> done | cancelled ; idle -> skipped | expired
        self.state = "idle"

    def start(self):
        if self.state != "idle":
            return False  # no overlapping / repeated timers
        self.started, self.state = self.clock(), "running"
        return True

    def remaining(self):
        if self.state != "running":
            return 0.0 if self.state == "done" else self.duration
        return max(0.0, self.duration - (self.clock() - self.started))

    def cancel(self):
        if self.state == "running":
            self.state = "cancelled"

    def skip(self):
        if self.state == "idle":
            self.state = "skipped"

    def expired(self):
        """True once, when an unanswered offer has waited offer_timeout seconds."""
        if (self.state == "idle" and self.offer_timeout is not None
                and self.clock() - self.created >= self.offer_timeout):
            self.state = "expired"
            return True
        return False

    def poll(self):
        """True exactly once, when the duration has elapsed (never after cancel)."""
        if self.state == "running" and self.remaining() <= 0:
            self.state = "done"
            return True
        return False


class Session:
    """What the window does, without any Tk: buttons and the 200 ms tick call this."""

    def __init__(self, timer, sound_on, play, close):
        self.timer, self.sound_on, self.play, self.close = timer, sound_on, play, close
        self.closed = False

    def _close(self):
        if not self.closed:
            self.closed = True
            self.close()

    def on_start(self):
        self.timer.start()

    def on_skip(self):  # Skip button, or X while still offering
        self.timer.skip()
        self._close()

    def on_cancel(self):  # Cancel button, or X during the countdown
        self.timer.cancel()
        self._close()

    def on_x(self):
        self.on_cancel() if self.timer.state == "running" else self.on_skip()

    def step(self):
        """Called every ~200 ms; returns the seconds to display while counting down."""
        if self.closed:
            return None
        if self.timer.poll():  # checked first: a running countdown is never timed out
            if self.sound_on:
                self.play()  # exactly once: poll() is True only once
            self._close()
        elif self.timer.expired():
            self._close()
        return None if self.closed else self.timer.remaining()


def single_instance():
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.CreateMutexW.restype = ctypes.c_void_p
    k32.CreateMutexW(None, False, "Local\\DigitalWellnessEyeBreak" + config.INSTANCE)
    return ctypes.get_last_error() != 183


def play_sound():
    try:
        import winsound
        winsound.MessageBeep(winsound.MB_ICONASTERISK)  # one short system chime
    except Exception:
        pass


def _no_activate(root):
    """Keep the window from taking keyboard focus (WS_EX_NOACTIVATE)."""
    try:
        u = ctypes.WinDLL("user32")
        u.GetParent.restype = ctypes.c_void_p
        u.GetParent.argtypes = [ctypes.c_void_p]
        u.GetWindowLongW.argtypes = [ctypes.c_void_p, ctypes.c_int]
        u.SetWindowLongW.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_long]
        hwnd = u.GetParent(root.winfo_id()) or root.winfo_id()
        u.SetWindowLongW(hwnd, -20, u.GetWindowLongW(hwnd, -20) | 0x08000000)
    except Exception:
        pass


def work_area(root):
    """(left, top, right, bottom) of the monitor under the mouse, without the taskbar."""
    try:
        from ctypes import wintypes as wt
        u = ctypes.WinDLL("user32")
        pt = wt.POINT()
        u.GetCursorPos(ctypes.byref(pt))
        u.MonitorFromPoint.restype = ctypes.c_void_p
        u.MonitorFromPoint.argtypes = [wt.POINT, wt.DWORD]
        mon = u.MonitorFromPoint(pt, 2)  # MONITOR_DEFAULTTONEAREST

        class MONITORINFO(ctypes.Structure):
            _fields_ = [("cbSize", wt.DWORD), ("rcMonitor", wt.RECT),
                        ("rcWork", wt.RECT), ("dwFlags", wt.DWORD)]
        mi = MONITORINFO()
        mi.cbSize = ctypes.sizeof(mi)
        u.GetMonitorInfoW.argtypes = [ctypes.c_void_p, ctypes.POINTER(MONITORINFO)]
        if mon and u.GetMonitorInfoW(mon, ctypes.byref(mi)):
            w = mi.rcWork
            return w.left, w.top, w.right, w.bottom
    except Exception:
        pass
    return 0, 0, root.winfo_screenwidth(), root.winfo_screenheight() - 60


def frame_extra(root):
    """(width, height) of the window frame (title bar + borders) around the client area."""
    try:
        from ctypes import wintypes as wt
        u = ctypes.WinDLL("user32")
        u.GetParent.restype = ctypes.c_void_p
        u.GetParent.argtypes = [ctypes.c_void_p]
        u.GetWindowRect.argtypes = [ctypes.c_void_p, ctypes.POINTER(wt.RECT)]
        u.GetClientRect.argtypes = [ctypes.c_void_p, ctypes.POINTER(wt.RECT)]
        hwnd = u.GetParent(root.winfo_id()) or root.winfo_id()
        outer, inner = wt.RECT(), wt.RECT()
        u.GetWindowRect(hwnd, ctypes.byref(outer))
        u.GetClientRect(hwnd, ctypes.byref(inner))
        return (max(0, outer.right - outer.left - inner.right),
                max(0, outer.bottom - outer.top - inner.bottom))
    except Exception:
        return 0, 0


def place(w, h, area, margin=MARGIN, frame=(0, 0)):
    """(x, y, h): w x h client size at the bottom-right of the work area.

    The Tk position is that of the outer frame, so the frame (title bar, borders) is
    counted in the size: the whole window, not just the client, ends `margin` above the edge.
    """
    l, t, r, b = area
    fw, fh = frame
    h = min(h, b - t - 2 * margin - fh)
    return max(l, r - w - fw - margin), max(t, b - h - fh - margin), h


def main():
    auto = "--auto" in sys.argv
    if not single_instance():
        return
    import tkinter as tk
    from tkinter import ttk

    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass
    sound_on = config.load()["eye_break_sound"]
    root = tk.Tk()
    root.title(WINDOW_TITLE)
    root.resizable(False, False)
    root.attributes("-topmost", True)
    root.after(4000, lambda: root.attributes("-topmost", False))  # not permanently on top
    frm = ttk.Frame(root, padding=16)
    frm.grid()
    ttk.Label(frm, text=TITLE, font=("Tahoma", 14, "bold")).grid()
    info = ttk.Label(frm, text=INSTRUCTION, font=("Tahoma", 11))
    info.grid(pady=(4, 0))
    big = tk.Label(frm, font=("Tahoma", 30, "bold"), fg="#1b7f3b")
    note = ttk.Label(frm, foreground="#555555")
    btns = ttk.Frame(frm)
    btns.grid(row=3, pady=(10, 0))

    session = Session(EyeBreakTimer(offer_timeout=OFFER_TIMEOUT if auto else None),
                      sound_on, play_sound, root.destroy)

    def reposition(w, h):
        area = work_area(root)
        x, y, h2 = place(w, h, area, frame=frame_extra(root))
        root.geometry("%dx%d+%d+%d" % (w, h2, x, y))
        root.update_idletasks()  # the real frame is known once the window is mapped: re-place
        x, y, h2 = place(w, h, area, frame=frame_extra(root))
        root.geometry("%dx%d+%d+%d" % (w, h2, x, y))

    def show_running():
        info.grid_remove()
        big.grid(row=1, pady=4)
        note.config(text="ไม่ต้องมองหน้าต่างนี้ — จะมีเสียงเบา ๆ เมื่อครบเวลา" if sound_on
                    else "ไม่ต้องมองหน้าต่างนี้ (ปิดเสียงไว้)")
        note.grid(row=2)
        for w in btns.winfo_children():
            w.destroy()
        ttk.Button(btns, text="ยกเลิก", command=session.on_cancel).grid()
        root.update_idletasks()  # re-fit to the countdown layout, inside the work area
        reposition(max(root.winfo_reqwidth(), 360), root.winfo_reqheight())

    def start():
        session.on_start()
        show_running()

    ttk.Button(btns, text="เริ่มพัก 20 วินาที", command=start).grid(row=0, column=0, padx=(0, 8))
    ttk.Button(btns, text="ข้าม", command=session.on_skip).grid(row=0, column=1)

    root.update_idletasks()
    reposition(max(root.winfo_reqwidth(), 360), root.winfo_reqheight() + 70)
    root.update_idletasks()
    _no_activate(root)
    root.protocol("WM_DELETE_WINDOW", session.on_x)

    def tick():
        rem = session.step()
        if rem is None:
            return
        if session.timer.state == "running":
            big.config(text="%d วินาที" % int(rem + 0.999))
        root.after(200, tick)

    tick()
    root.mainloop()
