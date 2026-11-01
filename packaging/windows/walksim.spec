# Python/Qt empaquetados y SUMO en su propia carpeta nativa.
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, copy_metadata

root = Path(SPECPATH).resolve().parents[1]
datas = collect_data_files("walksim") + collect_data_files("tzdata")
for package in ("walksim-mobility", "matplotlib", "PySide6", "tzdata"):
    datas += copy_metadata(package)

a = Analysis(
    [str(root / "packaging/windows/launcher.py")],
    pathex=[str(root / "src")],
    binaries=[], datas=datas, hiddenimports=[],
    hookspath=[], hooksconfig={"matplotlib": {"backends": ["QtAgg", "Agg", "pdf"]}},
    runtime_hooks=[],
    excludes=["PyQt5", "PyQt6", "PySide2", "tkinter", "IPython", "pytest"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, [], exclude_binaries=True, name="WalkSim",
    debug=False, bootloader_ignore_signals=False, strip=False, upx=False,
    console=False, icon=str(root / "build/windows/WalkSim.ico"),
    version=str(root / "build/windows/version.txt"),
)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="WalkSim")

