"""SUMO privado del instalador y procesos nativos aislados de Python/Qt."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from contextlib import contextmanager
from pathlib import Path
from threading import Lock

_DLL_LOCK = Lock()


def bundled_bin_directory() -> Path | None:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent / "sumo" / "bin"
    return None


def find_sumo_tool(name: str) -> str | None:
    folder = bundled_bin_directory()
    # El instalador usa siempre su pareja de binarios, sin mezclar versiones.
    if folder is not None:
        path = folder / (name + (".exe" if os.name == "nt" else ""))
        return str(path) if path.is_file() else None
    return shutil.which(name)


def command_environment(executable: str, cwd: Path | None = None) -> dict[str, str]:
    env = os.environ.copy()
    if getattr(sys, "frozen", False):
        bundle = Path(sys._MEIPASS).resolve()
        env["PATH"] = os.pathsep.join(
            part
            for part in env.get("PATH", "").split(os.pathsep)
            if part and not Path(part).resolve().is_relative_to(bundle)
        )
        if os.name != "nt":
            original = env.pop("LD_LIBRARY_PATH_ORIG", None)
            if original is None:
                env.pop("LD_LIBRARY_PATH", None)
            else:
                env["LD_LIBRARY_PATH"] = original
    executable_path = Path(executable).resolve()
    env["PATH"] = str(executable_path.parent) + os.pathsep + env.get("PATH", "")
    home = executable_path.parent.parent
    if (home / "data").is_dir():
        # Xerces/SUMO en Windows necesita los XSD en una ruta ASCII.
        # Una ruta relativa al escenario permite trabajar con usuarios como Héctor.
        if os.name == "nt" and not str(home).isascii() and cwd is not None:
            schemas = Path(cwd) / "sumo-resources" / "data" / "xsd"
            if not schemas.is_dir():
                shutil.copytree(home / "data" / "xsd", schemas)
            env["SUMO_HOME"] = "sumo-resources"
        else:
            env["SUMO_HOME"] = str(home)
    return env


@contextmanager
def _native_dll_search():
    if os.name != "nt" or not getattr(sys, "frozen", False):
        yield
        return
    import ctypes

    with _DLL_LOCK:
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.SetDllDirectoryW.argtypes = [ctypes.c_wchar_p]
        kernel.SetDllDirectoryW.restype = ctypes.c_int
        kernel.GetDllDirectoryW.argtypes = [ctypes.c_uint, ctypes.c_wchar_p]
        kernel.GetDllDirectoryW.restype = ctypes.c_uint
        previous = ctypes.create_unicode_buffer(32768)
        kernel.GetDllDirectoryW(len(previous), previous)
        if not kernel.SetDllDirectoryW(None):
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            yield
        finally:
            kernel.SetDllDirectoryW(previous.value or None)


def run_native(command: list[str], *, cwd: Path | None = None, timeout: int = 180):
    options = {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}
    with _native_dll_search():
        return subprocess.run(
            command,
            cwd=cwd,
            env=command_environment(command[0], cwd),
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            timeout=timeout,
            **options,
        )


def engine_version(executable: str) -> str:
    output = run_native([executable, "--version"], timeout=10).stdout.splitlines()
    return output[0] if output else "No registrada"
