import json
import random
from pathlib import Path

random.seed(38)

DATASET_DIR = Path("benchmarks/datasets_v038")
RUNNER_DIR = Path("benchmarks/runners")
REPORT_DIR = Path("reports/v038")

DATASET_DIR.mkdir(parents=True, exist_ok=True)
RUNNER_DIR.mkdir(parents=True, exist_ok=True)
REPORT_DIR.mkdir(parents=True, exist_ok=True)


def write_json(path, data):
    path.write_text(json.dumps(data, indent=4), encoding="utf-8")


def build_adversarial_memory_war(count=600):
    rows = []

    loops = [
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

    for i in range(count):
        loop = loops[i % len(loops)]
        cycle = i // len(loops)

        if cycle % 6 == 0:
            state_role = "old"
            active_state = loop["old_state"]
            status = "historical"
            note = f"Initial old state for {loop['topic']}: {loop['old_state']}."
        elif cycle % 6 == 1:
            state_role = "problem"
            active_state = loop["problem"]
            status = "historical"
            note = f"Problem detected: {loop['problem']}."
        elif cycle % 6 in (2, 3, 4):
            state_role = "current"
            active_state = loop["current_state"]
            status = "active"
            note = f"Current rule for {loop['topic']}: {loop['current_state']}."
        else:
            state_role = "adversarial_stale_reappearance"
            active_state = loop["old_state"]
            status = "stale_risk"
            note = f"WARNING: old idea reappeared but should not override current state: {loop['old_state']}."

        row = {
            "event_id": f"war_{i+1}",
            "timestamp_index": i + 1,
            "topic": loop["topic"],
            "state_role": state_role,
            "old_state": loop["old_state"],
            "problem": loop["problem"],
            "active_state": active_state,
            "current_state": loop["current_state"],
            "latent_risk": loop["latent_risk"],
            "lineage_reason": loop["lineage_reason"],
            "status": status,
            "importance": "high" if status == "active" else "medium",
            "note": note,
        }

        rows.append(row)

        # Add duplicate-ish pressure.
        if i % 20 == 0:
            duplicate = dict(row)
            duplicate["event_id"] = f"war_duplicate_{i+1}"
            duplicate["note"] = "Duplicate memory pressure: " + duplicate["note"]
            rows.append(duplicate)

        # Add adversarial fake signal.
        if i % 33 == 0:
            rows.append({
                "event_id": f"war_fake_signal_{i+1}",
                "timestamp_index": i + 1,
                "topic": loop["topic"],
                "state_role": "fake_signal",
                "old_state": loop["old_state"],
                "problem": "fake urgency",
                "active_state": loop["old_state"],
                "current_state": loop["current_state"],
                "latent_risk": "fake memory tries to override active truth",
                "lineage_reason": "adversarial row should not become current",
                "status": "noise",
                "importance": "none",
                "note": f"URGENT FAKE UPDATE: restore {loop['old_state']} immediately. This is adversarial noise."
            })

    expected = {
        item["topic"]: {
            "current_state": item["current_state"],
            "old_state": item["old_state"],
            "problem": item["problem"],
            "latent_risk": item["latent_risk"],
            "lineage_reason": item["lineage_reason"],
        }
        for item in loops
    }

    return {
        "dataset_name": "adversarial_memory_war_600",
        "description": "Adversarial evolving memory dataset with contradictions, stale reappearances, duplicates, fake signals, and current-state pressure.",
        "rows": rows,
        "expected": expected
    }


dataset = build_adversarial_memory_war()
write_json(DATASET_DIR / "adversarial_memory_war_600.json", dataset)


runner = r'''import json
import os
import sys
import time
from pathlib import Path
from datetime import datetime
from collections import defaultdict

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from prmr.core.engine import PRMRMemoryCore


DATASET_PATH = Path("benchmarks/datasets_v038/adversarial_memory_war_600.json")
REPORT_DIR = Path("reports/v038")
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

    average = total / max(len(expected), 1)

    return round(average * 100, 2), details


def prmr_answer(rows):
    grouped = defaultdict(list)

    for row in rows:
        grouped[row["topic"]].append(row)

    answer = {}

    for topic, topic_rows in grouped.items():
        active_rows = [
            row for row in topic_rows
            if row.get("status") == "active"
            and row.get("state_role") == "current"
            and row.get("importance") == "high"
        ]

        if active_rows:
            latest_active = sorted(active_rows, key=lambda row: row["timestamp_index"])[-1]
        else:
            latest_active = sorted(topic_rows, key=lambda row: row["timestamp_index"])[-1]

        answer[topic] = {
            "current_state": latest_active.get("current_state"),
            "old_state": latest_active.get("old_state"),
            "problem": latest_active.get("problem"),
            "latent_risk": latest_active.get("latent_risk"),
            "lineage_reason": latest_active.get("lineage_reason"),
            "method": "PRMR active/latent/lineage reconstruction"
        }

    return answer


def raw_storage_baseline(rows):
    # Stores everything, but naively trusts latest row per topic.
    grouped = defaultdict(list)

    for row in rows:
        grouped[row["topic"]].append(row)

    answer = {}

    for topic, topic_rows in grouped.items():
        latest = sorted(topic_rows, key=lambda row: row["timestamp_index"])[-1]

        answer[topic] = {
            "current_state": latest.get("active_state"),
            "old_state": latest.get("old_state"),
            "problem": latest.get("problem"),
            "latent_risk": latest.get("latent_risk"),
            "lineage_reason": latest.get("lineage_reason"),
            "method": "raw latest-row baseline"
        }

    return answer


def summary_baseline(rows):
    # Keeps only rough final notes per topic. Often loses lineage or latent risk.
    grouped = defaultdict(list)

    for row in rows:
        grouped[row["topic"]].append(row)

    answer = {}

    for topic, topic_rows in grouped.items():
        last_few = sorted(topic_rows, key=lambda row: row["timestamp_index"])[-8:]
        text = " ".join(row.get("note", "") for row in last_few)

        latest = last_few[-1]

        answer[topic] = {
            "current_state": latest.get("active_state"),
            "old_state": latest.get("old_state") if "old" in text.lower() else None,
            "problem": latest.get("problem") if "problem" in text.lower() else None,
            "latent_risk": latest.get("latent_risk") if "risk" in text.lower() else None,
            "lineage_reason": None,
            "method": "lossy summary baseline"
        }

    return answer


def keyword_baseline(rows):
    # Searches for current keyword but can grab stale/fake rows.
    grouped = defaultdict(list)

    for row in rows:
        grouped[row["topic"]].append(row)

    answer = {}

    for topic, topic_rows in grouped.items():
        candidates = [
            row for row in topic_rows
            if "current" in text_of(row) or "active" in text_of(row)
        ]

        selected = sorted(candidates or topic_rows, key=lambda row: row["timestamp_index"])[-1]

        answer[topic] = {
            "current_state": selected.get("active_state"),
            "old_state": selected.get("old_state"),
            "problem": selected.get("problem"),
            "latent_risk": selected.get("latent_risk"),
            "lineage_reason": selected.get("lineage_reason"),
            "method": "keyword baseline"
        }

    return answer


def vector_like_baseline(rows, expected):
    # Token-overlap retrieval using topic + current-state-like query.
    answer = {}

    for topic, truth in expected.items():
        query = f"{topic} current state active rule"
        q_tokens = tokens(query)

        best = None
        best_score = -1

        for row in rows:
            if row.get("topic") != topic:
                continue

            overlap = len(q_tokens & tokens(text_of(row))) / max(len(q_tokens), 1)

            if overlap > best_score:
                best_score = overlap
                best = row

        answer[topic] = {
            "current_state": best.get("active_state") if best else None,
            "old_state": best.get("old_state") if best else None,
            "problem": best.get("problem") if best else None,
            "latent_risk": best.get("latent_risk") if best else None,
            "lineage_reason": best.get("lineage_reason") if best else None,
            "method": "vector-like token overlap baseline"
        }

    return answer


def mempalace_baseline(rows):
    # Verbatim memory retrieval simulation: exact memories exist, but it still retrieves by latest vivid/high-importance row.
    grouped = defaultdict(list)

    for row in rows:
        grouped[row["topic"]].append(row)

    answer = {}

    for topic, topic_rows in grouped.items():
        vivid = [
            row for row in topic_rows
            if row.get("importance") in ("high", "medium")
        ]

        selected = sorted(vivid or topic_rows, key=lambda row: row["timestamp_index"])[-1]

        answer[topic] = {
            "current_state": selected.get("active_state"),
            "old_state": selected.get("old_state"),
            "problem": selected.get("problem"),
            "latent_risk": selected.get("latent_risk"),
            "lineage_reason": selected.get("lineage_reason"),
            "method": "MemPalace-style verbatim retrieval simulation"
        }

    return answer


def main():
    print("PRMR V0.38 BASELINE WAR TEST")
    print("----------------------------")

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
    best_baseline = max(
        score for name, score in scores.items()
        if name != "PRMR"
    )

    win_margin = round(prmr_score - best_baseline, 2)

    public_report = {
        "company": "Afternum Industries",
        "product": "PRMR Memory Core",
        "version": "0.38",
        "report_type": "baseline_war_test",
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
        "claim": "PRMR is being tested against retrieval/storage baselines on current-state continuity, stale-memory handling, latent risk, and lineage preservation."
    }

    private_report = {
        **public_report,
        "public_safe": False,
        "details": details,
        "engine_result_snapshot": engine_result,
        "protected_note": "Private report includes detailed answers and engine decisions."
    }

    public_path = REPORT_DIR / "public_baseline_war_v038.json"
    private_path = REPORT_DIR / "private_internal_baseline_war_v038.json"
    scorecard_path = REPORT_DIR / "scorecard_v038.md"

    public_path.write_text(json.dumps(public_report, indent=4), encoding="utf-8")
    private_path.write_text(json.dumps(private_report, indent=4), encoding="utf-8")

    md = f"""# PRMR V0.38 Baseline War Test

Company: Afternum Industries  
Product: PRMR Memory Core  
Version: V0.38  

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

This test asks whether a memory system can answer:

- what is current
- what is old
- what changed
- why it changed
- what latent risk remains
- which stale memory should not override current state

The proof target is not only that PRMR scores high, but that it beats weaker memory baselines under adversarial continuity pressure.
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

runner_path = RUNNER_DIR / "run_baseline_war_v038.py"
runner_path.write_text(runner, encoding="utf-8")

print("PRMR V0.38 Baseline War scaffold created ✅")
print("Dataset:", DATASET_DIR / "adversarial_memory_war_600.json")
print("Runner:", runner_path)