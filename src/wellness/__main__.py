"""Entry point.

  python -m wellness            start the tray app
  python -m wellness --panel    open the Thai control window
  python -m wellness --auto-panel  panel unless disabled for Windows login (start.bat)
  python -m wellness --launch   (installed exe) start the tray, then --auto-panel
  python -m wellness --tray     tray only (what --launch starts in the background)
  python -m wellness --quit    close the running app
  python -m wellness --diag     record full-screen detection for 90 s (logs/diag.txt)
  python -m wellness --selftest quick smoke test (shows real notifications)

The installed exe takes the same flags (DigitalWellnessAssistant.exe --launch --startup).
"""
import sys

APP_ID = "DigitalWellness.Assistant"  # AppUserModelID: notification / taskbar identity


def _has_package_identity():
    """True when running inside an MSIX package (Microsoft Store build)."""
    import ctypes
    try:
        n = ctypes.c_uint32(0)
        # 15700 = APPMODEL_ERROR_NO_PACKAGE (a normal, unpackaged process)
        return ctypes.windll.kernel32.GetCurrentPackageFullName(ctypes.byref(n), None) != 15700
    except Exception:
        return False


def _set_app_id():
    """Inno-installed exe only: name the process so Windows attributes notifications to it
    (the installer registers the same id with the display name). An MSIX package already
    has its own identity from the manifest, so it must not override it."""
    import ctypes
    if _has_package_identity():
        return
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_ID)
    except Exception:
        pass


def _auto_panel(args):
    # `--startup` adds the explicit Windows-login argument. The panel is
    # skipped only for a Windows-login start with the option turned off.
    from . import config, control
    explicit = "--startup" in args
    # The logon-time guess is only for legacy start.bat shortcuts (--auto-panel alone);
    # an installed --launch without --startup is a manual start: always show the panel.
    # `--packaged` = MSIX start (Start tile and the start-up task both pass no flags, so the
    # Windows-login case can only be guessed from the shell start time).
    manual = "--launch" in args and "--packaged" not in args
    since = None if explicit or manual else control.seconds_since_logon()
    if config.panel_wanted(config.load(), explicit, since):
        from .panel import main as panel_main
        panel_main()


def main():
    args = sys.argv[1:]
    from . import config
    if config.FROZEN:
        _set_app_id()
        if not args and _has_package_identity():
            args = ["--launch", "--packaged"]  # MSIX: Start tile / start-up task run with no flags
    if "--panel" in args:
        from .panel import main as panel_main
        panel_main()
    elif "--launch" in args:
        from .tray_app import spawn_module
        spawn_module("wellness", "--tray")  # tray guards itself with its single-instance mutex
        _auto_panel(args)
    elif "--auto-panel" in args:
        _auto_panel(args)
    elif "--eyebreak" in args:
        from .eyebreak import main as eyebreak_main
        eyebreak_main()
    elif "--quit" in args:
        from . import control
        print("ส่งคำสั่งปิดแล้ว" if control.send_command(control.ID_EXIT)
              else "โปรแกรมไม่ได้ทำงานอยู่")
    elif "--diag" in args:
        from . import fullscreen
        fullscreen.diag()
    else:
        from .tray_app import TrayApp, single_instance
        config.setup_logging()
        selftest = "--selftest" in args
        if not selftest and not single_instance():
            return  # already running
        TrayApp(selftest=selftest).run()


if __name__ == "__main__":
    main()
