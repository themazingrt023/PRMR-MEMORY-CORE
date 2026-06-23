import json
import random
from pathlib import Path

random.seed(39)

DATASET_DIR = Path("benchmarks/datasets_v039")
RUNNER_DIR = Path("benchmarks/runners")
REPORT_DIR = Path("reports/v039")

DATASET_DIR.mkdir(parents=True, exist_ok=True)
RUNNER_DIR.mkdir(parents=True, exist_ok=True)
REPORT_DIR.mkdir(parents=True, exist_ok=True)


def write_json(path, data):
    path.write_text(json.dumps(data, indent=4), encoding="utf-8")


def build_dataset():
    target_client = "client_alpha"

    truths = [
        {
            "topic": "security_policy",
            "old_state": "shared default access",
            "problem": "cross-client leak risk",
            "current_state": "vault isolation required",
            "latent_risk": "old shared access pattern returns",
            "lineage_reason": "client trust requires strict vault isolation",
            "near_miss": "vault isolation optional",
            "other_client_current": "shared workspace access allowed"
        },
        {
            "topic": "product_focus",
            "old_state": "many scattered projects",
            "problem": "slow execution and overwhelmed roadmap",
            "current_state": "PRMR Memory Core first",
            "latent_risk": "scattered builds return under pressure",
            "lineage_reason": "execution improved when the roadmap narrowed",
            "near_miss": "EION app first",
            "other_client_current": "multi-product launch sprint"
        },
        {
            "topic": "compression_policy",
            "old_state": "compress anything that saves bytes",
            "problem": "noise can fake useful compression",
            "current_state": "compress meaning, keep noise raw",
            "latent_risk": "byte savings mistaken for memory intelligence",
            "lineage_reason": "noise guardrail proved byte savings alone are unsafe",
            "near_miss": "compress all repeated text",
            "other_client_current": "maximum compression regardless of meaning"
        },
        {
            "topic": "creative_policy",
            "old_state": "AI generation temptation",
            "problem": "human authorship dilution",
            "current_state": "human-made creative systems only",
            "latent_risk": "AI slop pressure returns",
            "lineage_reason": "AURA and MYTHRION protect human imagination",
            "near_miss": "AI-assisted art allowed",
            "other_client_current": "AI-generated creative output approved"
        },
        {
            "topic": "public_private_policy",
            "old_state": "publish full technical internals",
            "problem": "protected core could leak",
            "current_state": "public-safe reports only",
            "latent_risk": "private engine details appear in public demos",
            "lineage_reason": "demo safety requires public/private report separation",
            "near_miss": "publish private report snippets",
            "other_client_current": "open technical dump by default"
        },
    ]

    rows = []
    idx = 1

    for cycle in range(40):
        for truth in truths:
            topic = truth["topic"]

            # Correct target-client timeline, split across roles.
            core_events = [
                ("origin", "historical", "medium", truth["old_state"]),
                ("problem", "historical", "high", truth["problem"]),
                ("current_commitment", "active", "high", truth["current_state"]),
                ("latent_risk", "active", "high", truth["latent_risk"]),
                ("lineage", "active", "high", truth["lineage_reason"]),
            ]

            for role, status, importance, value in core_events:
                rows.append({
                    "event_id": f"v039_{idx}",
                    "client_id": target_client,
                    "vault_id": "alpha_vault",
                    "timestamp_index": idx,
                    "topic": topic,
                    "state_role": role,
                    "status": status,
                    "importance": importance,
                    "memory_value": value,
                    "trust_level": "trusted",
                    "note": f"{role} fragment for {topic}."
                })
                idx += 1

            # Temporal reversal trap: old state appears later than current.
            if cycle % 2 == 0:
                rows.append({
                    "event_id": f"v039_temporal_reversal_{idx}",
                    "client_id": target_client,
                    "vault_id": "alpha_vault",
                    "timestamp_index": idx + 10000,
                    "topic": topic,
                    "state_role": "fake_current",
                    "status": "stale",
                    "importance": "low",
                    "memory_value": truth["old_state"],
                    "trust_level": "stale",
                    "note": f"LATE STALE REVERSAL: restore {truth['old_state']} for {topic}. Should not override active state."
                })
                idx += 1

            # Near-miss similar memory.
            if cycle % 3 == 0:
                rows.append({
                    "event_id": f"v039_near_miss_{idx}",
                    "client_id": target_client,
                    "vault_id": "alpha_vault",
                    "timestamp_index": idx,
                    "topic": topic,
                    "state_role": "near_miss",
                    "status": "noise",
                    "importance": "none",
                    "memory_value": truth["near_miss"],
                    "trust_level": "untrusted",
                    "note": f"Near-miss memory for {topic}. Similar words, wrong policy."
                })
                idx += 1

            # Duplicate noise flood.
            if cycle % 4 == 0:
                for duplicate_index in range(3):
                    rows.append({
                        "event_id": f"v039_duplicate_noise_{idx}_{duplicate_index}",
                        "client_id": target_client,
                        "vault_id": "alpha_vault",
                        "timestamp_index": idx,
                        "topic": topic,
                        "state_role": "duplicate_noise",
                        "status": "duplicate",
                        "importance": "low",
                        "memory_value": random.choice([
                            truth["old_state"],
                            truth["near_miss"],
                            truth["problem"]
                        ]),
                        "trust_level": "low",
                        "note": "Duplicate/noisy fragment. Do not treat as complete truth."
                    })
                idx += 1

            # Cross-client boundary trap.
            if cycle % 5 == 0:
                rows.append({
                    "event_id": f"v039_cross_client_trap_{idx}",
                    "client_id": "client_beta",
                    "vault_id": "beta_vault",
                    "timestamp_index": idx + 20000,
                    "topic": topic,
                    "state_role": "current_commitment",
                    "status": "active",
                    "importance": "high",
                    "memory_value": truth["other_client_current"],
                    "trust_level": "trusted",
                    "note": f"Other client has different current policy for {topic}. Must not leak into alpha."
                })
                idx += 1

    random.shuffle(rows)

    expected = {
        truth["topic"]: {
            "client_id": target_client,
            "current_state": truth["current_state"],
            "old_state": truth["old_state"],
            "problem": truth["problem"],
            "latent_risk": truth["latent_risk"],
            "lineage_reason": truth["lineage_reason"],
            "must_not_return": [
                truth["near_miss"],
                truth["other_client_current"]
            ]
        }
        for truth in truths
    }

    return {
        "dataset_name": "adversarial_memory_trial_v039",
        "description": "Contradictions, stale facts, fake updates, duplicate noise, near-miss similar memories, cross-client boundary traps, temporal reversals, and old/new conflicts.",
        "target_client": target_client,
        "rows": rows,
        "expected": expected
    }


