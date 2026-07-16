# Builds standalone executables into dist\ (gitignored).
# Usage: ./build.ps1
$ErrorActionPreference = "Stop"

if (-not (Test-Path .venv)) {
    python -m venv .venv
}
. .venv\Scripts\Activate.ps1

pip install -e ".[build]" -q

# GUI build: no console window, for double-click use
pyinstaller --onefile --windowed --name hd2-repatcher --clean --specpath build update_unit_mods.py

# CLI build: normal console app, for use from a terminal
pyinstaller --onefile --name hd2-repatcher-cli --clean --specpath build update_unit_mods.py

Write-Host "Build complete:"
Write-Host "  dist\hd2-repatcher.exe      (GUI, double-click)"
Write-Host "  dist\hd2-repatcher-cli.exe  (CLI, run from a terminal)"
