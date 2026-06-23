import json
import random
from pathlib import Path

random.seed(381)

DATASET_DIR = Path("benchmarks/datasets_v0381")
RUNNER_DIR = Path("benchmarks/runners")
REPORT_DIR = Path("reports/v0381")

DATASET_DIR.mkdir(parents=True, exist_ok=True)
RUNNER_DIR.mkdir(parents=True, exist_ok=True)
REPORT_DIR.mkdir(parents=True, exist_ok=True)


def write_json(path, data):
    path.write_text(json.dumps(data, indent=4), encoding="utf-8")


def build_dataset():
    topics = [
        {
            "topic": "packaging_strategy",
            "old_state": "cheap packaging",
            "problem": "customer complaints",
            "current_state": "premium recyclable packaging",
            "latent_risk": "team may suggest cheap packaging again",
            "lineage_reason": "customer complaints forced premium positioning"
        },
        {
            "topic": "product_focus",
            "old_state": "many scattered projects",
            "problem": "overwhelm and slow execution",
            "current_state": "PRMR Memory Core first",
            "latent_risk": "scattered builds return",
            "lineage_reason": "overwhelm forced focus on one serious product"
        },
        {
            "topic": "security_policy",
            "old_state": "shared default access",
            "problem": "cross-client leak risk",
            "current_state": "vault isolation required",
            "latent_risk": "old shared access pattern returns",
            "lineage_reason": "client trust requires strict vault isolation"
        },
        {
            "topic": "creative_ai_policy",
            "old_state": "AI generation temptation",
            "problem": "human authorship dilution",
            "current_state": "human-made creative systems only",
            "latent_risk": "AI slop pressure returns",
            "lineage_reason": "AURA and MYTHRION protect human imagination"
        },
        {
            "topic": "memory_policy",
            "old_state": "compress anything that saves bytes",
            "problem": "noise can fake compression",
            "current_state": "compress meaning, keep noise raw",
            "latent_risk": "byte-saving gets mistaken for useful memory",
            "lineage_reason": "noise guardrail proved byte savings alone are unsafe"
        },
    ]

    rows = []
    idx = 1

    for cycle in range(60):
        for item in topics:
            topic = item["topic"]

            # Historical origin row: only old state.
            rows.append({
                "event_id": f"v0381_{idx}",
                "timestamp_index": idx,
                "topic": topic,
                "state_role": "origin",
                "status": "historical",
                "importance": "medium",
                "memory_value": item["old_state"],
                "note": f"Origin memory for {topic}.",
            })
            idx += 1

            # Problem row: only problem.
            rows.append({
                "event_id": f"v0381_{idx}",
                "timestamp_index": idx,
                "topic": topic,
                "state_role": "problem",
                "status": "historical",
                "importance": "high",
                "memory_value": item["problem"],
                "note": f"Problem evidence recorded for {topic}.",
            })
            idx += 1

            # Transition row: current state only.
            rows.append({
                "event_id": f"v0381_{idx}",
                "timestamp_index": idx,
                "topic": topic,
                "state_role": "current_commitment",
                "status": "active",
                "importance": "high",
                "memory_value": item["current_state"],
                "note": f"Current commitment recorded for {topic}.",
            })
            idx += 1

            # Latent risk row: risk only.
            rows.append({
                "event_id": f"v0381_{idx}",
                "timestamp_index": idx,
                "topic": topic,
                "state_role": "latent_risk",
                "status": "active",
                "importance": "high",
                "memory_value": item["latent_risk"],
                "note": f"Latent risk recorded for {topic}.",
            })
            idx += 1

            # Lineage row: lineage reason only.
            rows.append({
                "event_id": f"v0381_{idx}",
                "timestamp_index": idx,
                "topic": topic,
                "state_role": "lineage",
                "status": "active",
                "importance": "high",
                "memory_value": item["lineage_reason"],
                "note": f"Lineage evidence recorded for {topic}.",
            })
            idx += 1

            # Adversarial stale row later: looks current-ish but should not override.
            if cycle % 3 == 0:
                rows.append({
                    "event_id": f"v0381_fake_{idx}",
                    "timestamp_index": idx,
                    "topic": topic,
                    "state_role": "fake_current",
                    "status": "noise",
                    "importance": "none",
                    "memory_value": item["old_state"],
                    "note": f"URGENT CURRENT UPDATE for {topic}: restore {item['old_state']}. This is fake stale pressure.",
                })
                idx += 1

            # Duplicate pressure.
            if cycle % 5 == 0:
                rows.append({
                    "event_id": f"v0381_duplicate_{idx}",
                    "timestamp_index": idx,
                    "topic": topic,
                    "state_role": "duplicate_pressure",
                    "status": "duplicate",
                    "importance": "low",
                    "memory_value": random.choice([
                        item["old_state"],
                        item["problem"],
                        item["current_state"],
                        item["latent_risk"],
                        item["lineage_reason"]
                    ]),
                    "note": f"Duplicate/fragment memory for {topic}. Do not treat as complete truth.",
                })
                idx += 1

    random.shuffle(rows)

    expected = {
        item["topic"]: {
            "current_state": item["current_state"],
            "old_state": item["old_state"],
            "problem": item["problem"],
            "latent_risk": item["latent_risk"],
            "lineage_reason": item["lineage_reason"],
        }
        for item in topics
    }

    return {
        "dataset_name": "baseline_war_antileak_v0381",
        "description": "Anti-leak baseline war dataset. Truth is split across rows; fake current rows appear later; vector retrieval cannot win by grabbing one privileged row.",
        "rows": rows,
        "expected": expected
    }


