import os.path
import shutil
import tarfile

COMPRESSION_MODE = 'gz'

def pack_dirs(filename, dirs):
    try:
        with tarfile.open(filename, 'w:' + COMPRESSION_MODE) as f:
            for d in dirs:
                f.add(d)
    except Exception as e:
        print(e)

def pack(filename):
    pack_dirs(filename, ['accounts', 'data'])

def pack_data(filename):
    pack_dirs(filename, ['data'])

def unpack(filename):
    try:
        with tarfile.open(filename, 'r:' + COMPRESSION_MODE) as f:
            if 'data' in f.getnames() and os.path.isdir('data'):
                shutil.rmtree('data')
            if 'accounts' in f.getnames() and os.path.isdir('accounts'):
                shutil.rmtree('accounts')
            f.extractall()
    except Exception as e:
        print(e)
