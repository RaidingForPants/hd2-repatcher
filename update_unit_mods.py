import argparse
import os
import struct
import sys
import concurrent.futures
from pathlib import Path
from slim import slim_init, is_slim_version, load_package, get_package_toc, get_resource_from_bundle, get_resource_from_package
from settings import get_cached_game_data_path, set_cached_game_data_path

game_resource_mapping = {}
game_resource_path = ""
directory = ""

UPDATE_SUCCESS = 0
NO_UNIT_FILES = 1
CORRUPTED_FILE = 2

def is_valid_game_data_path(path: str) -> bool:
    return os.path.isdir(path) and (
        os.path.exists(os.path.join(path, "9ba626afa44a3aa3")) or
        os.path.exists(os.path.join(path, "bundles.nxa"))
    )

def select_folder():
    from tkinter import filedialog, messagebox
    d = filedialog.askdirectory(title="Select folder containing patch files")
    if d:
        if not os.path.exists(d):
            messagebox.showwarning(message="No valid folder selected!")
            return False
    else:
        return None
    return d

def select_data_folder():
    from tkinter import filedialog, messagebox
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

class TocHeader:

    def __init__(self):
        pass
        
    def from_bytes(self, bytes):
        (self.file_id,
        self.type_id,
        self.toc_data_offset,
        self.stream_file_offset,
        self.gpu_resource_offset,
        self.unknown1,
        self.unknown2,
        self.toc_data_size,
        self.stream_size,
        self.gpu_resource_size,
        self.unknown3,
        self.unknown4,
        self.entry_index) = struct.unpack("<QQQQQQQIIIIII", bytes)
        
    def get_data(self):
        return (struct.pack("<QQQQQQQIIIIII",
            self.file_id,
            self.type_id,
            self.toc_data_offset,
            self.stream_file_offset,
            self.gpu_resource_offset,
            self.unknown1,
            self.unknown2,
            self.toc_data_size,
            self.stream_size,
            self.gpu_resource_size,
            self.unknown3,
            self.unknown4,
            self.entry_index))
            
class MemoryStream:
    '''
    Modified from https://github.com/kboykboy2/io_scene_helldivers2 with permission from kboykboy
    '''
    def __init__(self, Data=b"", io_mode = "read"):
        self.location = 0
        self.data = bytearray(Data)
        self.io_mode = io_mode
        self.endian = "<"

    def open(self, Data, io_mode = "read"): # Open Stream
        self.data = bytearray(Data)
        self.io_mode = io_mode

    def set_read_mode(self):
        self.io_mode = "read"

    def set_write_mode(self):
        self.io_mode = "write"

    def is_reading(self):
        return self.io_mode == "read"

    def is_writing(self):
        return self.io_mode == "write"

    def seek(self, location): # Go To Position In Stream
        self.location = location
        if self.location > len(self.data):
            missing_bytes = self.location - len(self.data)
            self.data += bytearray(missing_bytes)

    def tell(self): # Get Position In Stream
        return self.location

    def read(self, length=-1): # read Bytes From Stream
        if length == -1:
            length = len(self.data) - self.location
        if self.location + length > len(self.data):
            raise Exception("reading past end of stream")

        newData = self.data[self.location:self.location+length]
        self.location += length
        return bytearray(newData)

    def advance(self, offset):
        self.location += offset
        if self.location < 0:
            self.location = 0
        if self.location > len(self.data):
            missing_bytes = self.location - len(self.data)
            self.data += bytearray(missing_bytes)
            
    def insert(self, length):
        self.data[self.location:self.location] = bytearray(length)
        
    def delete(self, length):
        self.data[self.location:self.location+length] = b''

    def write(self, bytes): # Write Bytes To Stream
        length = len(bytes)
        if self.location + length > len(self.data):
            missing_bytes = (self.location + length) - len(self.data)
            self.data += bytearray(missing_bytes)
        self.data[self.location:self.location+length] = bytearray(bytes)
        self.location += length

    def read_format(self, format, size):
        format = self.endian+format
        return struct.unpack(format, self.read(size))[0]

    def bytes(self, value, size = -1):
        if size == -1:
            size = len(value)
        if len(value) != size:
            value = bytearray(size)

        if self.is_reading():
            return bytearray(self.read(size))
        elif self.is_writing():
            self.write(value)
            return bytearray(value)
        return value

    def int8_read(self):
        return self.read_format('b', 1)

    def uint8_read(self):
        return self.read_format('B', 1)

    def int16_read(self):
        return self.read_format('h', 2)

    def uint16_read(self):
        return self.read_format('H', 2)

    def int32_read(self):
        return self.read_format('i', 4)

    def uint32_read(self):
        return self.read_format('I', 4)

    def int64_read(self):
        return self.read_format('q', 8)

    def uint64_read(self):
        return self.read_format('Q', 8)
        
    def float32_read(self):
        return self.read_format('f', 4)

