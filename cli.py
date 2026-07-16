import argparse
import os
import sys

from settings import get_cached_game_data_path, set_cached_game_data_path
from update_unit_mods import (
    LEGACY_MARKER_FILE,
    SLIM_MARKER_FILE,
    PatchResult,
    init_game_resources,
    is_valid_game_data_path,
    process_patch_folder,
)

def print_cli_result(directory: str, result: PatchResult):
    print(f"\n{directory}")
    if result.patches_found == 0:
        print("  No patch files found.")
        return
    print(f"  Checked {result.patches_found} patch file(s)")
    print(f"  Updated {len(result.updated)} patch file(s) containing unit resources")
    if result.no_units:
        print(f"  Skipped {len(result.no_units)} patch file(s) with no unit resources")
    if result.corrupted_files:
        print(f"  Found {len(result.corrupted_files)} corrupted patch file(s):", file=sys.stderr)
        for name in result.corrupted_files:
            print(f"    {os.path.normpath(name)}", file=sys.stderr)

def pause_if_owns_console():
    '''
    When the console build is launched by double-click or drag-and-drop,
    Windows spawns a fresh console that closes the instant this process
    exits, taking the output with it. If this process is the console's only
    occupant, hold the window open so the result can be read. Run from an
    existing terminal (or in the windowed build, which has no console at
    all), this is a no-op.
    '''
    if os.name != "nt":
        return
    import ctypes
    process_ids = (ctypes.c_uint32 * 2)()
    if ctypes.windll.kernel32.GetConsoleProcessList(process_ids, 2) != 1:
        return
    if sys.stdin is None or not sys.stdin.isatty():
        return
    try:
        input("\nPress Enter to exit...")
    except EOFError:
        pass

def exit_cli(code):
    pause_if_owns_console()
    sys.exit(code)

def run_cli(game_path, patch_dirs):
    if game_path is None:
        cached = get_cached_game_data_path()
        if cached and is_valid_game_data_path(cached):
            game_path = cached
        else:
            print("error: no game data directory configured; pass -g/--game <path>", file=sys.stderr)
            exit_cli(1)

    print(f"Loading game resources from: {game_path}")
    init_game_resources(game_path)

    exit_code = 0
    for patch_dir in patch_dirs:
        patch_dir = os.path.abspath(patch_dir)
        if not os.path.isdir(patch_dir):
            print(f"error: '{patch_dir}' is not a directory", file=sys.stderr)
            exit_code = 1
            continue
        result = process_patch_folder(patch_dir)
        print_cli_result(patch_dir, result)
        if result.corrupted_files:
            exit_code = 1
    exit_cli(exit_code)

def parse_args():
    parser = argparse.ArgumentParser(description="Update unit resources in Helldivers II patch files.")
    parser.add_argument("-g", "--game", metavar="PATH",
                         help="path to the Helldivers II game data folder; also cached for future runs")
    parser.add_argument("patches", nargs="*", metavar="PATCH_FOLDER",
                         help="folder(s) containing patch files to update")
    args = parser.parse_args()
    if args.game and not args.patches:
        parser.error("at least one PATCH_FOLDER is required with -g/--game")
    return args

def setup_console_io():
    '''
    The windowed build has no console, so sys.stdout/stderr are None; guard
    stray print() calls from crashing it. The console build already has real
    stdio and this is a no-op there.
    '''
    if sys.stdout is None:
        sys.stdout = open(os.devnull, "w")
    if sys.stderr is None:
        sys.stderr = open(os.devnull, "w")

def main():
    setup_console_io()
    args = parse_args()

    game_path = None
    if args.game:
        game_path = os.path.abspath(args.game)
        if not is_valid_game_data_path(game_path):
            print(f"error: '{args.game}' does not look like a Helldivers II data folder "
                  f"(expected to find `{LEGACY_MARKER_FILE}` or `{SLIM_MARKER_FILE}` inside it)", file=sys.stderr)
            exit_cli(1)
        set_cached_game_data_path(game_path)
        print(f"Game data directory set to: {game_path}")

    if args.patches:
        run_cli(game_path, args.patches)
    else:
        from gui import run_gui
        run_gui()

if __name__ == "__main__":
    main()
