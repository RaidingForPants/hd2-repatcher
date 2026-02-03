import os
import struct
import sys
import concurrent.futures
import tkinter as tk
from tkinter import filedialog
from tkinter import messagebox
from pathlib import Path
from slim import slim_init, is_slim_version, load_package, get_package_toc, get_resource_from_bundle, get_resource_from_package

root = tk.Tk()
root.withdraw()

game_resource_mapping = {}
game_resource_path = ""
directory = ""

print("fixing unit mods...")

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
        if not os.path.exists(os.path.join(d, "9ba626afa44a3aa3")) and not os.path.exists(os.path.join(d, "bundles.nxa")):
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
    
    toc_data = get_package_toc(file_path)
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
                #self.SearchArchives.append(tocs[index])
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
                #self.SearchArchives.append(tocs[index])
        executor.shutdown()

def update_patch_file(file_path: str):
    tocFile = open(file_path, 'r+b')
    magic, numTypes, numFiles, unknown, unk4Data = struct.unpack("<IIII56s", tocFile.read(72))
    tocFile.seek(tocFile.tell() + 32 * numTypes)
    tocStart = tocFile.tell()
    size_offset = 0
    tocFile.seek(0)
    stream = MemoryStream(tocFile.read())
    headers = []
    for n in range(numFiles):
        tocFile.seek(tocStart + n*80)
        tocHeader = TocHeader()
        tocHeader.from_bytes(tocFile.read(80))
        headers.append((tocHeader, tocStart+n*80))
    headers.sort(key=lambda h: h[0].toc_data_offset)
    for header in headers:
        header_data, header_offset = header
        stream.seek(header_offset + 16)
        stream.write(struct.pack("<Q", header_data.toc_data_offset + size_offset))
        if header_data.type_id == 16187218042980615487: # unit ID
            stream.seek(header_data.toc_data_offset + size_offset) # start of unit data in patch
            # do the updating
            version, lod_group_data, lod_group_size = get_data_from_original_file(header_data.file_id)
            stream.advance(0x2C)
            stream.write(version)
            lod_group_offset = stream.uint32_read()
            joint_list_offset = stream.uint32_read()
            group_size = joint_list_offset - lod_group_offset
            stream.seek(header_data.toc_data_offset + size_offset + lod_group_offset)
            size_difference = lod_group_size - group_size
            print(f"group size: {group_size}")
            print(f"lod group size: {lod_group_size}")
            print(f"size difference: {size_difference}")
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
                    print(offset)
                    stream.write((offset + size_difference).to_bytes(4, "little"))
            stream.seek(header_data.toc_data_offset + size_offset + lod_group_offset)
            stream.write(lod_group_data)
            size_offset += (size_difference)
    tocFile.seek(0)
    tocFile.write(stream.data)
    tocFile.close()

def update_all():
    futures = []
    executor = concurrent.futures.ThreadPoolExecutor()
    patches = []
    for root, dirs, files in os.walk(directory):
        for file in files:
            if "patch" in os.path.splitext(file)[1]:
                patches.append(os.path.join(root, file))
    if len(patches) == 0:
        messagebox.showwarning(message="No patch files found in folder!")
        return
    else:
        messagebox.showinfo(message=f"Updating {len(patches)} patch files...")
    for patch in patches:
        futures.append(executor.submit(update_patch_file, patch))
    for index, future in enumerate(futures):
        if future.result():
            pass
    executor.shutdown()
    messagebox.showinfo(message=f"Update Complete!")
    
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
    update_all()