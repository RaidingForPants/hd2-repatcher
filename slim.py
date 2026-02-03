import struct
import os
import sys
from lz4 import block

def read_int(file):
    return int.from_bytes(file.read(4), "little")

def read_long(file):
    return int.from_bytes(file.read(8), "little")

def read_short(file):
    return int.from_bytes(file.read(2), "little")

def read_char(file):
    return int.from_bytes(file.read(1), "little")

def to_int(byte_data):
    return int.from_bytes(byte_data, "little")


# chunk type flags
CONTINUE = 0x04
START = 0x02
UNK = 0x01

# compression
UNCOMPRESSED = 0x00
COMPRESSED = 0x03

# package type
LEGACY = 3
BUNDLED = 2
DSAR = 1
UNKNOWN = 0

done_init = False
package_contents = {}
bundle_offsets = {}
file_handles = {}

# optimization stuff
START_OFFSET = 1
BUNDLE_INDEX = 2
ORIGINAL_ARCHIVE_OFFSET = 0
SIZE = 0
ENTRIES = 1

game_data_folder = ""

def slim_init(file_path: str):
    global game_data_folder
    game_data_folder = file_path
    if is_slim_version():
        init_bundle_mapping()

def is_slim_version():
    return not os.path.exists(os.path.join(game_data_folder, "9ba626afa44a3aa3"))
    
def get_file_handle(file_path):
    file_path = os.path.normpath(file_path)
    if file_path in file_handles:
        f = file_handles[file_path]
        f.seek(0)
        return f
    else:
        f = open(file_path, 'rb')
        file_handles[file_path] = f
        return f
        
def close_file_handles():
    global file_handles
    for f in file_handles.values():
        f.close()
    file_handles = {}

def decompress_dsar(file_path):

    # decompresses entire bundle file

    bundle = open(file_path, 'rb')

    num_chunks = num_chunks = struct.unpack("<8xI20x", bundle.read(0x20))[0] # num data chunks
    data = []
    file_count = 0
    chunk_data = struct.unpack(f"<{'QQIIBB6x'*num_chunks}", bundle.read(0x20*num_chunks))

    for i in range(num_chunks):
        uncompressed_offset, compressed_offset, uncompressed_size, compressed_size, compression_type, chunk_type = chunk_data[6*i:6*(i+1)]

        bundle.seek(compressed_offset)

        # read and decompress data
        temp_data = bundle.read(compressed_size)
        if compression_type == COMPRESSED:
            temp_data = block.decompress(temp_data, uncompressed_size=uncompressed_size)
        data.append(temp_data)
        
    bundle.close()

    return b"".join(data)

def get_resource_from_bundle(bundle_path: str, resource_file_offset: int):

    # returns resource from bundle file; resource determined by file offset in uncompressed bundle
    # handles resources split into multiple compressed chunks to return complete resource

    bundle = open(bundle_path, 'rb')
    num_chunks = struct.unpack("<8xI", bundle.read(12))[0] # num data chunks
    data = []
    
    global bundle_offsets
    chunk_num = bundle_offsets[os.path.basename(bundle_path)][resource_file_offset]

    while True:
        bundle.seek(0x20 + 0x20 * chunk_num)
        uncompressed_offset, compressed_offset, uncompressed_size, compressed_size, compression_type, chunk_type = struct.unpack("<QQIIBB6x", bundle.read(0x20))

        if chunk_type & START and len(data) > 0:
            bundle.close()
            return b"".join(data)

        # read and decompress data
        bundle.seek(compressed_offset)
        temp_data = bundle.read(compressed_size)
        if compression_type == COMPRESSED:
            temp_data = block.decompress(temp_data, uncompressed_size=uncompressed_size)
        data.append(temp_data)

        if chunk_num == num_chunks - 1:
            bundle.close()
            return b"".join(data)
            
        chunk_num += 1
        
    bundle.close()

class Package:

    def __init__(self):
        self.size = 0
        self.entries = []

class BundleEntry:

    def __init__(self):
        self.start_offset = self.bundle_index = self.original_archive_offset = 0
        
