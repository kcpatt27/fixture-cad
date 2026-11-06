from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from .config import Settings

RequestedLane = Literal["accurate", "fast", "auto"]
ResolvedLane = Literal["accurate", "fast"]


@dataclass(frozen=True)
class ModelSelection:
    lane: ResolvedLane
    model: str


def resolve_model(
    requested_lane: RequestedLane | None,
    *,
    mode: str,
    settings: Settings,
) -> ModelSelection:
    lane = requested_lane or "accurate"
    if lane == "auto":
        lane = "fast" if mode == "chat" else "accurate"
    if lane == "fast":
        return ModelSelection(lane="fast", model=settings.fast_model)
    if lane == "accurate":
        return ModelSelection(lane="accurate", model=settings.accurate_model)
    raise ValueError(f"unsupported model lane: {lane}")
