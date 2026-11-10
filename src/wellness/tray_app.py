"""Windows tray app using only ctypes + Win32 (no third-party packages).

Test-only environment overrides: DW_TIME_SCALE (clock speed-up), DW_TICK_MS,
DW_HEADLESS (log notifications instead of showing balloons).
"""
import ctypes
import logging
import os
import subprocess
import sys
import time
from ctypes import wintypes as wt
from pathlib import Path

from . import config, fullscreen
from .control import (WINDOW_CLASS, ID_PAUSE, ID_RESUME, ID_PAUSE30, ID_PAUSE60,
                      ID_TEST, ID_PANEL, ID_RELOAD, ID_EXIT, ID_EYEBREAK)
from .scheduler import Scheduler, GAP_LIMIT

log = logging.getLogger("wellness")

user32 = ctypes.WinDLL("user32", use_last_error=True)
shell32 = ctypes.WinDLL("shell32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

LRESULT = ctypes.c_ssize_t
WNDPROC = ctypes.WINFUNCTYPE(LRESULT, wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM)

WM_DESTROY, WM_COMMAND, WM_TIMER, WM_NULL = 0x0002, 0x0111, 0x0113, 0x0000
WM_RBUTTONUP, WM_LBUTTONUP, WM_LBUTTONDBLCLK = 0x0205, 0x0202, 0x0203
WM_TRAY = 0x8001
NIM_ADD, NIM_MODIFY, NIM_DELETE = 0, 1, 2
NIF_MESSAGE, NIF_ICON, NIF_TIP, NIF_INFO = 1, 2, 4, 0x10
NIIF_INFO = 1
MF_STRING, MF_SEPARATOR = 0, 0x800
TPM_RIGHTBUTTON, TPM_BOTTOMALIGN = 0x2, 0x20
ERROR_ALREADY_EXISTS = 183

TICK_MS = int(os.environ.get("DW_TICK_MS", 15000))
TIME_SCALE = float(os.environ.get("DW_TIME_SCALE", 1))
HEADLESS = bool(os.environ.get("DW_HEADLESS"))


class WNDCLASSW(ctypes.Structure):
    _fields_ = [("style", wt.UINT), ("lpfnWndProc", WNDPROC),
                ("cbClsExtra", ctypes.c_int), ("cbWndExtra", ctypes.c_int),
                ("hInstance", wt.HINSTANCE), ("hIcon", wt.HICON),
                ("hCursor", wt.HANDLE), ("hbrBackground", wt.HBRUSH),
                ("lpszMenuName", wt.LPCWSTR), ("lpszClassName", wt.LPCWSTR)]


class GUID(ctypes.Structure):
    _fields_ = [("a", wt.DWORD), ("b", wt.WORD), ("c", wt.WORD), ("d", ctypes.c_ubyte * 8)]


class NOTIFYICONDATAW(ctypes.Structure):
    _fields_ = [("cbSize", wt.DWORD), ("hWnd", wt.HWND), ("uID", wt.UINT),
                ("uFlags", wt.UINT), ("uCallbackMessage", wt.UINT), ("hIcon", wt.HICON),
                ("szTip", wt.WCHAR * 128), ("dwState", wt.DWORD), ("dwStateMask", wt.DWORD),
                ("szInfo", wt.WCHAR * 256), ("uVersion", wt.UINT),
                ("szInfoTitle", wt.WCHAR * 64), ("dwInfoFlags", wt.DWORD),
                ("guidItem", GUID), ("hBalloonIcon", wt.HICON)]


def _setup_prototypes():
    user32.DefWindowProcW.argtypes = [wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM]
    user32.DefWindowProcW.restype = LRESULT
    user32.RegisterClassW.argtypes = [ctypes.POINTER(WNDCLASSW)]
    user32.CreateWindowExW.argtypes = [wt.DWORD, wt.LPCWSTR, wt.LPCWSTR, wt.DWORD,
                                       ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                       wt.HWND, wt.HMENU, wt.HINSTANCE, wt.LPVOID]
    user32.CreateWindowExW.restype = wt.HWND
    user32.SetTimer.argtypes = [wt.HWND, ctypes.c_size_t, wt.UINT, wt.LPVOID]
    user32.GetMessageW.argtypes = [ctypes.POINTER(wt.MSG), wt.HWND, wt.UINT, wt.UINT]
    user32.TranslateMessage.argtypes = [ctypes.POINTER(wt.MSG)]
    user32.DispatchMessageW.argtypes = [ctypes.POINTER(wt.MSG)]
    user32.DispatchMessageW.restype = LRESULT
    user32.CreatePopupMenu.restype = wt.HMENU
    user32.AppendMenuW.argtypes = [wt.HMENU, wt.UINT, ctypes.c_size_t, wt.LPCWSTR]
    user32.TrackPopupMenu.argtypes = [wt.HMENU, wt.UINT, ctypes.c_int, ctypes.c_int,
                                      ctypes.c_int, wt.HWND, wt.LPVOID]
    user32.DestroyMenu.argtypes = [wt.HMENU]
    user32.SetForegroundWindow.argtypes = [wt.HWND]
    user32.PostMessageW.argtypes = [wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM]
    user32.DestroyWindow.argtypes = [wt.HWND]
    user32.LoadIconW.argtypes = [wt.HINSTANCE, ctypes.c_void_p]
    user32.LoadIconW.restype = wt.HICON
    user32.GetCursorPos.argtypes = [ctypes.POINTER(wt.POINT)]
    user32.RegisterWindowMessageW.argtypes = [wt.LPCWSTR]
    shell32.Shell_NotifyIconW.argtypes = [wt.DWORD, ctypes.POINTER(NOTIFYICONDATAW)]
    kernel32.GetModuleHandleW.argtypes = [wt.LPCWSTR]
    kernel32.GetModuleHandleW.restype = wt.HINSTANCE
    kernel32.CreateMutexW.argtypes = [wt.LPVOID, wt.BOOL, wt.LPCWSTR]
    kernel32.CreateMutexW.restype = wt.HANDLE


def spawn_module(module, *args):
    """Start `python -m <module>` without a console window; returns the Popen."""
    if config.FROZEN:  # installed exe: it is its own interpreter; args are the mode flags
        return subprocess.Popen([sys.executable, *args], cwd=str(config.PROJECT_DIR))
    exe = Path(sys.executable)
    pyw = exe.with_name("pythonw.exe")
    env = dict(os.environ, PYTHONPATH=str(config.PROJECT_DIR / "src"))
    return subprocess.Popen([str(pyw if pyw.exists() else exe), "-m", module, *args],
                            env=env, cwd=str(config.PROJECT_DIR))


class TrayApp:
    def __init__(self, selftest=False):
        _setup_prototypes()
        self.selftest = selftest
        self.cfg = config.load()
        self.cfg_mtime = config.mtime()
        # the "computer slept" threshold is real time, so scale it with the test clock
        self.sched = Scheduler(self.cfg, self._now(), gap_limit=GAP_LIMIT * TIME_SCALE)
        self.busy = self.away = False
        self._sig = None
        self._tip_paused = None
        self._panel = None
        self._eyebreak = None
        self._proc = WNDPROC(self._wndproc)  # keep reference alive
        self._taskbar_created = user32.RegisterWindowMessageW("TaskbarCreated")
        self._create_window()
        self._add_icon()
        self._sync_state()
        log.info("START pid=%d scale=%s tick=%dms headless=%s",
                 os.getpid(), TIME_SCALE, TICK_MS, HEADLESS)

    @staticmethod
    def _now():
        return time.monotonic() * TIME_SCALE

    # ----- window / tray plumbing -----
    def _create_window(self):
        hinst = kernel32.GetModuleHandleW(None)
        wc = WNDCLASSW()
        wc.lpfnWndProc = self._proc
        wc.hInstance = hinst
        wc.lpszClassName = WINDOW_CLASS
        user32.RegisterClassW(ctypes.byref(wc))
        self.hwnd = user32.CreateWindowExW(0, WINDOW_CLASS, "DigitalWellness", 0,
                                           0, 0, 0, 0, None, None, hinst, None)
        if not self.hwnd:
            raise ctypes.WinError(ctypes.get_last_error())
        user32.SetTimer(self.hwnd, 1, TICK_MS, None)

    def _nid(self, flags):
        nid = NOTIFYICONDATAW()
        nid.cbSize = ctypes.sizeof(NOTIFYICONDATAW)
        nid.hWnd = self.hwnd
        nid.uID = 1
        nid.uFlags = flags
        return nid

    def _tip(self):
        return ("ผู้ช่วยสุขภาพดิจิทัล - หยุดชั่วคราว" if self.sched.paused
                else "ผู้ช่วยสุขภาพดิจิทัล - ทำงานอยู่")

    def _add_icon(self):
        nid = self._nid(NIF_MESSAGE | NIF_ICON | NIF_TIP)
        nid.uCallbackMessage = WM_TRAY
        nid.hIcon = user32.LoadIconW(None, 32516)  # IDI_INFORMATION
        nid.szTip = self._tip()
        shell32.Shell_NotifyIconW(NIM_ADD, ctypes.byref(nid))

    def _update_tip(self):
        nid = self._nid(NIF_TIP)
        nid.szTip = self._tip()
        shell32.Shell_NotifyIconW(NIM_MODIFY, ctypes.byref(nid))

    def notify(self, title, text):
        if HEADLESS:
            return
        nid = self._nid(NIF_INFO)
        nid.szInfoTitle = title[:63]
        nid.szInfo = text[:255]
        nid.dwInfoFlags = NIIF_INFO
        shell32.Shell_NotifyIconW(NIM_MODIFY, ctypes.byref(nid))

    # ----- state shared with the control panel -----
    def _sync_state(self):
        """Refresh tooltip and state.json, but only when something changed."""
        s = self.sched
        sig = (s.paused, s.paused_until, tuple(sorted(s.next_due.items())),
               self.busy, self.away,
               tuple((k, self.cfg[k]["enabled"], self.cfg[k]["minutes"]) for k in config.MESSAGES))
        if s.paused != self._tip_paused:
            self._tip_paused = s.paused
            log.info("STATE paused=%s t=%.1f", s.paused, self._now())
            self._update_tip()
        if sig == self._sig:
            return
        self._sig = sig
        now, wall = self._now(), time.time()
        rem = s.remaining(now)
        state = {
            "pid": os.getpid(),
            "paused": s.paused,
            "paused_until": (None if s.paused_until is None
                             else wall + (s.paused_until - now) / TIME_SCALE),
            "busy": self.busy,
            "away": self.away,
            "reminders": {
                k: {"enabled": self.cfg[k]["enabled"],
                    "minutes": self.cfg[k]["minutes"],
                    "next": wall + rem[k] / TIME_SCALE if k in rem else None}
                for k in config.MESSAGES},
        }
        try:
            config.write_state(state)
        except OSError:
            log.exception("write_state failed")
            self._sig = None  # try again on the next tick

    # ----- behaviour -----
    def _reload_config(self, force=False):
        m = config.mtime()
        if force or m != self.cfg_mtime:
            self.cfg_mtime = m
            self.cfg = config.load()
            self.sched.apply_config(self.cfg, self._now())
            log.info("CONFIG reloaded %s", {k: self.cfg[k] for k in config.MESSAGES})

    def _on_tick(self):
        self._reload_config()
        st = fullscreen.user_state()
        busy, away = fullscreen.is_busy(st), fullscreen.is_away(st)
        if (busy, away) != (self.busy, self.away):
            log.info("USERSTATE %s busy=%s away=%s", fullscreen.NAMES.get(st, st), busy, away)
        self.busy, self.away = busy, away
        key = self.sched.tick(self._now(), busy, away)
        if key:
            self._dispatch(key)
        self._sync_state()

    def _dispatch(self, key):
        log.info("NOTIFY %s t=%.1f", key, self._now())
        if key == "eyes":
            if not HEADLESS:  # interactive window replaces the balloon (never both)
                self._start_eye_break(auto=True)
        else:
            self.notify(*config.MESSAGES[key])

    def _pause(self, minutes=None):
        self.sched.pause(self._now(), minutes)
        log.info("PAUSE minutes=%s t=%.1f", minutes, self._now())

    def _resume(self):
        self.sched.resume(self._now())
        log.info("RESUME t=%.1f", self._now())

    def _open_panel(self):
        if self._panel is not None and self._panel.poll() is None:
            return  # already open
        self._panel = spawn_module("wellness", "--panel")

    def _start_eye_break(self, auto=False):
        # one window at a time (the process also guards itself with a mutex); Popen
        # does not wait, so the tray loop and scheduler keep running
        if self._eyebreak is not None and self._eyebreak.poll() is None:
            return
        self._eyebreak = spawn_module("wellness", "--eyebreak", *(["--auto"] if auto else []))

    def _show_menu(self):
        menu = user32.CreatePopupMenu()
        paused = self.sched.paused
        user32.AppendMenuW(menu, MF_STRING, ID_PANEL, "เปิดหน้าต่างควบคุม")
        user32.AppendMenuW(menu, MF_SEPARATOR, 0, None)
        user32.AppendMenuW(menu, MF_STRING, ID_RESUME if paused else ID_PAUSE,
                           "▶ เริ่มการแจ้งเตือนต่อ" if paused else "⏸ หยุดการแจ้งเตือนชั่วคราว")
        if not paused:
            user32.AppendMenuW(menu, MF_STRING, ID_PAUSE30, "หยุด 30 นาที")
            user32.AppendMenuW(menu, MF_STRING, ID_PAUSE60, "หยุด 1 ชั่วโมง")
        user32.AppendMenuW(menu, MF_STRING, ID_EYEBREAK, "เริ่มพักสายตา 20 วินาที")
        user32.AppendMenuW(menu, MF_STRING, ID_TEST, "ทดสอบการแจ้งเตือน")
        user32.AppendMenuW(menu, MF_SEPARATOR, 0, None)
        user32.AppendMenuW(menu, MF_STRING, ID_EXIT, "ปิดโปรแกรม")
        pt = wt.POINT()
        user32.GetCursorPos(ctypes.byref(pt))
        user32.SetForegroundWindow(self.hwnd)  # needed so the menu closes on outside click
        user32.TrackPopupMenu(menu, TPM_RIGHTBUTTON | TPM_BOTTOMALIGN, pt.x, pt.y, 0, self.hwnd, None)
        user32.PostMessageW(self.hwnd, WM_NULL, 0, 0)
        user32.DestroyMenu(menu)

    def _on_command(self, cid):
        if cid == ID_PAUSE:
            self._pause()
        elif cid == ID_RESUME:
            self._resume()
        elif cid == ID_PAUSE30:
            self._pause(30)
        elif cid == ID_PAUSE60:
            self._pause(60)
        elif cid == ID_TEST:
            log.info("TEST notification")
            self.notify("ทดสอบการแจ้งเตือน", "ถ้าเห็นข้อความนี้ แสดงว่าการแจ้งเตือนทำงานปกติ")
        elif cid == ID_PANEL:
            self._open_panel()
        elif cid == ID_EYEBREAK:
            self._start_eye_break()
        elif cid == ID_RELOAD:
            self._reload_config(force=True)
        elif cid == ID_EXIT:
            log.info("EXIT requested")
            user32.DestroyWindow(self.hwnd)
            return
        self._sync_state()

    def _wndproc(self, hwnd, msg, wparam, lparam):
        try:
            if msg == WM_TIMER:
                self._on_tick()
                return 0
            if msg == WM_TRAY:
                ev = lparam & 0xFFFF
                if ev in (WM_RBUTTONUP, WM_LBUTTONUP):
                    self._show_menu()
                elif ev == WM_LBUTTONDBLCLK:
                    self._open_panel()
                return 0
            if msg == WM_COMMAND:
                self._on_command(wparam & 0xFFFF)
                return 0
            if msg == self._taskbar_created:  # Explorer restarted
                self._add_icon()
                return 0
            if msg == WM_DESTROY:
                shell32.Shell_NotifyIconW(NIM_DELETE, ctypes.byref(self._nid(0)))
                user32.PostQuitMessage(0)
                return 0
        except Exception:  # never let an error kill the message loop
            log.exception("error in window procedure (msg=0x%x)", msg)
            return 0
        return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

    def run(self):
        if self.selftest:
            self._run_selftest()
            return
        msg = wt.MSG()
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))
        log.info("STOPPED")

    def _run_selftest(self):
        """Show each reminder once, exercise pause/resume + state check, then exit."""
        for key in ("eyes", "stand", "posture"):
            self.notify(*config.MESSAGES[key])
            time.sleep(1)
        self._pause(); assert self.sched.paused
        self._resume(); assert not self.sched.paused
        print("user_state() =", fullscreen.user_state())
        user32.DestroyWindow(self.hwnd)
        print("SELFTEST OK")


def single_instance():
    """Return False if another instance is already running."""
    _setup_prototypes()
    kernel32.CreateMutexW(None, False, "Local\\DigitalWellnessAssistant" + config.INSTANCE)
    return ctypes.get_last_error() != ERROR_ALREADY_EXISTS
