# Digital Wellness Assistant

A small Windows tray app that reminds you to take care of your body while you work at the computer.
The interface is in Thai (a Thai guide is in [README_TH.md](README_TH.md)).

- **Eye rest** - the 20-20-20 rule: every 20 minutes look about 6 m away for 20 seconds (optional 20-second timer with a chime)
- **Stand up** - a reminder to walk and stretch (default every 45 minutes)
- **Posture** - a reminder to sit straight (default every 30 minutes)
- Runs quietly in the system tray, with a small control window for the settings
- Skips reminders while a full-screen video, game or presentation is running (can be switched off)
- Optional start with Windows, single-instance protection, per-user install (no administrator rights)

Requires Windows 10 or 11 (64-bit). Python is **not** needed on the user's PC.

## Install

1. Open the [Releases](../../releases) page and download `DigitalWellnessAssistant-Setup-<version>.exe`.
2. Run it. It installs for the current user only and can add the app to Windows start-up.
3. Settings and logs are stored in `%LOCALAPPDATA%\DigitalWellnessAssistant`.

Uninstall from Windows Settings > Apps.

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

## Code signing policy

Free code signing provided by [SignPath.io](https://about.signpath.io/), certificate by [SignPath Foundation](https://signpath.org/).

- Signed files are built **only from this repository**, by the automated GitHub Actions workflow above, running on GitHub-hosted runners. Every release signing request is approved manually.
- What is signed: `DigitalWellnessAssistant.exe` and the installer `DigitalWellnessAssistant-Setup-<version>.exe`. Third-party runtime files bundled by PyInstaller are the unmodified upstream files.
- Team roles:
  - Authors / committers: [samterm99](https://github.com/samterm99)
  - Reviewers: [samterm99](https://github.com/samterm99)
  - Approvers: [samterm99](https://github.com/samterm99)
- All team members use multi-factor authentication on GitHub and SignPath.

### Privacy policy

See [PRIVACY.md](PRIVACY.md). In short: this program does not transfer any information to other networked systems. It has no network code, no telemetry and no accounts.

## License

[MIT](LICENSE)
