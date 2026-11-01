"""Descarga verificada de SUMO y metadatos reproducibles del instalador."""

from __future__ import annotations

import hashlib
import json
import shutil
import sys
import tomllib
import urllib.request
import zipfile
from importlib import metadata
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[2]
BUILD = ROOT / "build/windows"
SUMO_VERSION = "1.28.0"
SUMO_URL = f"https://sumo.dlr.de/releases/{SUMO_VERSION}/sumo-win64-{SUMO_VERSION}.zip"
SUMO_SHA256 = "822aa9c57a07a895200d536fd2b3fe8785e36baa9b97ecbe75688e08a636fb8e"


def download_sumo():
    archive = BUILD / f"sumo-win64-{SUMO_VERSION}.zip"
    if not archive.exists():
        with urllib.request.urlopen(SUMO_URL, timeout=120) as response:
            with archive.open("wb") as output:
                shutil.copyfileobj(response, output)
    with archive.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    if digest != SUMO_SHA256:
        archive.unlink()
        raise RuntimeError("El SHA256 del paquete oficial de SUMO no coincide.")
    extracted = BUILD / "sumo-unpacked"
    extracted.mkdir(exist_ok=True)
    with zipfile.ZipFile(archive) as stream:
        for item in stream.infolist():
            if not (extracted / item.filename).resolve().is_relative_to(extracted.resolve()):
                raise RuntimeError("Ruta no válida en el paquete SUMO.")
        stream.extractall(extracted)
    candidates = [p.parent.parent for p in extracted.rglob("sumo.exe") if p.parent.name == "bin"]
    if len(candidates) != 1:
        raise RuntimeError("No se encontró una única distribución SUMO.")
    motor = BUILD / "sumo"
    shutil.copytree(candidates[0], motor, dirs_exist_ok=True)
    for tool in ("sumo.exe", "netconvert.exe"):
        if not (motor / "bin" / tool).is_file():
            raise RuntimeError(f"Falta {tool} en SUMO.")


def prepare_metadata():
    BUILD.mkdir(parents=True, exist_ok=True)
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    version = project["version"]
    numbers = ", ".join([*version.split("."), "0"])
    (BUILD / "version.txt").write_text(
        "VSVersionInfo(ffi=FixedFileInfo(filevers=(" + numbers + "), prodvers=(" + numbers + "), "
        "mask=0x3f, flags=0x0, OS=0x40004, fileType=0x1, subtype=0x0, date=(0,0)), "
        "kids=[StringFileInfo([StringTable('040904B0', ["
        "StringStruct('CompanyName', 'Héctor Alonso Benítez García'), "
        "StringStruct('FileDescription', 'WalkSim Mobility'), "
        f"StringStruct('FileVersion', '{version}'), "
        f"StringStruct('ProductVersion', '{version}'), "
        "StringStruct('ProductName', 'WalkSim Mobility'), "
        "StringStruct('OriginalFilename', 'WalkSim.exe'), "
        "StringStruct('LegalCopyright', 'GPL-3.0-only')])]), "
        "VarFileInfo([VarStruct('Translation', [1033, 1200])])])",
        encoding="utf-8",
    )
    # Icono de escritorio nativo: red vial, sin dependencias externas de diseño.
    icon = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
    draw = ImageDraw.Draw(icon)
    draw.rounded_rectangle((6, 6, 250, 250), radius=45, fill="#253b50")
    points = [(42, 66), (82, 190), (128, 112), (174, 190), (214, 66)]
    draw.line(points, fill="white", width=14, joint="curve")
    for x, y in points:
        draw.ellipse((x - 11, y - 11, x + 11, y + 11), fill="#8fd4d9")
    icon.save(BUILD / "WalkSim.ico", sizes=[(16, 16), (32, 32), (48, 48), (256, 256)])
    (BUILD / "build-info.json").write_text(
        json.dumps(
            {
                "version": version,
                "python": sys.version,
                "source_commit": __import__("subprocess")
                .check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True)
                .strip(),
                "sumo_version": SUMO_VERSION,
                "sumo_url": SUMO_URL,
                "sumo_sha256": SUMO_SHA256,
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def stage_distribution():
    destination = ROOT / "dist/WalkSim"
    shutil.copytree(BUILD / "sumo", destination / "sumo", dirs_exist_ok=True)
    for name in ("LEEME.txt", "THIRD_PARTY.txt"):
        shutil.copy2(ROOT / "packaging/windows" / name, destination / name)
    shutil.copy2(BUILD / "build-info.json", destination)
    shutil.copytree(ROOT / "examples", destination / "examples", dirs_exist_ok=True)
    shutil.copytree(ROOT / "docs", destination / "docs", dirs_exist_ok=True)
    licenses = destination / "licenses"
    licenses.mkdir(exist_ok=True)
    shutil.copy2(ROOT / "LICENSE", licenses / "WalkSim-GPL-3.0.txt")
    for name in ("LICENSE.txt", "LICENSE"):
        python_license = Path(sys.base_prefix) / name
        if python_license.is_file():
            shutil.copy2(python_license, licenses / "Python-LICENSE.txt")
            break
    else:
        raise RuntimeError("No se encontró la licencia de Python.")
    # El inventario se toma del entorno real; conserva las licencias de las ruedas.
    inventory = []
    for dist in sorted(metadata.distributions(), key=lambda d: d.metadata["Name"].lower()):
        name = dist.metadata["Name"]
        files = list(dist.files or [])
        for file in files:
            if any("license" in part.lower() or "copying" in part.lower() for part in file.parts):
                source = Path(dist.locate_file(file))
                if source.is_file():
                    safe = [part for part in file.parts if part not in ("..", ".", "/")]
                    target = licenses / name / Path(*safe)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source, target)
        inventory.append(
            {
                "name": name,
                "version": dist.version,
                "license": dist.metadata.get("License-Expression") or dist.metadata.get("License"),
                "urls": dist.metadata.get_all("Project-URL", []),
                "pypi": f"https://pypi.org/project/{name}/{dist.version}/#files",
            }
        )
    (licenses / "components.json").write_text(
        json.dumps(inventory, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    sources = destination / "sources"
    sources.mkdir(exist_ok=True)
    # Fuente exacta del ejecutable, no una rama mutable.
    with zipfile.ZipFile(sources / "WalkSim-source.zip", "w", zipfile.ZIP_DEFLATED) as archive:
        for folder in ("src", "packaging", "tests", "docs", ".github"):
            for path in (ROOT / folder).rglob("*"):
                if path.is_file() and "__pycache__" not in path.parts:
                    archive.write(path, path.relative_to(ROOT))
        for filename in ("LICENSE", "README.md", "CHANGELOG.md", "pyproject.toml"):
            archive.write(ROOT / filename, filename)


if __name__ == "__main__":
    if "--stage" in sys.argv:
        stage_distribution()
    else:
        prepare_metadata()
        download_sumo()
