"""Bounded deterministic explanations for Epistemic Continuity Packet V2."""

from __future__ import annotations

from typing import Any


def explain_packet_v2(packet: dict[str, Any]) -> list[str]:
    """Explain only structural facts present in a verified packet payload."""

    current = packet.get("current_state", {})
    explanations: list[str] = []
    if current.get("primary_state_status") == "conflicted":
        conflict_ids = ", ".join(current.get("primary_conflict_ids", []))
        explanations.append(
            f"The primary state is conflicted because {conflict_ids} remains open. "
            "No winner was selected."
        )
    elif current.get("primary_asserted_event_id"):
        explanations.append(
            "The primary state is supported by "
            f"{current.get('epistemic_status')} event "
            f"{current['primary_asserted_event_id']} at the requested bitemporal boundary."
        )
    elif current.get("primary_tentative_event_id"):
        explanations.append(
            f"Event {current['primary_tentative_event_id']} remains a tentative primary "
            "state because no asserted or derived state is available."
        )
    elif current.get("primary_unknown_event_id"):
        explanations.append(
            "The current state remains unknown because effective event "
            f"{current['primary_unknown_event_id']} is unresolved."
        )
    for item in packet.get("tentative_information", []):
        explanations.append(
            f"The inferred event {item['event_id']} remains a tentative overlay and did "
            "not replace explicitly supported state."
        )
    if packet.get("governance_context", {}).get("governance_erasure_present"):
        explanations.append(
            "Historical recoverability is partial because authorised governance "
            "erasure removed required evidence."
        )
    return explanations


__all__ = ["explain_packet_v2"]
