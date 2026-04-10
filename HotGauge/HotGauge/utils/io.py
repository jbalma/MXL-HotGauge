import sys
import contextlib
from pathlib import Path

@contextlib.contextmanager
def open_file_or_stdout(filename=None):
    if filename is None or filename == '-':
        handle = sys.stdout
    else:
        handle = open(filename, 'w')
    try:
        yield handle
    finally:
        if handle is not sys.stdout:
            handle.close()

def replace_suffix(original_filename, new_suffix):
    p = Path(original_filename)
    return p.with_suffix(new_suffix)
