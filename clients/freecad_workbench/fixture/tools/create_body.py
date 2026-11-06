from __future__ import annotations

from typing import Any

from ._partdesign import active_document, ensure_name_available, transaction
from .base import ToolRunner


def run(args: dict[str, Any]) -> str:
    doc = active_document(create=True)
    name = str(args.get("name") or "Body").strip()
    if not name:
        raise ValueError("Body name must not be empty")
    ensure_name_available(doc, name)

    created: list[str] = []

    def rollback() -> None:
        for object_name in reversed(created):
            doc.removeObject(object_name)

    with transaction(doc, "Fixture create_body", rollback=rollback):
        body = doc.addObject("PartDesign::Body", name)
        created.append(body.Name)
        body.Label = name
        doc.recompute()

    return f"created PartDesign Body {body.Name}"


RUNNER = ToolRunner(name="create_body", permission="confirm", run=run)