def get_resource_from_package(package_name: str, resource_file_offset: int, resource_size: int = 0):
    
    global package_contents

    package_name = os.path.basename(package_name)

    full_path = os.path.join(game_data_folder, package_name)

    package_type = 0

    if os.path.exists(full_path):
        with open(full_path, 'rb') as f:
            magic = int.from_bytes(f.read(4), "little")
            if magic == 1380012868: # compressed DSAR file
                package_type = DSAR
            else:
                package_type = LEGACY
    else:
        package_type = BUNDLED

    if package_type == BUNDLED:

        try:
            package = package_contents[package_name]
        except KeyError:
            # print(f"Unable to get package {package_name}")
            return bytearray()
            
        # how to convert file offset in package into file offset in bundle?
        
        for entry in reversed(package[ENTRIES]):
            if entry[ORIGINAL_ARCHIVE_OFFSET] <= resource_file_offset:
                return get_resource_from_bundle(os.path.join(game_data_folder, f"bundles.{entry[BUNDLE_INDEX]:02d}.nxa"), entry[START_OFFSET] + (resource_file_offset - entry[ORIGINAL_ARCHIVE_OFFSET]))

        return bytearray()

    elif package_type == DSAR:

        return get_resource_from_bundle(full_path, resource_file_offset)

    elif package_type == LEGACY:

        package_file = open(full_path, 'rb')
        bin_data = b""
        bin_data = package_file.read(12)
        magic, numTypes, numFiles = struct.unpack("<III", bin_data)
        if magic != 4026531857:
            package_file.close()
            return bytearray()

        package_file.seek(resource_file_offset)
        return package_file.read(resource_size)

    return bytearray()

def init_bundle_mapping():
    bundle_contents = decompress_dsar(os.path.join(game_data_folder, "bundles.nxa"))

    num_bundles, num_packages = struct.unpack_from("<II", bundle_contents, 0x0C)

    bundle_location = 0
    bundles = [[] for _ in range(num_bundles)]

    global package_contents
    package_contents = {}
    global bundle_offsets
    bundle_offsets = {}
    
    # get toc for each bundle:
    with os.scandir(game_data_folder) as it:
        for entry in it:
            filename = entry.name
            if entry.is_file() and (".patch" not in filename) and (os.path.splitext(filename)[1] in ["", ".stream", ".nxa", ".gpu_resources"]):
                bundle_offsets[filename] = {}
                with open(os.path.join(game_data_folder, filename), 'rb') as bundle:
                    num_chunks = struct.unpack("<8xI20x", bundle.read(0x20))[0] # num data chunks
                    uncompressed_offsets = struct.unpack(f"<{'Q24x'*num_chunks}", bundle.read(0x20*num_chunks))
                    for j, offset in enumerate(uncompressed_offsets):
                        bundle_offsets[filename][offset] = j
    '''
    for filename in os.listdir(game_data_folder):
        if (not os.path.isdir(os.path.join(game_data_folder, filename))) and (".patch" not in filename) and (os.path.splitext(filename)[1] in ["", ".stream", ".nxa", ".gpu_resources"]):
            bundle_offsets[filename] = {}
            with open(os.path.join(game_data_folder, filename), 'rb') as bundle:
                num_chunks = struct.unpack("<8xI20x", bundle.read(0x20))[0] # num data chunks
                uncompressed_offsets = struct.unpack(f"<{'Q24x'*num_chunks}", bundle.read(0x20*num_chunks))
                for j, offset in enumerate(uncompressed_offsets):
                    bundle_offsets[filename][offset] = j
    '''
    # check name of each package to find the right one
    package_info = struct.unpack_from(f"<{'QIII4x'*num_packages}", bundle_contents, 0x18)
    for n in range(num_packages):
        bundle_size, name_offset, items_count, items_offset = package_info[n*4:(n+1)*4]
        string_end = bundle_contents.find(b"\x00", name_offset)
        name = bundle_contents[name_offset:string_end].decode()
        # parse all BundleEntries for each package
        item_data = struct.unpack_from(f"<{'QI3xB'*items_count}", bundle_contents, items_offset)
        package_contents[name] = (bundle_size, [item_data[i*3:(i+1)*3] for i in range(items_count)])

def get_resources_from_bundle(bundle_path: str, start_offset: int, size: int):



    # returns resource from bundle file; resource determined by file offset in uncompressed bundle
    # handles resources split into multiple compressed chunks to return complete resource

    current_size = 0
    resources = []

    while current_size < size:
        resource = get_resource_from_bundle(bundle_path, start_offset + current_size)
        current_size += len(resource)
        resources.append(resource)
    return resources
    
