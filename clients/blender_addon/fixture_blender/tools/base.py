from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


@dataclass
class ToolRunner:
    name: str
    permission: str
    run: Callable[[dict[str, Any]], str]
