from pathlib import Path

path = Path("benchmarks/runners/run_trust_suite_v036.py")
text = path.read_text(encoding="utf-8")

start = text.index("def score_compression_efficiency")
end = text.index("def score_continuity_preservation")

new_function = r'''def score_compression_efficiency(prmr_public_result):
    dataset_results = prmr_public_result.get("results", prmr_public_result.get("datasets", []))

    if not dataset_results:
        return 0, {
            "max_points": 15,
            "points": 0,
            "note": "Could not extract dataset results from PRMR engine output."
        }

    checks = []

    pattern_points = 0
    document_points = 0
    noise_points = 0

    for item in dataset_results:
        decision = item.get("decision", {})

        name = (
            item.get("dataset_name")
            or item.get("name")
            or item.get("dataset")
            or "unknown_dataset"
        )

        mode = (
            item.get("selected_mode")
            or item.get("mode")
            or item.get("storage_mode")
            or decision.get("policy_mode")
            or decision.get("technical_best_mode")
        )

        ratio = (
            item.get("compression_ratio")
            or decision.get("policy_compression_ratio")
            or decision.get("technical_compression_ratio")
            or 1
        )

        reduction = (
            item.get("storage_reduction_percent")
            or decision.get("policy_saved_percentage")
            or decision.get("technical_saved_percentage")
            or 0
        )

        raw_size = decision.get("raw_size")
        prmr_size = decision.get("policy_size") or decision.get("technical_best_size")
        rule_possible = decision.get("rule_possible")
        rule_failed_field = decision.get("rule_failed_field")
        rule_failure_reason = decision.get("rule_failure_reason")

        check = {
            "dataset": name,
            "mode": mode,
            "compression_ratio": ratio,
            "storage_reduction_percent": reduction,
            "raw_size": raw_size,
            "prmr_size": prmr_size,
            "rule_possible": rule_possible,
            "rule_failed_field": rule_failed_field,
            "rule_failure_reason": rule_failure_reason
        }

        # Structured pattern data target:
        # Full points only when rule compression reaches 5x+.
        # Partial points are allowed for useful transform compression,
        # but this exposes that the rule dataset is not yet fully rule-compressing.
        if "rule" in name or "synthetic_rule" in name:
            if mode == "rule" and ratio >= 5:
                pattern_points = 5
                check["compression_check"] = "full_pattern_pass"
            elif ratio >= 2:
                pattern_points = max(pattern_points, 3)
                check["compression_check"] = "partial_pattern_pass_transform_or_low_rule"
            elif ratio >= 1.5 and reduction >= 10:
                pattern_points = max(pattern_points, 2)
                check["compression_check"] = "weak_partial_pattern_pass"
            else:
                check["compression_check"] = "pattern_fail"

        # Evolving document target:
        # 2x to 5x is ideal. Below 2x gets partial if it still saves useful space.
        if "document" in name:
            if 2 <= ratio <= 5:
                document_points = 5
                check["compression_check"] = "full_document_pass"
            elif ratio > 5:
                document_points = max(document_points, 4)
                check["compression_check"] = "document_overcompressed_but_useful"
            elif ratio >= 1.2 and reduction >= 10:
                document_points = max(document_points, 3)
                check["compression_check"] = "partial_document_pass"
            else:
                check["compression_check"] = "document_fail"

        # Noise target:
        # Random noise should not be falsely compressed.
        if "noise" in name:
            if mode == "raw" or ratio <= 1.1 or reduction <= 1:
                noise_points = 5
                check["compression_check"] = "noise_guardrail_pass"
            else:
                check["compression_check"] = "noise_guardrail_fail"

        checks.append(check)

    points = pattern_points + document_points + noise_points

    return points, {
        "max_points": 15,
        "points": points,
        "pattern_points": pattern_points,
        "document_points": document_points,
        "noise_points": noise_points,
        "checks": checks,
        "note": "V0.36.1 compression scorer reads PRMR engine decision.policy_* fields and gives partial credit for useful transform compression."
    }


'''

text = text[:start] + new_function + text[end:]
path.write_text(text, encoding="utf-8")

print("V0.36.1 compression scorer patched ✅")
print("Now rerun: python benchmarks/runners/run_trust_suite_v036.py")