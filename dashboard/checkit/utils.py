import os
import tempfile
import time
from contextlib import contextmanager


def atomic_write(path, text, encoding="utf-8", newline=None):
    """Replace `path` with `text`, whole or not at all.

    `with open(path, "w") as f: f.write(build())` empties the file before
    `build()` runs, so an exception there -- a generator failing, an XSLT
    error -- leaves a zero-byte file. For bank.json that is a viewer whose
    "Loading" spinner never stops (RV-10, 2026-11-16). This writes a
    temporary file beside the target and renames it over; the rename is
    all-or-nothing.

    UTF-8 by default, never the locale's: see RV-6 in CODEBASE_NOTES.md.

    checkit-printit carries its own copy (`checkit_printit.fileio`) on
    purpose, because it is installed against released wheels of this
    package and must not depend on a helper only the newest one has.
    """
    path = os.fspath(path)
    directory = os.path.dirname(os.path.abspath(path))
    os.makedirs(directory, exist_ok=True)
    fd, temp = tempfile.mkstemp(
        prefix="." + os.path.basename(path) + ".", suffix=".tmp",
        dir=directory)
    try:
        with os.fdopen(fd, "w", encoding=encoding, newline=newline) as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        deadline = time.monotonic() + 1.0
        while True:
            try:
                os.replace(temp, path)
                break
            except PermissionError:
                # Windows refuses while a scanner or indexer has the
                # target open for a moment.
                if time.monotonic() >= deadline:
                    raise
                time.sleep(0.05)
    except BaseException:
        try:
            os.remove(temp)
        except OSError:
            pass
        raise
    return path

@contextmanager
def working_directory(path):
    """
    Temporarily change the current working directory.
    Usage:
    with working_directory(path):
        do_things()   # working in the given path
    do_other_things() # back to original path
    """
    current_directory=os.getcwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(current_directory)