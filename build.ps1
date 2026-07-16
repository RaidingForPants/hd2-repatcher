# Builds a standalone hd2-repatcher.exe into dist\ (gitignored).
# Usage: ./build.ps1
$ErrorActionPreference = "Stop"

if (-not (Test-Path .venv)) {
    python -m venv .venv
}
. .venv\Scripts\Activate.ps1

pip install -e ".[build]" -q

pyinstaller --onefile --name hd2-repatcher --clean --specpath build update_unit_mods.py

Write-Host "Build complete: dist\hd2-repatcher.exe"
