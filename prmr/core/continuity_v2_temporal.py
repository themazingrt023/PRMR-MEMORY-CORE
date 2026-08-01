"""Temporal packet layers preserving each item's epistemic class."""

from __future__ import annotations

from collections import Counter
from typing import Any


def project_temporal_layers(layers: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    items: dict[str, dict[str, Any]] = {}
    for name in (
        "asserted_information",
        "derived_information",
        "tentative_information",
        "unknown_information",
    ):
        for item in layers[name]:
            items[str(item["event_id"])] = item
    ordered = [items[key] for key in sorted(items)]
    result = {
        f"{phase}_information_v2": [item for item in ordered if item.get("temporal_phase") == phase]
        for phase in ("active", "latent", "dormant", "decayed")
    }
    result["reinforced_information_v2"] = [item for item in ordered if item.get("reinforced")]
    result["re_emergence_information_v2"] = [item for item in ordered if item.get("re_emerging")]
    horizons: Counter[str] = Counter()
    for item in ordered:
        horizon = item.get("temporal_horizon")
        if horizon:
            horizons[str(horizon)] += 1
    result["temporal_horizon_summary"] = dict(sorted(horizons.items()))
    return result


__all__ = ["project_temporal_layers"]