def get_data_from_original_file(unit_id: int):
    if is_slim_version():
        unit_data = get_resource_from_package(*game_resource_mapping[unit_id])
        unit_version = unit_data[0x2C:0x30]
        lod_group_offset, joint_list_offset = struct.unpack_from("<II", unit_data, 0x30)
        lod_group_size = joint_list_offset - lod_group_offset
        lod_group_data = unit_data[lod_group_offset:lod_group_offset + lod_group_size]
        return unit_version, lod_group_data, lod_group_size
    else:
        file_path = os.path.join(game_resource_path, game_resource_mapping[unit_id][0])
        data_offset = game_resource_mapping[unit_id][1]
        toc_file = open(file_path, 'r+b')
        toc_file.seek(data_offset + 0x2C)
        unit_version = toc_file.read(4)
        lod_group_offset, joint_list_offset = struct.unpack("<II", toc_file.read(8))
        lod_group_size = joint_list_offset - lod_group_offset
        toc_file.seek(data_offset + lod_group_offset)
        lod_group_data = toc_file.read(lod_group_size)
        return unit_version, lod_group_data, lod_group_size
    
def load_resources_from_file(file_path: str):
    global game_resource_mapping
    try:
        toc_data = get_package_toc(file_path)
    except KeyError as e:
        return
    if len(toc_data) == 0:
        return
    tocFile = MemoryStream(toc_data)
    magic, numTypes, numFiles, unknown, unk4Data = struct.unpack("<IIII56s", tocFile.read(72))
    tocFile.seek(tocFile.tell() + 32 * numTypes)
    tocStart = tocFile.tell()
    size_offset = 0
    tocFile.seek(0)
    headers = []
    for n in range(numFiles):
        tocFile.seek(tocStart + n*80)
        tocHeader = TocHeader()
        try:
            tocHeader.from_bytes(tocFile.read(80))
        except:
            print(file_path)
        if tocHeader.type_id == 16187218042980615487:
            game_resource_mapping[tocHeader.file_id] = (os.path.basename(file_path), tocHeader.toc_data_offset, tocHeader.toc_data_size)
    
def load_game_resources():
    global game_resource_mapping
    game_resource_mapping = {}
    
    if is_slim_version():
        futures = []
        executor = concurrent.futures.ThreadPoolExecutor()
        bundle_database = open(os.path.join(game_resource_path, "bundle_database.data"), 'rb')
        bundle_database_data = bundle_database.read()
        num_packages = int.from_bytes(bundle_database_data[4:8], "little")
        for i in range(num_packages):
            offset = 0x10 + 0x33 * i
            name = bundle_database_data[offset:offset+0x33].decode().split("\x17")[0]
            futures.append(executor.submit(load_resources_from_file, os.path.join(game_resource_path, name)))
        for index, future in enumerate(futures):
            if future.result():
                pass
        executor.shutdown()
    else:
        futures = []
        tocs = []
        executor = concurrent.futures.ThreadPoolExecutor()
        for root, dirs, files in os.walk(Path(game_resource_path)):
            for name in files:
                if Path(name).suffix == "":
                    futures.append(executor.submit(load_resources_from_file, os.path.join(root, name)))
        for index, future in enumerate(futures):
            if future.result():
                pass
        executor.shutdown()
        
