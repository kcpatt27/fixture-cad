from __future__ import annotations

import json

from fixture.context import json_safe_property


class FakeQuantity:
    def __init__(self, value: float) -> None:
        self.Value = value


class StringOnly:
    def __str__(self) -> str:
        return "fallback"


def test_json_safe_property_converts_quantity_to_float() -> None:
    value = json_safe_property(FakeQuantity(8.0))
    assert value == 8.0
    assert json.loads(json.dumps({"Length": value})) == {"Length": 8.0}


def test_json_safe_property_preserves_scalars_and_stringifies_unknowns() -> None:
    assert json_safe_property("Pad") == "Pad"
    assert json_safe_property(3) == 3
    assert json_safe_property(True) is True
    assert json_safe_property(None) is None
    assert json_safe_property(StringOnly()) == "fallback"
