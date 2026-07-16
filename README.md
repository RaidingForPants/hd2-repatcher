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

### Why two builds?

`hd2-repatcher.exe` is built by PyInstaller in **windowed** mode: it has no
console and no stdout/stderr at all, so double-clicking it (or dragging a mod
folder onto it) never pops up a window beyond its own dialogs.

`hd2-repatcher-cli.exe` is built in **console** mode instead. Run from an
already-open terminal, it just prints to that terminal like any other console
program. But double-click it (or drag a folder onto it), and since there's no
terminal for it to attach to, Windows pops up a brand new console window to
show the result.

If you don't need CLI usage or drag-and-drop feedback, download the regular
windowed `hd2-repatcher.exe` so it doesn't pop up a console at you.

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

Once the game data path is cached, you can also just drag and drop one or more
mod folders directly onto `hd2-repatcher-cli.exe` (or a shortcut to it) —
Windows passes the dropped folder(s) as arguments, so the tool processes them
immediately instead of prompting, with a console window showing the result
(see [Why two builds?](#why-two-builds) for why this only pops up for the CLI
build).

Once the game path is cached, you can omit `-g`:

```powershell
hd2-repatcher-cli C:\path\to\mods\SomeMod C:\path\to\mods\AnotherMod
```

Exit code is non-zero if any corrupted patch files were found.

If you're integrating this into a mod manager, always pass the game data path
explicitly via `-g`/`--game` on every invocation rather than relying on the
cache — the cache is a convenience for interactive/manual use, and a mod
manager shouldn't assume a previous run (by itself or another tool) already
set it.

## Testing

There's no automated end-to-end test against real game files (the game data
isn't available in CI), so changes that touch the patching logic should be
verified manually against a mod that's actually broken by a game update:

1. Find a mod that's known to break after updates, e.g.
   [Invisible supply pack](https://www.nexusmods.com/helldivers2/mods/7308?tab=files),
   and download an **older** file version — recent-enough game updates should
   have desynced it from current unit data.
2. Install it with a mod manager (or manually) and confirm in-game that it's
   broken (fails to load / crashes / doesn't apply).
3. Run it through the repatcher (GUI, drag-and-drop, or CLI) and confirm it
   reports the patch as updated.
4. Redeploy the mod and confirm it now loads correctly in-game.

## Building

```powershell
./build.ps1
```

Builds both `dist\hd2-repatcher.exe` (windowed) and
`dist\hd2-repatcher-cli.exe` (console) via PyInstaller.