def update_patch_file(file_path: str):
    file_size = os.path.getsize(file_path)
    total_resources = 0
    tocFile = open(file_path, 'r+b')
    magic, numTypes, numFiles, unknown, unk4Data = struct.unpack("<IIII56s", tocFile.read(72))
    resource_type = 0
    for _ in range(numTypes):
        tocFile.seek(tocFile.tell()+8)
        resource_type, num_resources = struct.unpack("<QQ", tocFile.read(16))
        total_resources += num_resources
        type_offset = tocFile.tell()-8
        tocFile.seek(tocFile.tell()+8)
        if resource_type < 2**32:
            return (CORRUPTED_FILE, file_path)
        if resource_type == 16187218042980615487:
            break
    if resource_type != 16187218042980615487: # no units in this patch
        return (NO_UNIT_FILES, file_path)
    if total_resources < numFiles:
        return (CORRUPTED_FILE, file_path)
    tocStart = 72 + 32 * numTypes
    size_offset = 0
    tocFile.seek(0)
    stream = MemoryStream(tocFile.read())
    headers = []
    for n in range(numFiles):
        tocFile.seek(tocStart + n*80)
        tocHeader = TocHeader()
        tocHeader.from_bytes(tocFile.read(80))
        if tocHeader.toc_data_offset > file_size:
            return (CORRUPTED_FILE, file_path)
        headers.append([tocHeader, tocStart+n*80])
    stream.seek(tocStart)
    header_offset_adjustment = 0
    temp_headers = []
    for header in headers:
        header[1] += header_offset_adjustment
        header_data, header_offset = header
        if header_data.file_id not in game_resource_mapping and header_data.type_id == 16187218042980615487:
            stream.seek(header_offset)
            stream.delete(80)
            numFiles -= 1
            num_resources -= 1
            header_offset_adjustment -= 80
        else:
            temp_headers.append(header)
    headers = temp_headers
    for header in headers:
        header[0].toc_data_offset += header_offset_adjustment
    headers.sort(key=lambda h: h[0].toc_data_offset)
    stream.seek(8)
    stream.write(struct.pack("<I", numFiles))
    stream.seek(type_offset)
    stream.write(struct.pack("<Q", num_resources))
    for header in headers:
        header_data, header_offset = header
        stream.seek(header_offset + 16)
        stream.write(struct.pack("<Q", header_data.toc_data_offset + size_offset))
        if header_data.type_id == 16187218042980615487 and header_data.file_id in game_resource_mapping: # unit ID
            stream.seek(header_data.toc_data_offset + size_offset) # start of unit data in patch
            # do the updating
            version, lod_group_data, lod_group_size = get_data_from_original_file(header_data.file_id)

            unit_start = stream.tell()
            
            stream.seek(unit_start + 0x2C)
            v = stream.uint32_read()
            if (v < 0xA4CD36):
                stream.seek(unit_start + 0x5C)
                layout_list_offset = stream.uint32_read()
                stream.seek(unit_start + layout_list_offset)
                num_layouts = stream.uint32_read()
                layout_offsets = [stream.uint32_read() for _ in range(num_layouts)]
                for layout_offset in layout_offsets:
                    stream.seek(unit_start + layout_list_offset + layout_offset)
                    stream.advance(8)
                    for _ in range(16):
                        item_type = stream.uint32_read()
                        item_format = stream.uint32_read()
                        if item_format > 16:
                            stream.advance(-4)
                            stream.write(struct.pack("<I", item_format+4))
                        stream.advance(12)
            stream.seek(unit_start)
            
            stream.advance(0x2C)
            stream.write(version)
            lod_group_offset = stream.uint32_read()
            joint_list_offset = stream.uint32_read()
            group_size = joint_list_offset - lod_group_offset
            stream.seek(header_data.toc_data_offset + size_offset + lod_group_offset)
            size_difference = lod_group_size - group_size
            if size_difference > 0:
                stream.insert(size_difference)
            else:
                stream.delete(-size_difference)
            # update offsets
            stream.seek(header_data.toc_data_offset + size_offset + 0x34)
            for _ in range(16):
                offset = stream.uint32_read()
                if offset != 0 and offset > lod_group_offset:
                    stream.advance(-4)
                    stream.write((offset + size_difference).to_bytes(4, "little"))
            stream.seek(header_data.toc_data_offset + size_offset + lod_group_offset)
            stream.write(lod_group_data)
            size_offset += (size_difference)
    tocFile.seek(0)
    tocFile.write(stream.data)
    tocFile.close()
    return (UPDATE_SUCCESS, file_path)
    
def find_patch_files(directory: str):
    patches = []
    for root, dirs, files in os.walk(directory):
        for file in files:
            if "patch" in os.path.splitext(file)[1]:
                patches.append(os.path.join(root, file))
    return patches

def process_patch_files(patches: list) -> dict:
    result = {"updated": [], "no_units": [], "corrupted_files": []}
    futures = []
    executor = concurrent.futures.ThreadPoolExecutor()
    for patch in patches:
        futures.append(executor.submit(update_patch_file, patch))
    for future in futures:
        code, path = future.result()
        if code == CORRUPTED_FILE:
            result["corrupted_files"].append(path)
        elif code == NO_UNIT_FILES:
            result["no_units"].append(path)
        else:
            result["updated"].append(path)
    executor.shutdown()
    return result

