from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from .config import settings


def _load_all_schemas() -> dict[str, Any]:
    store: dict[str, Any] = {}
    for path in Path(settings.schemas_dir).glob("*.json"):
        data = json.loads(path.read_text(encoding="utf-8"))
        store[path.name] = data
        schema_id = data.get("$id")
        if isinstance(schema_id, str):
            store[schema_id] = data
    return store


def load_schema(name: str) -> dict[str, Any]:
    path = Path(settings.schemas_dir) / name
    if not path.exists():
        raise FileNotFoundError(f"Schema not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def validate_or_raise(instance: Any, schema_name: str) -> None:
    schema = load_schema(schema_name)
    store = _load_all_schemas()

    try:
        from referencing import Registry, Resource
        from referencing.jsonschema import DRAFT202012

        registry: Any = Registry()
        for key, doc in store.items():
            resource = Resource.from_contents(doc, default_specification=DRAFT202012)
            registry = registry.with_resource(key, resource)
        validator = Draft202012Validator(schema, registry=registry)
    except Exception:
        from jsonschema import RefResolver

        resolver = RefResolver(
            base_uri=f"file:///{Path(settings.schemas_dir).as_posix()}/",
            referrer=schema,
            store=store,
        )
        validator = Draft202012Validator(schema, resolver=resolver)

    errors = sorted(validator.iter_errors(instance), key=lambda e: list(e.path))
    if errors:
        messages = "; ".join(e.message for e in errors)
        raise ValueError(messages)
