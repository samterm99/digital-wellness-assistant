"""Command ids + helpers for controlling the running tray app from another process."""
import ctypes
from ctypes import wintypes as wt

from . import config

WINDOW_CLASS = "DigitalWellnessTray" + config.INSTANCE
WM_COMMAND = 0x0111

(ID_PAUSE, ID_RESUME, ID_PAUSE30, ID_PAUSE60, ID_TEST,
 ID_PANEL, ID_RELOAD, ID_EXIT) = range(1001, 1009)
ID_EYEBREAK = 1009

_user32 = ctypes.WinDLL("user32", use_last_error=True)
_user32.FindWindowW.argtypes = [wt.LPCWSTR, wt.LPCWSTR]
_user32.FindWindowW.restype = wt.HWND
_user32.PostMessageW.argtypes = [wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM]


def seconds_since_logon():
    """Approximate time since the user's desktop shell started (None if unknown)."""
    import time
    try:
        user32, k32 = _user32, ctypes.WinDLL("kernel32", use_last_error=True)
        user32.GetShellWindow.restype = wt.HWND
        k32.OpenProcess.restype = wt.HANDLE
        k32.OpenProcess.argtypes = [wt.DWORD, wt.BOOL, wt.DWORD]
        k32.GetProcessTimes.argtypes = [wt.HANDLE] + [ctypes.POINTER(wt.FILETIME)] * 4
        k32.CloseHandle.argtypes = [wt.HANDLE]
        pid = wt.DWORD()
        user32.GetWindowThreadProcessId(user32.GetShellWindow(), ctypes.byref(pid))
        h = k32.OpenProcess(0x1000, False, pid.value)  # PROCESS_QUERY_LIMITED_INFORMATION
        if not h:
            return None
        ft = [wt.FILETIME() for _ in range(4)]
        ok = k32.GetProcessTimes(h, *[ctypes.byref(x) for x in ft])
        k32.CloseHandle(h)
        if not ok:
            return None
        start = ((ft[0].dwHighDateTime << 32) | ft[0].dwLowDateTime) / 1e7 - 11644473600
        return time.time() - start
    except Exception:
        return None


def is_running():
    return bool(_user32.FindWindowW(WINDOW_CLASS, None))


def send_command(cid):
    """Ask the running tray app to perform a command. False if it is not running."""
    hwnd = _user32.FindWindowW(WINDOW_CLASS, None)
    if not hwnd:
        return False
    return bool(_user32.PostMessageW(hwnd, WM_COMMAND, cid, 0))
