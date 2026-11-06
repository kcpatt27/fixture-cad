"""N1 harness HTTP smoke: ambiguous / partial / history acceptance."""

from __future__ import annotations

import json
import urllib.request


def post(path: str, body: dict) -> dict:
    req = urllib.request.Request(
        f"http://127.0.0.1:8766{path}",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=120) as response:
        return json.loads(response.read().decode())


def main() -> None:
    ctx = {
        "active_document": "Unnamed",
        "workbench_or_mode": "PartDesign",
        "selected_objects": [],
        "extra": {},
    }
    base = {
        "app": "freecad",
        "version": "0.1.0",
        "context": ctx,
        "mode": "chat",
        "model_lane": "accurate",
    }

    amb = post("/chat", {**base, "message": "make an interlocking hinge in plastic"})
    tools = [a for a in amb.get("actions", []) if a.get("type") == "tool_call"]
    assert amb.get("intent_status") in {"ambiguous", "unsupported"}, amb.get("intent_status")
    assert not tools, tools
    print("OK ambiguous/unsupported", amb.get("intent_status"))

    partial = post("/chat", {**base, "message": "make a hinge; start with anything you can"})
    ptools = [a for a in partial.get("actions", []) if a.get("type") == "tool_call"]
    confirm = [a for a in partial.get("actions", []) if a.get("kind") == "need_confirm"]
    print(
        "partial status",
        partial.get("intent_status"),
        "tools",
        len(ptools),
        "confirm",
        bool(confirm),
        "remainder",
        (partial.get("supported_scope") or {}).get("remainder"),
    )
    if partial.get("intent_status") == "partial":
        assert ptools and confirm and (partial.get("supported_scope") or {}).get("remainder")
        print("OK partial gated")
    elif partial.get("intent_status") == "supported" and ptools and confirm:
        print("OK supported+confirm subset")
    else:
        assert partial.get("intent_status") in {"ambiguous", "unsupported"}
        assert not ptools
        print("OK fail-closed without tools")

    hist = post(
        "/chat",
        {
            **base,
            "message": "yes, make the base plate",
            "history": [
                {"role": "user", "text": "make a hinge; start with anything you can"},
                {
                    "role": "assistant",
                    "text": (
                        "I can start with a 30x15x2 mm rectangular base plate. "
                        "Barrels remain unsupported."
                    ),
                },
            ],
        },
    )
    htools = [a for a in hist.get("actions", []) if a.get("type") == "tool_call"]
    assert hist.get("intent_status") in {"supported", "partial"}, hist.get("intent_status")
    assert htools, hist
    assert any(a.get("kind") == "need_confirm" for a in hist.get("actions", [])), hist
    print("OK history accept", hist.get("intent_status"), [t.get("tool_name") for t in htools])


if __name__ == "__main__":
    main()
