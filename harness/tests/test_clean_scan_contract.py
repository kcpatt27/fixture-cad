"""Contract + path-validation coverage for the Blender clean_scan tool."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from fixture_cad.tools.registry import ToolRegistry

ADDON_ROOT = Path(__file__).resolve().parents[2] / "clients" / "blender_addon"
if str(ADDON_ROOT) not in sys.path:
    sys.path.insert(0, str(ADDON_ROOT))

from fixture_blender.tools.clean_scan import validate_paths  # noqa: E402


def test_clean_scan_contract_is_blender_confirm() -> None:
    registry = ToolRegistry.load()
    tool = registry.get("clean_scan")
    assert tool is not None
    assert tool.permission == "confirm"
    assert tool.apps == ("blender",)
    schema = tool.args_schema
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == {"input_path", "output_path"}
    assert schema["properties"]["target_triangles"]["minimum"] == 1000
    assert schema["properties"]["voxel_size"]["default"] == 0


def test_validate_paths_rejects_missing_input(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="does not exist"):
        validate_paths(str(tmp_path / "missing.stl"), str(tmp_path / "out.stl"))


def test_validate_paths_rejects_unsupported_suffix(tmp_path: Path) -> None:
    src = tmp_path / "scan.xyz"
    src.write_text("not a mesh")
    with pytest.raises(ValueError, match="unsupported input format"):
        validate_paths(str(src), str(tmp_path / "out.stl"))


def test_validate_paths_appends_stl_and_creates_parent(tmp_path: Path) -> None:
    src = tmp_path / "scan.ply"
    src.write_text("ply")
    dst = tmp_path / "nested" / "cleaned"
    resolved_src, resolved_dst = validate_paths(str(src), str(dst))
    assert resolved_src == src.resolve()
    assert resolved_dst == (dst.with_suffix(".stl")).resolve()
    assert resolved_dst.parent.is_dir()
