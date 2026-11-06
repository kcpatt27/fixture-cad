from __future__ import annotations

import re
import tomllib
from pathlib import Path

from fixture_cad import __version__

ROOT = Path(__file__).resolve().parents[2]
EXPECTED_PACKAGE = "0.2.0"
EXPECTED_PROTOCOL = "0.1.0"


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_package_versions_match_release() -> None:
    pyproject = tomllib.loads(_read("harness/pyproject.toml"))
    package_xml = re.search(r"<version>([^<]+)</version>", _read("clients/freecad_workbench/package.xml"))
    freecad = re.search(r'__version__ = "([^"]+)"', _read("clients/freecad_workbench/fixture/__init__.py"))
    bench = re.search(r'__version__ = "([^"]+)"', _read("benchmark/fixture_bench/__init__.py"))
    blender = re.search(
        r'"version": \((\d+), (\d+), (\d+)\)',
        _read("clients/blender_addon/fixture_blender/__init__.py"),
    )
    assert package_xml and freecad and bench and blender
    blender_version = ".".join(blender.groups())
    versions = {
        "fixture_cad.__version__": __version__,
        "pyproject": pyproject["project"]["version"],
        "package.xml": package_xml.group(1),
        "fixture.__version__": freecad.group(1),
        "fixture_bench.__version__": bench.group(1),
        "bl_info.version": blender_version,
    }
    assert set(versions.values()) == {EXPECTED_PACKAGE}, versions


def test_client_protocol_versions_match_contract() -> None:
    freecad = re.search(
        r'CLIENT_VERSION = "([^"]+)"',
        _read("clients/freecad_workbench/fixture/config.py"),
    )
    blender = re.search(
        r'CLIENT_VERSION = "([^"]+)"',
        _read("clients/blender_addon/fixture_blender/config.py"),
    )
    assert freecad and blender
    assert freecad.group(1) == blender.group(1) == EXPECTED_PROTOCOL
    assert "wire protocol" in _read("docs/api-contract.md")
    assert EXPECTED_PROTOCOL in _read("docs/api-contract.md")
