# Builds dist\DigitalWellnessAssistant (PyInstaller) and, if Inno Setup is found, the Setup.exe.
# Everything is written to $Out (default C:\Users\<you>\DWA-build), never into the source tree.
# Usage:  powershell -File packaging\build.ps1 [-Out D:\somewhere] [-Iscc path\to\ISCC.exe]
param([string]$Out = "$env:USERPROFILE\DWA-build", [string]$Iscc = "")
$ErrorActionPreference = "Stop"
$src = Split-Path $PSScriptRoot -Parent
$py = "$Out\venv\Scripts\python.exe"
if (-not (Test-Path $py)) {
    python -m venv "$Out\venv"
    & $py -m pip install --quiet pyinstaller
}
& $py -m PyInstaller --noconfirm --clean --windowed --onedir `
    --name DigitalWellnessAssistant --paths "$src\src" `
    --version-file "$src\packaging\version_info.txt" `
    --distpath "$Out\dist" --workpath "$Out\work" --specpath "$Out\work" `
    "$src\packaging\launcher.py"
if ($LASTEXITCODE) { throw "PyInstaller failed" }

if (-not $Iscc) {
    $Iscc = @("$Out\InnoSetup\ISCC.exe", "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe",
              "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe") | Where-Object { Test-Path $_ } | Select-Object -First 1
}
if (-not $Iscc) { Write-Warning "Inno Setup not found: only the exe folder was built."; exit 0 }
& $Iscc "/DSourceDir=$Out\dist\DigitalWellnessAssistant" "/DOutDir=$Out\installer" "$src\packaging\installer.iss"
if ($LASTEXITCODE) { throw "Inno Setup failed" }
