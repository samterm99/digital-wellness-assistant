"""User-state detection via the official Windows API (SHQueryUserNotificationState).

We only *read* what Windows itself reports; nothing here tries to override
full-screen or protected-content behaviour.
"""
import ctypes
import time
from ctypes import wintypes as wt

from . import config

_shell32 = ctypes.WinDLL("shell32")
_user32 = ctypes.WinDLL("user32")
_user32.GetForegroundWindow.restype = wt.HWND
_user32.GetClassNameW.argtypes = [wt.HWND, wt.LPWSTR, ctypes.c_int]

NOT_PRESENT, BUSY, D3D_FULLSCREEN, PRESENTATION, ACCEPTS = 1, 2, 3, 4, 5
NAMES = {1: "NOT_PRESENT(locked/screensaver)", 2: "BUSY(fullscreen)",
         3: "D3D_FULLSCREEN(game)", 4: "PRESENTATION", 5: "ACCEPTS_NOTIFICATIONS",
         6: "QUIET_TIME"}


def user_state():
    """Windows QUERY_USER_NOTIFICATION_STATE value, or None if the call failed."""
    state = ctypes.c_int(0)
    if _shell32.SHQueryUserNotificationState(ctypes.byref(state)) != 0:
        return None
    return state.value


def is_busy(state):
    return state in (BUSY, D3D_FULLSCREEN, PRESENTATION)


def is_away(state):
    return state == NOT_PRESENT


def _foreground_class():
    hwnd = _user32.GetForegroundWindow()
    if not hwnd:
        return ""
    buf = ctypes.create_unicode_buffer(256)
    _user32.GetClassNameW(hwnd, buf, 256)
    return buf.value


def diag(seconds=90):
    """Record state changes (+ foreground window *class* only, no titles) to logs/diag.txt.

    Used to check how Windows classifies YouTube/Netflix/games on the owner's machine.
    """
    config.LOG_DIR.mkdir(parents=True, exist_ok=True)
    last = object()
    with open(config.LOG_DIR / "diag.txt", "w", encoding="utf-8") as f:
        f.write("เวลา | สถานะ Windows | ชนิดหน้าต่างที่ใช้งานอยู่\n")
        end = time.time() + seconds
        while time.time() < end:
            st = user_state()
            cur = (st, _foreground_class())
            if cur != last:
                f.write("%s | %s | %s\n" % (time.strftime("%H:%M:%S"),
                                            NAMES.get(st, st), cur[1]))
                f.flush()
                last = cur
            time.sleep(1)
        f.write("จบการตรวจ\n")
