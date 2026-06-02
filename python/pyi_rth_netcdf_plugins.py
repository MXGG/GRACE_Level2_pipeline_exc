"""
Runtime hook for PyInstaller builds that need netCDF4/HDF5 filter plugins.

Ensures extracted DLL locations are discoverable on Windows and points HDF5
at the bundled plugin directory.
"""

import os
import sys


def _existing_dirs(base: str):
    candidates = [
        base,
        os.path.join(base, "netCDF4"),
        os.path.join(base, "netCDF4", "plugins"),
        os.path.join(base, "netCDF4.libs"),
    ]
    return [d for d in candidates if os.path.isdir(d)]


base_dir = getattr(sys, "_MEIPASS", "")
if base_dir:
    dll_dirs = _existing_dirs(base_dir)
    for dll_dir in dll_dirs:
        try:
            os.add_dll_directory(dll_dir)
        except Exception:
            pass

    if dll_dirs:
        old_path = os.environ.get("PATH", "")
        prepend = os.pathsep.join(dll_dirs)
        os.environ["PATH"] = prepend + (os.pathsep + old_path if old_path else "")

    plugin_dir = os.path.join(base_dir, "netCDF4", "plugins")
    if os.path.isdir(plugin_dir):
        os.environ.setdefault("HDF5_PLUGIN_PATH", plugin_dir)
