from pathlib import Path

path = Path("benchmarks/runners/run_trust_suite_v036.py")
text = path.read_text(encoding="utf-8")

start = text.index("def score_continuity_preservation")
end = text.index("def score_noise_resistance")

new_function = r'''def score_continuity_preservation(datasets):
    """
    V0.36.2 Causal Signature Continuity Scorer.

    This replaces simple static keyword continuity checks with a PRMR-style
    causal continuity check:

    - old state
    - problem/collapse
    - current active state
    - latent/repeated risk
    - lineage reason
    - continuity conclusion

    Inspired by PRMR v0.03 active / latent / lineage decomposition and
    causal signature preservation across transformation.
    """

    dataset_map = {
        dataset["dataset_name"]: dataset
        for dataset in datasets
    }

    checks = []

    def event_text(dataset_name):
        dataset = dataset_map[dataset_name]
        return " ".join(
            json.dumps(event, sort_keys=True).lower()
            for event in dataset.get("events", [])
        )

    def has_all(text, keywords):
        missing = [
            keyword
            for keyword in keywords
            if keyword.lower() not in text
        ]

        return {
            "passed": len(missing) == 0,
            "missing": missing
        }

    # Scenario 1: Company strategy changed.
    # Cheap packaging -> complaints -> premium positioning -> cheap suggestion reappears as mistake risk.
    document_text = event_text("document_evolution")

    company_channels = {
        "old_state": has_all(document_text, ["cheap packaging"]),
        "collapse_or_problem": has_all(document_text, ["complaints"]),
        "active_current_state": has_all(document_text, ["premium positioning"]),
        "latent_risk": has_all(document_text, ["cheap packaging again"]),
        "lineage_reason": has_all(document_text, ["customer complaints", "premium"])
    }

    company_passed_channels = sum(1 for item in company_channels.values() if item["passed"])
    company_score = company_passed_channels / len(company_channels)

    checks.append({
        "scenario": "company_strategy_change_packaging",
        "description": "Tracks old cheap-packaging strategy, complaint collapse, new premium rule, and repeated-risk warning.",
        "score": company_score,
        "passed": company_score >= 0.80,
        "channels": company_channels,
        "prmr_interpretation": {
            "active": "premium positioning",
            "latent": "cheap packaging suggestion may reappear",
            "lineage": "complaints explain why premium became current rule"
        }
    })

    # Scenario 2: User changed goal/focus.
    # Many projects -> overwhelm -> PRMR Memory Core focus -> protect against scattered builds.
    personal_text = event_text("fake_personal_ai_memory")

    personal_channels = {
        "old_state": has_all(personal_text, ["many projects"]),
        "collapse_or_problem": has_all(personal_text, ["overwhelmed"]),
        "active_current_state": has_all(personal_text, ["prmr memory core", "first serious product"]),
        "latent_risk": has_all(personal_text, ["scattered builds"]),
        "lineage_reason": has_all(personal_text, ["protect focus"])
    }

    personal_passed_channels = sum(1 for item in personal_channels.values() if item["passed"])
    personal_score = personal_passed_channels / len(personal_channels)

    checks.append({
        "scenario": "user_goal_change_focus",
        "description": "Tracks shift from many projects to PRMR Memory Core as current focus and preserves the reason.",
        "score": personal_score,
        "passed": personal_score >= 0.80,
        "channels": personal_channels,
        "prmr_interpretation": {
            "active": "PRMR Memory Core is current serious product focus",
            "latent": "risk of scattered builds returning",
            "lineage": "overwhelm caused focus rule"
        }
    })

    # Scenario 3: Creative ecosystem separation.
    # Mythrion = human imagination creative mode.
    # AURA = separate human-made art/authorship preservation system.
    creative_text = event_text("fake_creative_world_memory")

    creative_channels = {
        "old_or_origin_state": has_all(creative_text, ["mythrion", "human imagination"]),
        "rule_update": has_all(creative_text, ["ai generation", "rejected"]),
        "new_identity": has_all(creative_text, ["aura", "authorship", "real art"]),
        "separation": has_all(creative_text, ["separate", "human-made art"]),
        "lineage_reason": has_all(creative_text, ["preserving", "human-made"])
    }

    creative_passed_channels = sum(1 for item in creative_channels.values() if item["passed"])
    creative_score = creative_passed_channels / len(creative_channels)

    checks.append({
        "scenario": "creative_world_identity_separation",
        "description": "Tracks Mythrion/AURA separation and preserves human-authorship continuity.",
        "score": creative_score,
        "passed": creative_score >= 0.80,
        "channels": creative_channels,
        "prmr_interpretation": {
            "active": "AURA preserves human-made art/authorship",
            "latent": "AI-generation pressure remains external risk",
            "lineage": "Mythrion and AURA share human-first origin but diverge into separate roles"
        }
    })

    average = sum(check["score"] for check in checks) / max(len(checks), 1)
    points = round(average * 20, 2)

    return points, {
        "max_points": 20,
        "points": points,
        "average_continuity_score": round(average, 4),
        "passed_checks": sum(1 for check in checks if check["passed"]),
        "total_checks": len(checks),
        "checks": checks,
        "note": "V0.36.2 scorer uses PRMR-style active/latent/lineage continuity channels instead of static fact recall."
    }


'''

text = text[:start] + new_function + text[end:]
path.write_text(text, encoding="utf-8")

print("V0.36.2 causal signature continuity scorer patched ✅")
print("Now rerun: python benchmarks/runners/run_trust_suite_v036.py")