def process_patch_folder(directory: str) -> dict:
    patches = find_patch_files(directory)
    result = process_patch_files(patches)
    result["directory"] = directory
    result["patches_found"] = len(patches)
    return result

def update_all_gui(directory: str):
    from tkinter import messagebox
    patches = find_patch_files(directory)
    if len(patches) == 0:
        messagebox.showwarning(message="No patch files found in folder!")
        return
    messagebox.showinfo(message=f"Checking {len(patches)} patch files...")
    result = process_patch_files(patches)
    patch_files_updated = len(result["updated"])
    if len(result["corrupted_files"]) > 0:
        m = f"Found {len(result['corrupted_files'])} corrupted patch file(s)!"
        for name in result["corrupted_files"]:
            m += f"\n{os.path.normpath(name)}"
        messagebox.showerror(message=m)
    m = f"Update Complete!\nUpdated {patch_files_updated} patch file(s) that contained unit resources."
    if len(result["no_units"]) > 0:
        m += f"\n{len(result['no_units'])} patch file(s) did not contain any unit resources and were skipped."
    messagebox.showinfo(message=m)

def print_cli_result(directory: str, result: dict):
    print(f"\n{directory}")
    if result["patches_found"] == 0:
        print("  No patch files found.")
        return
    print(f"  Checked {result['patches_found']} patch file(s)")
    print(f"  Updated {len(result['updated'])} patch file(s) containing unit resources")
    if result["no_units"]:
        print(f"  Skipped {len(result['no_units'])} patch file(s) with no unit resources")
    if result["corrupted_files"]:
        print(f"  Found {len(result['corrupted_files'])} corrupted patch file(s):", file=sys.stderr)
        for name in result["corrupted_files"]:
            print(f"    {os.path.normpath(name)}", file=sys.stderr)

def run_cli(game_path, patch_dirs):
    global game_resource_path
    if game_path is None:
        cached = get_cached_game_data_path()
        if cached and is_valid_game_data_path(cached):
            game_path = cached
        else:
            print("error: no game data directory configured; pass -g/--game <path>", file=sys.stderr)
            sys.exit(1)

    game_resource_path = game_path
    print(f"Loading game resources from: {game_resource_path}")
    slim_init(game_resource_path)
    load_game_resources()

    exit_code = 0
    for patch_dir in patch_dirs:
        patch_dir = os.path.abspath(patch_dir)
        if not os.path.isdir(patch_dir):
            print(f"error: '{patch_dir}' is not a directory", file=sys.stderr)
            exit_code = 1
            continue
        result = process_patch_folder(patch_dir)
        print_cli_result(patch_dir, result)
        if result["corrupted_files"]:
            exit_code = 1
    sys.exit(exit_code)

def run_gui():
    global game_resource_path, directory
    import tkinter as tk
    from tkinter import messagebox

    root = tk.Tk()
    root.withdraw()

    print("fixing unit mods...")

    cached = get_cached_game_data_path()
    if cached and is_valid_game_data_path(cached):
        game_resource_path = cached

    while True:

        if not game_resource_path:
            game_resource_path = select_data_folder()
            print(game_resource_path)
            if game_resource_path == False: continue
            if game_resource_path is None:
                do_exit = messagebox.askyesnocancel(message="Would you like to quit?")
                if do_exit:
                    sys.exit()
                else:
                    continue
            set_cached_game_data_path(os.path.abspath(game_resource_path))
            slim_init(game_resource_path)
            load_game_resources()

        directory = select_folder()
        if directory == False: continue
        if directory is None:
            do_exit = messagebox.askyesnocancel(message="Would you like to quit?")
            if do_exit:
                sys.exit()
            else:
                continue
        update_all_gui(directory)

def parse_args():
    parser = argparse.ArgumentParser(description="Update unit resources in Helldivers II patch files.")
    parser.add_argument("-g", "--game", metavar="PATH",
                         help="path to the Helldivers II game data folder; also cached for future runs")
    parser.add_argument("patches", nargs="*", metavar="PATCH_FOLDER",
                         help="folder(s) containing patch files to update")
    return parser.parse_args()

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
                  f"(expected to find `9ba626afa44a3aa3` or `bundles.nxa` inside it)", file=sys.stderr)
            sys.exit(1)
        set_cached_game_data_path(game_path)
        print(f"Game data directory set to: {game_path}")

    if args.patches:
        run_cli(game_path, args.patches)
    elif args.game:
        return
    else:
        run_gui()

if __name__ == "__main__":
    main()