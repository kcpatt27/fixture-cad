from __future__ import annotations

import os
import sys
from pathlib import Path

CLIENT_ROOT = Path(__file__).resolve().parents[1]
if str(CLIENT_ROOT) not in sys.path:
    sys.path.insert(0, str(CLIENT_ROOT))

from fixture_blender.context import document_name  # noqa: E402


def test_document_name_is_basename_only() -> None:
    assert document_name("/home/me/part.blend") == "part.blend"
    if os.name == "nt":
        assert document_name(r"C:\Users\me\part.blend") == "part.blend"


def test_document_name_untitled_when_empty() -> None:
    assert document_name("") == "untitled"
    assert document_name(None) == "untitled"
