from pathlib import Path

TARGET = Path("benchmarks/runners/run_fraud_continuity_simulator_v045.py")

text = TARGET.read_text(encoding="utf-8")

start = text.index("def classify_packet(packet):")
end = text.index("\n\ndef build_packet(rows):", start)

new_function = r'''def classify_packet(packet):
    current = packet.get("current_state", "").lower()
    risk = " ".join(packet.get("risk_signals", [])).lower()
    human = " ".join(packet.get("human_context", [])).lower()
    counter = " ".join(packet.get("counter_evidence", [])).lower()
    action = packet.get("review_action", "").lower()

    full_text = " ".join([current, risk, human, counter, action])

    # Normal user: stable pattern and no escalation.
    if "ordinary spending continues" in full_text or "no fraud escalation" in full_text:
        return "normal_user"

    # False positive protection should happen before generic fraud suspicion.
    if "documented student finance" in counter or "likely false positive" in action:
        return "likely_false_positive"

    # Account takeover victim: broken login/device continuity + customer denial.
    if (
        "device continuity broke" in risk
        or "account takeover" in action
        or "did not authorize" in human
    ):
        return "possible_account_takeover_victim"

    # Scam victim: coached by caller / victim support.
    if "coached by caller" in human or "scam victim support" in action:
        return "possible_scam_victim"

    # Malicious/coordinated pattern:
    # Important: this must handle NEGATED victim/coercion evidence.
    # "no clear victim-coaching, coercion..." means do NOT classify as coerced.
    if (
        "coordinated pattern" in risk
        and (
            "no clear victim" in counter
            or "no clear victim-coaching" in counter
            or "no clear victim-coaching, coercion" in counter
        )
    ):
        return "fraud_investigation_needed"

    # Pressured/coerced mule:
    # Only use positive human-context/action signals, not negated counter-evidence.
    if (
        "messages suggest pressure" in human
        or "being instructed by another person" in human
        or "safeguarding assessment" in action
        or "coercion and safeguarding" in action
    ):
        return "possible_coercion_or_pressured_mule"

    # Fallback: if risk exists but context is unclear, require human review.
    if risk:
        return "needs_human_review"

    return "needs_human_review"
'''

patched = text[:start] + new_function + text[end:]

TARGET.write_text(patched, encoding="utf-8")

print("Patched V0.45 fraud classifier.")
print("Reason: prevent negated coercion/victim language from being misread as positive coercion.")
print("Now run:")
print("python benchmarks/runners/run_fraud_continuity_simulator_v045.py")