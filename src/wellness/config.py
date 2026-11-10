"""Load/save config.json and shared paths.

Environment overrides (used by automated tests only):
  DW_HOME      folder for config.json / state.json / logs
  DW_INSTANCE  suffix for window class + mutex names (isolates a test instance)
"""
import json
import logging
import logging.handlers
import os
import sys
import time
from pathlib import Path

FROZEN = bool(getattr(sys, "frozen", False))  # packaged with PyInstaller
PROJECT_DIR = Path(sys.executable).parent if FROZEN else Path(__file__).resolve().parents[2]
# Installed app: settings/state/logs live in the user's AppData, never in the install dir.
_DATA_DIR = (Path(os.environ.get("LOCALAPPDATA") or Path.home()) / "DigitalWellnessAssistant"
             if FROZEN else PROJECT_DIR)
BASE_DIR = Path(os.environ.get("DW_HOME") or _DATA_DIR)
CONFIG_PATH = BASE_DIR / "config.json"
STATE_PATH = BASE_DIR / "state.json"
LOG_DIR = BASE_DIR / "logs"
INSTANCE = os.environ.get("DW_INSTANCE", "")

DEFAULTS = {
    "eyes": {"enabled": True, "minutes": 20},
    "stand": {"enabled": True, "minutes": 45},
    "posture": {"enabled": True, "minutes": 30},
    "skip_fullscreen": True,
    "show_panel_on_startup": True,    # v1.1: open the control panel at Windows login
    "eye_break_sound": True,          # chime when the optional 20 s eye-break timer ends
}

MESSAGES = {
    "eyes": ("พักสายตา",
             "มองไกลออกไปประมาณ 6 เมตร นาน 20 วินาที แล้วกะพริบตาช้าๆ"),
    "stand": ("ลุกขึ้นเดิน",
              "นั่งนานแล้ว ลุกขึ้นยืดเส้นยืดสายหรือเดินสัก 2-3 นาที"),
    "posture": ("ปรับท่านั่ง",
                "หลังตรง ไหล่ผ่อนคลาย จอระดับสายตา เท้าวางราบกับพื้น"),
}

LABELS = {"eyes": "พักสายตา", "stand": "ลุกขึ้นเดิน", "posture": "ปรับท่านั่ง"}


def _clean(raw):
    """Merge raw JSON over defaults and coerce to safe values."""
    cfg = json.loads(json.dumps(DEFAULTS))
    if not isinstance(raw, dict):
        return cfg
    for key in MESSAGES:
        item = raw.get(key)
        if isinstance(item, dict):
            cfg[key]["enabled"] = bool(item.get("enabled", True))
            try:
                cfg[key]["minutes"] = min(480, max(1, int(item.get("minutes"))))
            except (TypeError, ValueError):
                pass
    for flag in ("skip_fullscreen", "show_panel_on_startup", "eye_break_sound"):
        cfg[flag] = bool(raw.get(flag, DEFAULTS[flag]))
    return cfg


def panel_wanted(cfg, startup_arg, since_logon):
    """Should start.bat's --auto-panel open the control panel?

    `start.bat startup` (explicit startup argument) is authoritative. Without it
    (e.g. an older Startup shortcut with no argument) fall back to "the desktop
    shell started < 120 s ago" only to honour the preference; a manual launch
    shortly after login then still skips the panel, so the shortcut should
    pass `startup`. Unknown logon time => open the panel.
    """
    if cfg["show_panel_on_startup"]:
        return True
    if startup_arg:
        return False
    return not (since_logon is not None and since_logon < 120)


def load(path=None):
    try:
        with open(path or CONFIG_PATH, encoding="utf-8") as f:
            return _clean(json.load(f))
    except (OSError, ValueError):
        return _clean(None)


def _atomic_write(path, data):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    tmp = str(path) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    # On Windows os.replace fails while another process has the target open
    # (e.g. the control panel reading it), so retry briefly.
    for attempt in range(10):
        try:
            os.replace(tmp, path)
            return
        except PermissionError:
            if attempt == 9:
                raise
            time.sleep(0.03)


def save(cfg, path=None):
    _atomic_write(path or CONFIG_PATH, _clean(cfg))


def write_state(state, path=None):
    _atomic_write(path or STATE_PATH, state)


def read_state(path=None):
    try:
        with open(path or STATE_PATH, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def mtime(path=None):
    try:
        return os.path.getmtime(path or CONFIG_PATH)
    except OSError:
        return 0.0


def setup_logging():
    """Small rotating log file (max ~200 KB total)."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    h = logging.handlers.RotatingFileHandler(
        LOG_DIR / "app.log", maxBytes=100_000, backupCount=1, encoding="utf-8")
    h.setFormatter(logging.Formatter("%(asctime)s %(message)s"))
    log = logging.getLogger("wellness")
    log.setLevel(logging.INFO)
    log.addHandler(h)
    return log
