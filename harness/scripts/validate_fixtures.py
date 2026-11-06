"""Validate fixtures and smoke-test harness imports."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012

ROOT = Path(__file__).resolve().parents[2]
SCHEMAS = ROOT / "docs" / "schemas"
FIXTURES = ROOT / "docs" / "fixtures"


def main() -> int:
    store: dict = {}
    for path in SCHEMAS.glob("*.json"):
        data = json.loads(path.read_text(encoding="utf-8"))
        store[path.name] = data
        schema_id = data.get("$id")
        if isinstance(schema_id, str):
            store[schema_id] = data

    registry = Registry()
    for key, doc in store.items():
        registry = registry.with_resource(
            key, Resource.from_contents(doc, default_specification=DRAFT202012)
        )

    checks = [
        ("chat-request.json", "chat-request-box.json"),
        ("chat-request.json", "chat-request-explain.json"),
        ("chat-request.json", "chat-request-history.json"),
        ("chat-request.json", "chat-request-reference-image.json"),
        ("chat-response.json", "chat-response-box.json"),
        ("chat-response.json", "chat-response-ambiguous.json"),
        ("tool-result.json", "tool-result-failure.json"),
    ]
    failed = 0
    for schema_name, fixture_name in checks:
        schema = store[schema_name]
        data = json.loads((FIXTURES / fixture_name).read_text(encoding="utf-8"))
        errors = list(Draft202012Validator(schema, registry=registry).iter_errors(data))
        if errors:
            print(f"FAIL {fixture_name}: {errors[0].message}")
            failed += 1
        else:
            print(f"OK   {fixture_name}")

    from fixture_cad.config import settings
    from fixture_cad.tools.registry import ToolRegistry

    reg = ToolRegistry.load()
    print("tools_dir", settings.tools_dir)
    print("freecad", [t.name for t in reg.for_app("freecad")])
    print("blender", [t.name for t in reg.for_app("blender")])
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
