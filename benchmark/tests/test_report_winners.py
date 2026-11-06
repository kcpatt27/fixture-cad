"""Winner selection for BEST-SMALLEST / BEST-FASTEST."""
from __future__ import annotations

from fixture_bench.models import parse_param_count_billions
from fixture_bench.report import aggregate, pick_winners, render_summary_md, winner_preset_models


def test_parse_param_count_billions() -> None:
    assert parse_param_count_billions("7.6B") == 7.6
    assert parse_param_count_billions("354.48M") == 0.35448
    assert parse_param_count_billions(name="qwen2.5:7b-instruct-q8_0") == 7.0
    assert parse_param_count_billions(name="LiquidAI/lfm2.5-350m:latest") == 0.35
    assert parse_param_count_billions(name="gpt-oss:20b") == 20.0


def test_best_smallest_and_best_fastest() -> None:
    results = [
        _row("tiny-slow", 4.0, "fc-a", score=8, max_score=8, lat=10.0),
        _row("tiny-slow", 4.0, "fc-b", score=8, max_score=8, lat=10.0),
        _row("mid-fast", 8.0, "fc-a", score=8, max_score=8, lat=1.0),
        _row("mid-fast", 8.0, "fc-b", score=7, max_score=8, lat=1.0),  # 93.75%
        _row("big-best", 20.0, "fc-a", score=8, max_score=8, lat=5.0),
        _row("big-best", 20.0, "fc-b", score=8, max_score=8, lat=5.0),
        _row("tiny-weak", 1.0, "fc-a", score=4, max_score=8, lat=0.2),
        _row("tiny-weak", 1.0, "fc-b", score=4, max_score=8, lat=0.2),  # 50%
        _row("mid-slow", 6.0, "fc-a", score=8, max_score=8, lat=2.0),
        _row("mid-slow", 6.0, "fc-b", score=8, max_score=8, lat=2.0),  # 100%, 6B
    ]
    sizes = {
        "tiny-slow": {"param_b": 4.0, "parameter_size": "4.0B"},
        "mid-fast": {"param_b": 8.0, "parameter_size": "8.0B"},
        "big-best": {"param_b": 20.0, "parameter_size": "20.0B"},
        "tiny-weak": {"param_b": 1.0, "parameter_size": "1.0B"},
        "mid-slow": {"param_b": 6.0, "parameter_size": "6.0B"},
    }
    winners = pick_winners(aggregate(results, size_by_model=sizes))
    # same 100%: mid-slow wins BEST on lower latency; big-best is BEST2
    assert winners["best"]["model"] == "mid-slow"
    assert winners["best2"]["model"] == "big-best"
    assert winners["fastest"]["model"] == "tiny-weak"
    assert winners["best_smallest"]["model"] == "tiny-slow"
    assert winners["best_smallest2"]["model"] == "mid-slow"
    assert winners["best_fastest"]["model"] == "mid-fast"
    assert winners["best_fastest2"]["model"] == "mid-slow"


def test_winner_preset_dedupes_and_orders() -> None:
    results = [
        _row("mid-slow", 6.0, "fc-a", score=8, max_score=8, lat=2.0),
        _row("mid-fast", 8.0, "fc-a", score=8, max_score=8, lat=1.0),
        _row("tiny-weak", 1.0, "fc-a", score=4, max_score=8, lat=0.2),
        _row("tiny-slow", 4.0, "fc-a", score=8, max_score=8, lat=10.0),
    ]
    meta = {
        "model_info": {
            "mid-slow": {"param_b": 6.0, "parameter_size": "6.0B"},
            "mid-fast": {"param_b": 8.0, "parameter_size": "8.0B"},
            "tiny-weak": {"param_b": 1.0, "parameter_size": "1.0B"},
            "tiny-slow": {"param_b": 4.0, "parameter_size": "4.0B"},
        }
    }
    names, roles = winner_preset_models(results, meta)
    # mid-fast is both BEST (tied 100%, lower latency) and BEST-FASTEST → one slot
    assert names == ["mid-fast", "tiny-weak", "tiny-slow"]
    assert roles["mid-fast"] == ["BEST", "BEST-FASTEST"]
    assert roles["tiny-weak"] == ["FASTEST"]
    assert roles["tiny-slow"] == ["BEST-SMALLEST"]
    assert "mid-slow" not in names


def test_summary_marks_new_winners() -> None:
    results = [
        _row("small", 4.0, "fc-a", score=8, max_score=8, lat=3.0),
        _row("fast", 8.0, "fc-a", score=8, max_score=8, lat=1.0),
        _row("weak", 1.0, "fc-a", score=1, max_score=8, lat=0.1),
    ]
    meta = {
        "started": "t",
        "models": ["small", "fast", "weak"],
        "case_count": 1,
        "model_info": {
            "small": {"param_b": 4.0, "parameter_size": "4.0B"},
            "fast": {"param_b": 8.0, "parameter_size": "8.0B"},
            "weak": {"param_b": 1.0, "parameter_size": "1.0B"},
        },
    }
    md = render_summary_md(results, meta)
    assert "BEST-SMALL" in md
    assert "BEST-FAST" in md
    assert "small" in md and "BEST-SMALL" in md
    assert "fast" in md and "BEST-FAST" in md


def _row(
    model: str,
    _param: float,
    case_id: str,
    *,
    score: float,
    max_score: float,
    lat: float,
) -> dict:
    return {
        "model": model,
        "case_id": case_id,
        "app": "freecad",
        "score": score,
        "max_score": max_score,
        "latency_s": lat,
        "checks": {},
        "notes": [],
    }
