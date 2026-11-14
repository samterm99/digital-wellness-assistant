# Digital Wellness Assistant

A small Windows tray app that reminds you to take care of your body while you work at the computer.
The interface is in Thai (a Thai guide is in [README_TH.md](README_TH.md)).

- **Eye rest** - the 20-20-20 rule: every 20 minutes look about 6 m away for 20 seconds (optional 20-second timer with a chime)
- **Stand up** - a reminder to walk and stretch (default every 45 minutes)
- **Posture** - a reminder to sit straight (default every 30 minutes)
- Runs quietly in the system tray, with a small control window for the settings
- Skips reminders while a full-screen video, game or presentation is running (can be switched off)
- Optional start with Windows, single-instance protection, per-user install (no administrator rights)

Requires Windows 10 or 11 (64-bit). The script edition needs Python 3.9+ (installed automatically via winget if missing).

## Install

**Script edition (works with Windows 11 Smart App Control, no .exe of ours):**
download the `DigitalWellnessAssistant-Script-<version>.zip` from the Releases page, extract it and double-click
`INSTALL.bat`. It uses the official Python (installed with winget if missing) and needs no administrator rights.
Uninstall with `UNINSTALL.bat`.

**Windows 10:** the unsigned installer `DigitalWellnessAssistant-Setup-<version>.exe` can also be used
(SmartScreen may warn: More info > Run anyway).

Settings and logs: `%LOCALAPPDATA%\DigitalWellnessAssistant` (installer) or
`%LOCALAPPDATA%\DigitalWellnessAssistant-Source` (script edition).

## Build from source

```powershell
# run from the repository root, with Python 3.13
python -m venv .venv
.venv\Scripts\python -m pip install pyinstaller
$env:PYTHONPATH = "src"
python -m unittest discover -s tests          # unit tests
python -m wellness                           # run the tray app from source
powershell -File packaging\build.ps1         # PyInstaller one-folder build (+ installer if Inno Setup 6 is installed)
```

Releases are built by GitHub Actions ([.github/workflows/release.yml](.github/workflows/release.yml)) from a version tag such as `v1.2.0`.

## Code signing

Releases are **not** code-signed. The project applied to the SignPath Foundation program and was not accepted yet
(it is too new to show the public-visibility signals the program requires), so no code-signing claim is made.
On Windows 11 with Smart App Control turned on, unsigned installers are blocked; use the script edition below.

## Privacy policy

See [PRIVACY.md](PRIVACY.md). In short: this program does not transfer any information to other networked systems. It has no network code, no telemetry and no accounts.

## License

[MIT](LICENSE)