def get_package_toc(package_name: str):
    global package_contents

    package_name = os.path.basename(package_name)

    full_path = os.path.join(game_data_folder, package_name)

    package_type = 0

    if os.path.exists(full_path):
        with open(full_path, 'rb') as f:
            magic = int.from_bytes(f.read(4), "little")
            if magic == 1380012868: # compressed DSAR file
                package_type = DSAR
            else:
                package_type = LEGACY
    else:
        package_type = BUNDLED

    if package_type == BUNDLED:

        try:
            package = package_contents[package_name]
        except KeyError:
            # print(f"Unable to get package {package_name}")
            return bytearray()

        return get_resource_from_bundle(os.path.join(game_data_folder, f"bundles.{package[ENTRIES][0][BUNDLE_INDEX]:02d}.nxa"), package[ENTRIES][0][START_OFFSET])

    elif package_type == DSAR:

        return get_resource_from_bundle(full_path, 0x00)

    elif package_type == LEGACY:

        package_file = open(full_path, 'rb')
        bin_data = b""
        bin_data = package_file.read(12)
        magic, numTypes, numFiles = struct.unpack("<III", bin_data)
        if magic != 4026531857:
            package_file.close()
            return bytearray()

        package_file.seek(0)
        return package_file.read(72 + numTypes*32 + numFiles*80)

    return bytearray()

def load_package(package_path: str):

    if not os.path.dirname(package_path):
        package_path = os.path.join(game_data_folder, package_path)

    package_type = 0

    if os.path.exists(package_path):
        with open(package_path, 'rb') as f:
            magic = int.from_bytes(f.read(4), "little")
            if magic == 1380012868: # compressed DSAR file
                package_type = DSAR
            else:
                package_type = LEGACY
    else:
        package_type = BUNDLED

    toc_data = bytearray()
    gpu_data = bytearray()
    stream_data = bytearray()

    if package_type == BUNDLED:
        content = reconstruct_package_from_bundles(package_path)
        if content: toc_data = content
        
        content = reconstruct_package_from_bundles(f"{package_path}.gpu_resources")
        if content: gpu_data = content

        content = reconstruct_package_from_bundles(f"{package_path}.stream")
        if content: stream_data = content

    elif package_type == DSAR:
        toc_data = decompress_dsar(package_path)
        if os.path.exists(package_path+".gpu_resources"):
            gpu_data = decompress_dsar(package_path+".gpu_resources")
        if os.path.exists(package_path+".stream"):
            stream_data = decompress_dsar(package_path+".stream")

    elif package_type == LEGACY:
        with open(package_path, 'rb') as f:
            toc_data = f.read()
        if os.path.exists(package_path+".gpu_resources"):
            with open(package_path+".gpu_resources", 'rb') as f:
                gpu_data = f.read()
        if os.path.exists(package_path+".stream"):
            with open(package_path+".stream", 'rb') as f:
                stream_data = f.read()
                
    close_file_handles()

    return toc_data, gpu_data, stream_data

def reconstruct_package_from_bundles(package_name: str):

    # reconstructs a package file from compressed bundle files
    package_name = os.path.basename(package_name)

    global package_contents

    try:
        package = package_contents[package_name]
    except KeyError:
        return bytearray()
    data = []
    package_data = bytearray(package[SIZE])
    for i, item in enumerate(package[ENTRIES]):
        try:
            item_size = package[ENTRIES][i+1][ORIGINAL_ARCHIVE_OFFSET] - item[ORIGINAL_ARCHIVE_OFFSET]
        except IndexError:
            item_size = package[SIZE] - item[ORIGINAL_ARCHIVE_OFFSET]
        resources = get_resources_from_bundle(os.path.join(game_data_folder, f"bundles.{item[BUNDLE_INDEX]:02d}.nxa"), item[START_OFFSET], item_size)
        combined_data = b"".join(resources)
        package_data[item[ORIGINAL_ARCHIVE_OFFSET]:item[ORIGINAL_ARCHIVE_OFFSET]+len(combined_data)] = combined_data
    return package_data

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: <game data folder> <package name> [<output folder>]")
        sys.exit()
    game_data_folder = sys.argv[1]
    package_name = sys.argv[2]
    if len(sys.argv) == 3:
        output_folder = "."
    else:
        output_folder = sys.argv[3]
    slim_init(game_data_folder)
    content = reconstruct_package_from_bundles(package_name)
    if content:
        with open(os.path.join(output_folder, package_name), 'wb') as f:
            f.write(content)

    content = reconstruct_package_from_bundles(f"{package_name}.gpu_resources")
    if content:
        with open(os.path.join(output_folder, f"{package_name}.gpu_resources"), 'wb') as f:
            f.write(content)

    content = reconstruct_package_from_bundles(f"{package_name}.stream")
    if content:
        with open(os.path.join(output_folder, f"{package_name}.stream"), 'wb') as f:
            f.write(content)
    close_file_handles()