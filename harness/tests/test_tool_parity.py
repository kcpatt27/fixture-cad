from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
for rel in ("clients/freecad_workbench", "clients/blender_addon"):
    path = ROOT / rel
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from fixture.tools import get_runner as freecad_runner  # noqa: E402
from fixture_blender.tools import get_runner as blender_runner  # noqa: E402


def test_documented_tools_have_matching_client_runners() -> None:
    tools_dir = ROOT / "docs" / "tools"
    runners = {
        "freecad": freecad_runner,
        "blender": blender_runner,
    }
    failures: list[str] = []
    for path in sorted(tools_dir.glob("*.json")):
        data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
        name = data["name"]
        permission = data["permission"]
        for app in data.get("apps", []):
            runner = runners[app](name)
            if runner is None:
                failures.append(f"{name}: no {app} runner")
                continue
            if runner.permission != permission:
                failures.append(
                    f"{name}: docs={permission} {app}={runner.permission}"
                )
            if runner.name != name:
                failures.append(f"{name}: {app} runner is {runner.name}")
    assert not failures, "\n".join(failures)
