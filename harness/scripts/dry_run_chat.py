"""HTTP dry-run against a running harness."""

from __future__ import annotations

import json
import sys
import urllib.request


BASE = "http://127.0.0.1:8766"


def get(path: str) -> dict:
    with urllib.request.urlopen(BASE + path, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def post(path: str, payload: dict) -> dict:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        BASE + path,
        data=data,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=180) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main() -> int:
    health = get("/health")
    print("health:", json.dumps(health))
    if not health.get("ok"):
        return 1

    tools = get("/tools?app=freecad")
    print("tools:", [t["name"] for t in tools.get("tools", [])])

    explain = post(
        "/chat",
        {
            "app": "freecad",
            "version": "0.1.0",
            "context": {
                "active_document": "Unnamed",
                "workbench_or_mode": "PartDesign",
                "selected_objects": [
                    {
                        "name": "Pad001",
                        "type": "PartDesign::Pad",
                        "shape": "Solid",
                        "properties": {"Length": 10},
                    }
                ],
                "extra": {},
            },
            "message": "Explain what this selected part is",
            "mode": "explain",
        },
    )
    print("explain reply:", explain.get("reply_text", "")[:200])
    print("explain actions:", json.dumps(explain.get("actions"), indent=2)[:500])

    box = post(
        "/chat",
        {
            "app": "freecad",
            "version": "0.1.0",
            "context": {
                "active_document": "Unnamed",
                "workbench_or_mode": "PartDesign",
                "selected_objects": [],
                "extra": {},
            },
            "message": "Create a 40x40x10mm box",
            "mode": "chat",
        },
    )
    print("box reply:", box.get("reply_text", "")[:200])
    print("box actions:", json.dumps(box.get("actions"), indent=2)[:800])

    blender = post(
        "/chat",
        {
            "app": "blender",
            "version": "0.1.0",
            "context": {
                "active_document": "untitled",
                "workbench_or_mode": "OBJECT",
                "selected_objects": [
                    {"name": "Cube", "type": "MESH", "shape": "Mesh", "properties": {"vertices": 8}}
                ],
                "extra": {},
            },
            "message": "Clean up this mesh",
            "mode": "chat",
        },
    )
    print("blender reply:", blender.get("reply_text", "")[:200])
    print("blender actions:", json.dumps(blender.get("actions"), indent=2)[:500])
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001
        print("DRYRUN FAILED:", exc, file=sys.stderr)
        raise SystemExit(1)
