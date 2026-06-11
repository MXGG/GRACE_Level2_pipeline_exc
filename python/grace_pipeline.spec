# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for GRACE Pipeline.

Build command:
    pyinstaller grace_pipeline.spec --clean

Output:
    dist/grace-pipeline.exe (Windows)
    dist/grace-pipeline-gui.exe (Windows)
    dist/grace-pipeline (Linux/macOS)
    dist/grace-pipeline-gui (Linux/macOS)
"""

import shutil
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs, collect_submodules

SPEC_DIR = Path(SPECPATH)
SRC_DIR = SPEC_DIR
REPO_ROOT = SRC_DIR.parent
APP_ICON = REPO_ROOT / "installer" / "grace-l2.ico"
SPLASH_IMAGE = SRC_DIR / "grace_pipeline" / "ui" / "qt" / "assets" / "splash.png"

extra_binaries = []
extra_binaries += collect_dynamic_libs("netCDF4")
extra_binaries += collect_dynamic_libs("h5py")

alias_src_dir = Path(sys.prefix) / "Lib" / "site-packages" / "netCDF4.libs"
alias_out_dir = SRC_DIR / "_pyi_dll_aliases"
alias_out_dir.mkdir(exist_ok=True)


def _add_netcdf_alias(pattern: str, alias_name: str) -> None:
    if not alias_src_dir.exists():
        return
    matches = sorted(alias_src_dir.glob(pattern))
    if not matches:
        return
    src = matches[0]
    dst = alias_out_dir / alias_name
    if (not dst.exists()) or (src.stat().st_mtime > dst.stat().st_mtime):
        shutil.copy2(src, dst)
    extra_binaries.append((str(dst), "."))


for _pattern, _alias in [
    ("netcdf-*.dll", "netcdf.dll"),
    ("zlib-*.dll", "zlib.dll"),
    ("libbz2-*.dll", "libbz2.dll"),
    ("szip-*.dll", "szip.dll"),
    ("hdf5-*.dll", "hdf5.dll"),
    ("hdf5_hl-*.dll", "hdf5_hl.dll"),
]:
    _add_netcdf_alias(_pattern, _alias)

snappy_candidates = [
    Path(sys.prefix) / "Library" / "bin" / "snappy.dll",
    Path(sys.prefix) / "DLLs" / "snappy.dll",
    Path(sys.prefix) / "snappy.dll",
    Path(sys.prefix) / "Lib" / "site-packages" / "netCDF4.libs" / "snappy.dll",
    Path(sys.prefix) / "Lib" / "site-packages" / "snappy.libs" / "snappy.dll",
    Path(sys.prefix) / "Lib" / "site-packages" / "python_snappy.libs" / "snappy.dll",
    REPO_ROOT / "vendor" / "snappy.dll",
    SPEC_DIR / "vendor" / "snappy.dll",
]
for cand in snappy_candidates:
    if cand.exists():
        extra_binaries.append((str(cand), "."))
        break

# Bundle canonical configs first; keep legacy matlab/cfg as a fallback during migration.
datas = [
    (str(REPO_ROOT / "configs" / "*.json"), "configs"),
    (str(REPO_ROOT / "matlab" / "cfg" / "*.json"), "cfg"),
    (str(REPO_ROOT / "data" / "Boundary"), "data/Boundary"),
    (str(REPO_ROOT / "data" / "GRACE" / "LowDegree"), "data/GRACE/LowDegree"),
    (str(REPO_ROOT / "data" / "GRACE" / "GIA"), "data/GRACE/GIA"),
    (str(SRC_DIR / "grace_pipeline" / "__init__.py"), "grace_pipeline"),
    (str(SRC_DIR / "grace_pipeline" / "gui.py"), "grace_pipeline"),
]
if SPLASH_IMAGE.exists():
    datas.append((str(SPLASH_IMAGE), "grace_pipeline/ui/qt/assets"))

datas += collect_data_files("matplotlib", includes=["mpl-data/*"])

hiddenimports = sorted(set(collect_submodules("grace_pipeline") + collect_submodules("netCDF4") + collect_submodules("h5py") + [
    "numpy",
    "scipy",
    "scipy.io",
    "scipy.linalg",
    "scipy.special",
    "scipy.interpolate",
    "scipy.ndimage",
    "click",
    "tqdm",
    "h5py",
    "netCDF4",
    "matplotlib",
    "matplotlib.pyplot",
    "matplotlib.backends.backend_qtagg",
    "PySide6",
    "PySide6.QtCore",
    "PySide6.QtGui",
    "PySide6.QtWidgets",
    "shiboken6",
    "shapefile",
    "typing_extensions",
]))

excludes = [
    "PyQt5",
    "PyQt6",
    "PySide2",
    "wx",
    "IPython",
    "jupyter",
    "notebook",
]
runtime_hooks = [str(SRC_DIR / "pyi_rth_netcdf_plugins.py")]
block_cipher = None

# CLI executable.
a = Analysis(
    [str(SRC_DIR / "grace_pipeline" / "entrypoints.py")],
    pathex=[str(SRC_DIR)],
    binaries=extra_binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=runtime_hooks,
    excludes=excludes,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# GUI executable.
a_gui = Analysis(
    [str(SRC_DIR / "grace_pipeline" / "gui_entry.py")],
    pathex=[str(SRC_DIR)],
    binaries=extra_binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=runtime_hooks,
    excludes=excludes,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)
pyz_gui = PYZ(a_gui.pure, a_gui.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="grace-pipeline",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(APP_ICON) if APP_ICON.exists() else None,
)

exe_gui = EXE(
    pyz_gui,
    a_gui.scripts,
    a_gui.binaries,
    a_gui.zipfiles,
    a_gui.datas,
    [],
    name="grace-pipeline-gui",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(APP_ICON) if APP_ICON.exists() else None,
)