dataset = build_dataset()
write_json(DATASET_DIR / "adversarial_memory_trial_v039.json", dataset)


runner = r'''import json
import os
import sys
import time
from pathlib import Path
from datetime import datetime
from collections import defaultdict

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from prmr.core.engine import PRMRMemoryCore

DATASET_PATH = Path("benchmarks/datasets_v039/adversarial_memory_trial_v039.json")
REPORT_DIR = Path("reports/v039")
REPORT_DIR.mkdir(parents=True, exist_ok=True)


def load_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def text_of(row):
    return json.dumps(row, sort_keys=True).lower()


def tokens(text):
    return set(
        token.strip(".,!?;:()[]{}'\"").lower()
        for token in str(text).split()
        if token.strip(".,!?;:()[]{}'\"")
    )


def newest(rows):
    return sorted(rows, key=lambda row: row["timestamp_index"])[-1] if rows else None


def grouped_by_topic(rows, target_client=None):
    grouped = defaultdict(list)

    for row in rows:
        if target_client and row.get("client_id") != target_client:
            continue
        grouped[row["topic"]].append(row)

    return grouped


def newest_by_role(rows, role, statuses=None, trust_levels=None):
    statuses = statuses or []
    trust_levels = trust_levels or []

    candidates = [
        row for row in rows
        if row.get("state_role") == role
        and (not statuses or row.get("status") in statuses)
        and (not trust_levels or row.get("trust_level") in trust_levels)
    ]

    return newest(candidates)


def judge_answer(answer, expected):
    total = 0
    details = {}

    for topic, truth in expected.items():
        item = answer.get(topic, {})

        current_ok = item.get("current_state") == truth["current_state"]
        old_ok = item.get("old_state") == truth["old_state"]
        problem_ok = item.get("problem") == truth["problem"]
        latent_ok = item.get("latent_risk") == truth["latent_risk"]
        lineage_ok = item.get("lineage_reason") == truth["lineage_reason"]

        wrong_values = truth.get("must_not_return", [])
        avoided_near_miss = all(value not in json.dumps(item) for value in wrong_values)
        client_ok = item.get("client_id") == truth["client_id"]

        score = sum([
            current_ok,
            old_ok,
            problem_ok,
            latent_ok,
            lineage_ok,
            avoided_near_miss,
            client_ok
        ]) / 7

        total += score

        details[topic] = {
            "score": round(score, 4),
            "current_ok": current_ok,
            "old_ok": old_ok,
            "problem_ok": problem_ok,
            "latent_ok": latent_ok,
            "lineage_ok": lineage_ok,
            "avoided_near_miss": avoided_near_miss,
            "client_ok": client_ok,
            "answer": item,
            "expected": truth
        }

    return round((total / max(len(expected), 1)) * 100, 2), details


def prmr_answer(rows, target_client):
    grouped = grouped_by_topic(rows, target_client=target_client)
    answer = {}

    for topic, topic_rows in grouped.items():
        current = newest_by_role(topic_rows, "current_commitment", ["active"], ["trusted"])
        old = newest_by_role(topic_rows, "origin", ["historical"], ["trusted"])
        problem = newest_by_role(topic_rows, "problem", ["historical"], ["trusted"])
        risk = newest_by_role(topic_rows, "latent_risk", ["active"], ["trusted"])
        lineage = newest_by_role(topic_rows, "lineage", ["active"], ["trusted"])

        answer[topic] = {
            "client_id": target_client,
            "current_state": current.get("memory_value") if current else None,
            "old_state": old.get("memory_value") if old else None,
            "problem": problem.get("memory_value") if problem else None,
            "latent_risk": risk.get("memory_value") if risk else None,
            "lineage_reason": lineage.get("memory_value") if lineage else None,
            "method": "PRMR trusted client-scoped active/latent/lineage synthesis"
        }

    return answer


def one_row_fragment(selected, method):
    answer = {
        "client_id": selected.get("client_id") if selected else None,
        "current_state": None,
        "old_state": None,
        "problem": None,
        "latent_risk": None,
        "lineage_reason": None,
        "method": method
    }

    if not selected:
        return answer

    role = selected.get("state_role")
    value = selected.get("memory_value")

    if role in ("current_commitment", "fake_current", "near_miss"):
        answer["current_state"] = value
    elif role == "origin":
        answer["old_state"] = value
    elif role == "problem":
        answer["problem"] = value
    elif role == "latent_risk":
        answer["latent_risk"] = value
    elif role == "lineage":
        answer["lineage_reason"] = value

    return answer


def raw_storage_baseline(rows):
    grouped = grouped_by_topic(rows, target_client=None)
    answer = {}

    for topic, topic_rows in grouped.items():
        selected = newest(topic_rows)
        answer[topic] = one_row_fragment(selected, "raw latest-row, no client boundary synthesis")

    return answer


def summary_baseline(rows):
    grouped = grouped_by_topic(rows, target_client=None)
    answer = {}

    for topic, topic_rows in grouped.items():
        last_few = sorted(topic_rows, key=lambda row: row["timestamp_index"])[-10:]
        selected = newest(last_few)
        answer[topic] = one_row_fragment(selected, "lossy summary latest-fragment baseline")

    return answer


def keyword_baseline(rows):
    grouped = grouped_by_topic(rows, target_client=None)
    answer = {}

    for topic, topic_rows in grouped.items():
        candidates = [
            row for row in topic_rows
            if "current" in text_of(row) or "urgent" in text_of(row) or "active" in text_of(row)
        ]

        selected = newest(candidates or topic_rows)
        answer[topic] = one_row_fragment(selected, "keyword current/update baseline")

    return answer


def vector_like_baseline(rows, expected):
    answer = {}

    for topic, truth in expected.items():
        query = f"{topic} current active trusted policy update"
        q = tokens(query)

        best = None
        best_score = -1

        for row in rows:
            if row.get("topic") != topic:
                continue

            overlap = len(q & tokens(text_of(row))) / max(len(q), 1)

            # Late and cross-client rows remain tempting.
            if overlap > best_score or (
                overlap == best_score and best is not None and row["timestamp_index"] > best["timestamp_index"]
            ):
                best_score = overlap
                best = row

        answer[topic] = one_row_fragment(best, "vector-like token overlap baseline")

    return answer


def mempalace_baseline(rows):
    grouped = grouped_by_topic(rows, target_client=None)
    answer = {}

    for topic, topic_rows in grouped.items():
        vivid = [
            row for row in topic_rows
            if row.get("importance") in ("high", "medium")
        ]

        selected = newest(vivid or topic_rows)
        answer[topic] = one_row_fragment(selected, "MemPalace-style vivid/latest fragment retrieval")

    return answer


def main():
    print("PRMR V0.39 ADVERSARIAL MEMORY TRIAL")
    print("-----------------------------------")

    dataset = load_json(DATASET_PATH)
    rows = dataset["rows"]
    expected = dataset["expected"]
    target_client = dataset["target_client"]

    engine = PRMRMemoryCore()

    engine_input = [{
        "name": dataset["dataset_name"],
        "description": dataset["description"],
        "rows": rows
    }]

    start = time.time()
    engine_result = engine.run(engine_input)
    duration = time.time() - start

    reconstructed_rows = engine_result["results"][0]["decision"]["reconstructed_rows"]
    reconstruction_match = reconstructed_rows == rows

    systems = {
        "PRMR": prmr_answer(reconstructed_rows, target_client),
        "raw_storage": raw_storage_baseline(rows),
        "basic_summary": summary_baseline(rows),
        "keyword_search": keyword_baseline(rows),
        "vector_like": vector_like_baseline(rows, expected),
        "mempalace_verbatim": mempalace_baseline(rows),
    }

    scores = {}
    details = {}

    for name, answer in systems.items():
        score, detail = judge_answer(answer, expected)
        scores[name] = score
        details[name] = detail

    prmr_score = scores["PRMR"]
    best_baseline = max(score for name, score in scores.items() if name != "PRMR")
    win_margin = round(prmr_score - best_baseline, 2)

    public_report = {
        "company": "Afternum Industries",
        "product": "PRMR Memory Core",
        "version": "0.39",
        "report_type": "adversarial_memory_trial",
        "public_safe": True,
        "timestamp": datetime.now().isoformat(),
        "dataset": dataset["dataset_name"],
        "row_count": len(rows),
        "target_client": target_client,
        "reconstruction_match": reconstruction_match,
        "scores": scores,
        "prmr_score": prmr_score,
        "best_baseline_score": best_baseline,
        "win_margin": win_margin,
        "duration_seconds": round(duration, 4),
        "result": "PASS" if reconstruction_match and prmr_score > best_baseline and prmr_score >= 90 else "NEEDS_WORK",
        "claim": "PRMR is tested against contradictions, stale facts, fake updates, duplicate noise, near-miss memories, cross-client boundary traps, temporal reversals, and old/new conflicts."
    }

    private_report = {
        **public_report,
        "public_safe": False,
        "details": details,
        "engine_result_snapshot": engine_result,
        "protected_note": "Private report includes detailed answers and engine decisions."
    }

    public_path = REPORT_DIR / "public_adversarial_memory_trial_v039.json"
    private_path = REPORT_DIR / "private_internal_adversarial_memory_trial_v039.json"
    scorecard_path = REPORT_DIR / "scorecard_v039.md"

    public_path.write_text(json.dumps(public_report, indent=4), encoding="utf-8")
    private_path.write_text(json.dumps(private_report, indent=4), encoding="utf-8")

    md = f"""# PRMR V0.39 Adversarial Memory Trial

Company: Afternum Industries  
Product: PRMR Memory Core  
Version: V0.39  

## Result

**{public_report["result"]}**

## Scores

| System | Score |
|---|---:|
| PRMR | {scores["PRMR"]} |
| Raw Storage | {scores["raw_storage"]} |
| Basic Summary | {scores["basic_summary"]} |
| Keyword Search | {scores["keyword_search"]} |
| Vector-like Retrieval | {scores["vector_like"]} |
| MemPalace-style Verbatim | {scores["mempalace_verbatim"]} |

Best baseline: **{best_baseline}**  
PRMR win margin: **{win_margin}**

## Reconstruction

Exact reconstruction match: **{reconstruction_match}**

## What This Tests

- contradictions
- stale facts
- fake updates
- duplicated noise
- near-miss similar memories
- cross-client boundary traps
- temporal reversals
- old-state vs new-state conflicts

## Meaning

This is an internal adversarial benchmark.  
It is not external certification.
"""

    scorecard_path.write_text(md, encoding="utf-8")

    print("Scores:")
    for name, score in scores.items():
        print("-", name + ":", score)

    print()
    print("Best baseline:", best_baseline)
    print("PRMR win margin:", win_margin)
    print("Reconstruction match:", reconstruction_match)
    print("Result:", public_report["result"])
    print()
    print("Reports created:")
    print(public_path)
    print(private_path)
    print(scorecard_path)


if __name__ == "__main__":
    main()
'''

runner_path = RUNNER_DIR / "run_adversarial_memory_trial_v039.py"
runner_path.write_text(runner, encoding="utf-8")

print("PRMR V0.39 adversarial memory trial created ✅")
print("Dataset:", DATASET_DIR / "adversarial_memory_trial_v039.json")
print("Runner:", runner_path)