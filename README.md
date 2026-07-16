# HD2 Repatcher

Repatches Helldivers II unit mods after a game update.

When Helldivers II updates, unit mod `.patch` files can go out of sync with the
game's unit data, causing them to fail to load. This tool scans a folder of
patch files, finds the ones containing unit resources, and updates those
resources in place using the current game data.

## Requirements

- Windows (reads the Helldivers II install directly; uses `tkinter` for the GUI)
- Python 3.10+ (only if running from source — see below)
- A Helldivers II install (specifically its `data` folder)

## Installation

### Option 1: Prebuilt executable

Download `hd2-repatcher.exe` (GUI, no console) or `hd2-repatcher-cli.exe`
(console/CLI) from the [Releases](../../releases) page. No Python required.

### Option 2: Run from source

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e .
```

## Usage

### GUI

Double-click `hd2-repatcher.exe`, or run:

```powershell
python update_unit_mods.py
```

You'll be prompted to select your Helldivers II `data` folder (once — it's
cached for future runs), then the folder containing the patch files you want
to fix.

### CLI

```powershell
hd2-repatcher-cli --game "C:\Program Files (x86)\Steam\steamapps\common\Helldivers 2\data" C:\path\to\mods\SomeMod
```

- `-g`/`--game PATH` — path to the Helldivers II `data` folder. Only needs to
  be passed once; it's cached for future runs.
- `PATCH_FOLDER [PATCH_FOLDER ...]` — one or more folders containing patch
  files to update.

Once the game path is cached, you can omit `-g`:

```powershell
hd2-repatcher-cli C:\path\to\mods\SomeMod C:\path\to\mods\AnotherMod
```

Exit code is non-zero if any corrupted patch files were found.

## Building

```powershell
./build.ps1
```

Builds both `dist\hd2-repatcher.exe` (windowed) and
`dist\hd2-repatcher-cli.exe` (console) via PyInstaller.
