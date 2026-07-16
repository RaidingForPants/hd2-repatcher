'''
Tkinter GUI: folder-picker dialogs around the patching engine in
update_unit_mods. Only imported (by cli.main) when the tool is started with
no arguments, so CLI runs never load tkinter.
'''
import os
import sys
import tkinter as tk
from tkinter import filedialog, messagebox

from settings import get_cached_game_data_path, set_cached_game_data_path
from update_unit_mods import init_game_resources, is_valid_game_data_path, process_patch_folder

def select_folder():
    d = filedialog.askdirectory(title="Select folder containing patch files")
    if d:
        if not os.path.exists(d):
            messagebox.showwarning(message="No valid folder selected!")
            return False
    else:
        return None
    return d

def select_data_folder():
    d = filedialog.askdirectory(title="Select folder containing game data")
    if d:
        if not os.path.exists(d):
            messagebox.showwarning(message="No valid folder selected!")
            return False
        if not is_valid_game_data_path(d):
            messagebox.showwarning(message="Unable to find Helldivers II game data at this location; make sure you select the `data` folder in your Helldivers II install")
            return False
    else:
        return None
    return d

def update_all_gui(directory: str):
    result = process_patch_folder(directory)
    if result.patches_found == 0:
        messagebox.showwarning(message="No patch files found in folder!")
        return
    if result.corrupted_files:
        m = f"Found {len(result.corrupted_files)} corrupted patch file(s)!"
        for name in result.corrupted_files:
            m += f"\n{os.path.normpath(name)}"
        messagebox.showerror(message=m)
    m = (f"Update Complete!\nChecked {result.patches_found} patch file(s).\n"
         f"Updated {len(result.updated)} patch file(s) that contained unit resources.")
    if result.no_units:
        m += f"\n{len(result.no_units)} patch file(s) did not contain any unit resources and were skipped."
    messagebox.showinfo(message=m)

def run_gui():
    root = tk.Tk()
    root.withdraw()

    print("fixing unit mods...")

    game_data_path = ""
    cached = get_cached_game_data_path()
    if cached and is_valid_game_data_path(cached):
        game_data_path = cached
        init_game_resources(game_data_path)

    while True:

        if not game_data_path:
            selection = select_data_folder()
            if selection is False:
                continue
            if selection is None:
                if messagebox.askyesnocancel(message="Would you like to quit?"):
                    sys.exit()
                continue
            game_data_path = os.path.abspath(selection)
            set_cached_game_data_path(game_data_path)
            init_game_resources(game_data_path)

        directory = select_folder()
        if directory is False:
            continue
        if directory is None:
            if messagebox.askyesnocancel(message="Would you like to quit?"):
                sys.exit()
            continue
        update_all_gui(directory)
