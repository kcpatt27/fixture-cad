from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from ..config import settings


@dataclass(frozen=True)
class ToolDef:
    name: str
    description: str
    permission: str
    apps: tuple[str, ...]
    args_schema: dict[str, Any]
    raw: dict[str, Any]

    def for_prompt(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "permission": self.permission,
            "args_schema": self.args_schema,
        }


class ToolRegistry:
    def __init__(self, tools: list[ToolDef]) -> None:
        self._by_name = {t.name: t for t in tools}

    @classmethod
    def load(cls, tools_dir: Path | None = None) -> ToolRegistry:
        directory = Path(tools_dir or settings.tools_dir)
        tools: list[ToolDef] = []
        for path in sorted(directory.glob("*.json")):
            data = json.loads(path.read_text(encoding="utf-8"))
            tools.append(
                ToolDef(
                    name=data["name"],
                    description=data.get("description", ""),
                    permission=data.get("permission", "confirm"),
                    apps=tuple(data.get("apps", [])),
                    args_schema=data.get("args_schema", {"type": "object"}),
                    raw=data,
                )
            )
        return cls(tools)

    def for_app(self, app: str) -> list[ToolDef]:
        return [t for t in self._by_name.values() if app in t.apps]

    def get(self, name: str) -> ToolDef | None:
        return self._by_name.get(name)

    def validate_args(self, tool_name: str, args: dict[str, Any]) -> list[str]:
        tool = self.get(tool_name)
        if tool is None:
            return [f"unknown tool: {tool_name}"]
        validator = Draft202012Validator(tool.args_schema)
        return [e.message for e in validator.iter_errors(args)]