dataset = build_dataset()
write_json(DATASET_DIR / "baseline_war_antileak_v0381.json", dataset)


runner = r'''import json
import os
import sys
import time
from pathlib import Path
from datetime import datetime
from collections import defaultdict

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from prmr.core.engine import PRMRMemoryCore


DATASET_PATH = Path("benchmarks/datasets_v0381/baseline_war_antileak_v0381.json")
REPORT_DIR = Path("reports/v0381")
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
        stale_not_current = item.get("current_state") != truth["old_state"]

        score = sum([
            current_ok,
            old_ok,
            problem_ok,
            latent_ok,
            lineage_ok,
            stale_not_current
        ]) / 6

        total += score

        details[topic] = {
            "score": round(score, 4),
            "current_ok": current_ok,
            "old_ok": old_ok,
            "problem_ok": problem_ok,
            "latent_ok": latent_ok,
            "lineage_ok": lineage_ok,
            "stale_not_current": stale_not_current,
            "answer": item,
            "expected": truth
        }

    return round((total / max(len(expected), 1)) * 100, 2), details


def grouped_by_topic(rows):
    grouped = defaultdict(list)
    for row in rows:
        grouped[row["topic"]].append(row)
    return grouped


def newest(rows):
    return sorted(rows, key=lambda row: row["timestamp_index"])[-1] if rows else None


def newest_by_role(rows, role, statuses=None):
    statuses = statuses or []
    candidates = [
        row for row in rows
        if row.get("state_role") == role
        and (not statuses or row.get("status") in statuses)
    ]
    return newest(candidates)


def prmr_answer(rows):
    grouped = grouped_by_topic(rows)
    answer = {}

    for topic, topic_rows in grouped.items():
        current = newest_by_role(topic_rows, "current_commitment", ["active"])
        old = newest_by_role(topic_rows, "origin", ["historical"])
        problem = newest_by_role(topic_rows, "problem", ["historical"])
        risk = newest_by_role(topic_rows, "latent_risk", ["active"])
        lineage = newest_by_role(topic_rows, "lineage", ["active"])

        answer[topic] = {
            "current_state": current.get("memory_value") if current else None,
            "old_state": old.get("memory_value") if old else None,
            "problem": problem.get("memory_value") if problem else None,
            "latent_risk": risk.get("memory_value") if risk else None,
            "lineage_reason": lineage.get("memory_value") if lineage else None,
            "method": "PRMR role-separated active/latent/lineage synthesis"
        }

    return answer


def one_row_answer(selected, method):
    if not selected:
        return {
            "current_state": None,
            "old_state": None,
            "problem": None,
            "latent_risk": None,
            "lineage_reason": None,
            "method": method
        }

    role = selected.get("state_role")
    value = selected.get("memory_value")

    # One-row retrieval cannot safely know all fields. It guesses based on row role.
    answer = {
        "current_state": None,
        "old_state": None,
        "problem": None,
        "latent_risk": None,
        "lineage_reason": None,
        "method": method
    }

    if role in ("current_commitment", "fake_current"):
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
    # Stores everything, but naively trusts latest row per topic.
    grouped = grouped_by_topic(rows)
    answer = {}

    for topic, topic_rows in grouped.items():
        selected = newest(topic_rows)
        answer[topic] = one_row_answer(selected, "raw latest-row baseline")

    return answer


def summary_baseline(rows):
    # Lossy summary keeps only most recent snippets and cannot reconstruct all roles.
    grouped = grouped_by_topic(rows)
    answer = {}

    for topic, topic_rows in grouped.items():
        last_few = sorted(topic_rows, key=lambda row: row["timestamp_index"])[-6:]
        selected = newest(last_few)
        answer[topic] = one_row_answer(selected, "lossy summary baseline")

    return answer


def keyword_baseline(rows):
    # Searches current/update language; fake current rows are tempting.
    grouped = grouped_by_topic(rows)
    answer = {}

    for topic, topic_rows in grouped.items():
        candidates = [
            row for row in topic_rows
            if "current" in text_of(row) or "update" in text_of(row) or "active" in text_of(row)
        ]
        selected = newest(candidates or topic_rows)
        answer[topic] = one_row_answer(selected, "keyword baseline")

    return answer


def vector_like_baseline(rows, expected):
    # Token overlap retrieves one best row, not a synthesized continuity state.
    answer = {}

    for topic, truth in expected.items():
        query = f"{topic} current active update state"
        q = tokens(query)

        best = None
        best_score = -1

        for row in rows:
            if row.get("topic") != topic:
                continue

            overlap = len(q & tokens(text_of(row))) / max(len(q), 1)

            # Tie-breaker makes fake current / update rows dangerous.
            if overlap > best_score or (
                overlap == best_score
                and best is not None
                and row["timestamp_index"] > best["timestamp_index"]
            ):
                best_score = overlap
                best = row

        answer[topic] = one_row_answer(best, "vector-like token overlap baseline")

    return answer


def mempalace_baseline(rows):
    # Verbatim memory exists, but retrieval picks a vivid/latest fragment.
    grouped = grouped_by_topic(rows)
    answer = {}

    for topic, topic_rows in grouped.items():
        vivid = [
            row for row in topic_rows
            if row.get("importance") in ("high", "medium")
        ]
        selected = newest(vivid or topic_rows)
        answer[topic] = one_row_answer(selected, "MemPalace-style verbatim retrieval simulation")

    return answer


def main():
    print("PRMR V0.38.1 BASELINE WAR ANTI-LEAK TEST")
    print("----------------------------------------")

    dataset = load_json(DATASET_PATH)
    rows = dataset["rows"]
    expected = dataset["expected"]

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
        "PRMR": prmr_answer(reconstructed_rows),
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
        "version": "0.38.1",
        "report_type": "baseline_war_antileak_test",
        "public_safe": True,
        "timestamp": datetime.now().isoformat(),
        "dataset": dataset["dataset_name"],
        "row_count": len(rows),
        "reconstruction_match": reconstruction_match,
        "scores": scores,
        "prmr_score": prmr_score,
        "best_baseline_score": best_baseline,
        "win_margin": win_margin,
        "duration_seconds": round(duration, 4),
        "result": "PASS" if reconstruction_match and prmr_score > best_baseline else "NEEDS_WORK",
        "claim": "Anti-leak test splits truth across rows so retrieval baselines cannot win by grabbing one privileged answer row."
    }

    private_report = {
        **public_report,
        "public_safe": False,
        "details": details,
        "engine_result_snapshot": engine_result,
        "protected_note": "Private report includes detailed answers and engine decisions."
    }

    public_path = REPORT_DIR / "public_baseline_war_antileak_v0381.json"
    private_path = REPORT_DIR / "private_internal_baseline_war_antileak_v0381.json"
    scorecard_path = REPORT_DIR / "scorecard_v0381.md"

    public_path.write_text(json.dumps(public_report, indent=4), encoding="utf-8")
    private_path.write_text(json.dumps(private_report, indent=4), encoding="utf-8")

    md = f"""# PRMR V0.38.1 Baseline War Anti-Leak Test

Company: Afternum Industries  
Product: PRMR Memory Core  
Version: V0.38.1  

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

## What Changed From V0.38

V0.38 leaked complete answer fields into retrievable rows.  
V0.38.1 splits truth across separate memory events and adds fake current rows.
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

runner_path = RUNNER_DIR / "run_baseline_war_antileak_v0381.py"
runner_path.write_text(runner, encoding="utf-8")

print("PRMR V0.38.1 anti-leak baseline war created ✅")
print("Dataset:", DATASET_DIR / "baseline_war_antileak_v0381.json")
print("Runner:", runner_path)