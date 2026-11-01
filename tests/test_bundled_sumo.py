"""El paquete usa su motor privado y no hereda DLL de Qt para SUMO."""

import os
from pathlib import Path

from walksim.sumo import runtime
from walksim.sumo.runner import detect_sumo


def test_frozen_detection_uses_bundle_and_never_mixes_external_tools(tmp_path, monkeypatch):
    monkeypatch.setattr(runtime.sys, "frozen", True, raising=False)
    monkeypatch.setattr(runtime.sys, "executable", str(tmp_path / "WalkSim.exe"))
    folder = tmp_path / "sumo" / "bin"
    folder.mkdir(parents=True)
    suffix = ".exe" if os.name == "nt" else ""
    (folder / ("sumo" + suffix)).touch()
    monkeypatch.setattr(runtime.shutil, "which", lambda name: "/external/" + name)
    detected = detect_sumo()
    assert Path(detected.sumo).parent == folder
    assert detected.netconvert is None
    assert not detected.available
    (folder / ("netconvert" + suffix)).touch()
    assert detect_sumo().available


def test_development_keeps_path_detection(monkeypatch):
    monkeypatch.setattr(runtime.sys, "frozen", False, raising=False)
    monkeypatch.setattr(runtime.shutil, "which", lambda name: "/system/" + name)
    assert detect_sumo().sumo == "/system/sumo"


def test_native_environment_removes_frozen_dll_path_and_selects_engine(tmp_path, monkeypatch):
    bundle = tmp_path / "_internal"
    native = tmp_path / "sumo"
    (native / "data").mkdir(parents=True)
    tool = native / "bin" / "sumo.exe"
    monkeypatch.setattr(runtime.sys, "frozen", True, raising=False)
    monkeypatch.setattr(runtime.sys, "_MEIPASS", str(bundle), raising=False)
    value = os.pathsep.join([str(bundle), str(bundle / "Qt"), str(tmp_path / "system")])
    monkeypatch.setenv("PATH", value)
    monkeypatch.setenv("SUMO_HOME", "/external")
    env = runtime.command_environment(str(tool))
    assert env["PATH"].split(os.pathsep) == [str(tool.parent), str(tmp_path / "system")]
    assert env["SUMO_HOME"] == str(native)
    assert os.environ["PATH"] == value
    assert os.environ["SUMO_HOME"] == "/external"


def test_windows_unicode_install_uses_relative_local_schemas(tmp_path, monkeypatch):
    # Simula sólo la decisión de rutas; Windows real se comprueba con el instalador.
    from types import SimpleNamespace

    native = tmp_path / "Héctor México" / "sumo"
    schemas = native / "data" / "xsd"
    schemas.mkdir(parents=True)
    (schemas / "routes_file.xsd").write_text("<schema/>")
    scenario = tmp_path / "scenario"
    scenario.mkdir()
    monkeypatch.setattr(runtime.sys, "frozen", False, raising=False)
    monkeypatch.setattr(
        runtime, "os", SimpleNamespace(name="nt", environ=os.environ, pathsep=os.pathsep)
    )
    env = runtime.command_environment(str(native / "bin" / "sumo.exe"), scenario)
    assert env["SUMO_HOME"] == "sumo-resources"
    assert (scenario / env["SUMO_HOME"] / "data/xsd/routes_file.xsd").read_text() == "<schema/>"
