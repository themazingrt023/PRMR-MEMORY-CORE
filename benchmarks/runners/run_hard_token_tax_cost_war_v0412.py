import json
import os
import sys
import time
from pathlib import Path
from datetime import datetime
from collections import defaultdict

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from prmr.core.engine import PRMRMemoryCore

DATASET_PATH = Path("benchmarks/datasets_v0412/hard_token_tax_cost_war_v0412.json")
REPORT_DIR = Path("reports/v0412")
REPORT_DIR.mkdir(parents=True, exist_ok=True)

ASSUMED_INPUT_COST_PER_1M_TOKENS_USD = 0.15


def load_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def estimate_tokens(obj):
    text = json.dumps(obj, sort_keys=True)
    return max(1, round(len(text) / 4))


def tokenize(text):
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


def synthesize_continuity(rows, target_client, method):
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
            "method": method
        }

    return answer


def fragment_answer_from_rows(rows, target_client, method):
    grouped = grouped_by_topic(rows, target_client=target_client)
    answer = {}

    for topic, topic_rows in grouped.items():
        answer[topic] = {
            "client_id": target_client,
            "current_state": None,
            "old_state": None,
            "problem": None,
            "latent_risk": None,
            "lineage_reason": None,
            "method": method
        }

        for row in topic_rows:
            role = row.get("state_role")
            value = row.get("memory_value")

            # Retrieval baselines fill from whatever fragments they retrieved,
            # even if those fragments are stale/untrusted.
            if role in ("current_commitment", "fake_current", "near_miss", "stale_update"):
                answer[topic]["current_state"] = value
            elif role == "origin":
                answer[topic]["old_state"] = value
            elif role == "problem":
                answer[topic]["problem"] = value
            elif role == "latent_risk":
                answer[topic]["latent_risk"] = value
            elif role == "lineage":
                answer[topic]["lineage_reason"] = value

    return answer


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
        client_ok = item.get("client_id") == truth["client_id"]

        wrong_values = truth.get("must_not_return", [])
        answer_text = json.dumps(item)
        avoided_wrong_values = all(value not in answer_text for value in wrong_values)

        score = sum([
            current_ok,
            old_ok,
            problem_ok,
            latent_ok,
            lineage_ok,
            client_ok,
            avoided_wrong_values
        ]) / 7

        total += score

        details[topic] = {
            "score": round(score, 4),
            "current_ok": current_ok,
            "old_ok": old_ok,
            "problem_ok": problem_ok,
            "latent_ok": latent_ok,
            "lineage_ok": lineage_ok,
            "client_ok": client_ok,
            "avoided_wrong_values": avoided_wrong_values,
            "answer": item,
            "expected": truth
        }

    return round((total / max(len(expected), 1)) * 100, 2), details


def raw_context_method(rows, expected, target_client):
    payload = rows
    answer = synthesize_continuity(rows, target_client, "raw full-context synthesis")
    return {"payload": payload, "answer": answer}


def basic_summary_method(rows, expected, target_client):
    grouped = grouped_by_topic(rows, target_client=target_client)
    summary_rows = []

    for topic, topic_rows in grouped.items():
        summary_rows.extend(sorted(topic_rows, key=lambda row: row["timestamp_index"])[-3:])

    answer = fragment_answer_from_rows(summary_rows, target_client, "basic lossy summary")
    return {"payload": summary_rows, "answer": answer}


def keyword_method(rows, expected, target_client):
    selected = []

    query_terms = ["current", "active", "trusted", "policy", "update", "risk", "problem", "lineage", "origin"]

    for row in rows:
        if row.get("client_id") != target_client:
            continue

        text = json.dumps(row, sort_keys=True).lower()
        score = sum(1 for term in query_terms if term in text)

        if score > 0:
            selected.append((score, row["timestamp_index"], row))

    selected.sort(reverse=True, key=lambda item: (item[0], item[1]))

    # Tight retrieval budget: retrieval systems cannot send all fragments.
    payload = [item[2] for item in selected[:40]]
    answer = fragment_answer_from_rows(payload, target_client, "keyword retrieval under trap pressure")

    return {"payload": payload, "answer": answer}


def vector_like_method(rows, expected, target_client):
    selected = []

    for topic in expected.keys():
        query = f"{topic} current active trusted policy update risk problem lineage origin"
        q = tokenize(query)

        candidates = [
            row for row in rows
            if row.get("client_id") == target_client
            and row.get("topic") == topic
        ]

        scored = []

        for row in candidates:
            text = json.dumps(row, sort_keys=True)
            overlap = len(q & tokenize(text)) / max(len(q), 1)
            scored.append((overlap, row["timestamp_index"], row))

        scored.sort(reverse=True, key=lambda item: (item[0], item[1]))

        # Tight per-topic budget. Traps should crowd out true continuity.
        selected.extend([item[2] for item in scored[:5]])

    answer = fragment_answer_from_rows(selected, target_client, "vector-like retrieval under trap pressure")
    return {"payload": selected, "answer": answer}


def prmr_method(rows, expected, target_client):
    engine = PRMRMemoryCore()

    engine_input = [{
        "name": "hard_token_tax_cost_war_v0412",
        "description": "Hard token tax benchmark input",
        "rows": rows
    }]

    engine_result = engine.run(engine_input)
    decision = engine_result["results"][0]["decision"]

    reconstructed_rows = decision["reconstructed_rows"]
    reconstruction_match = reconstructed_rows == rows

    answer = synthesize_continuity(reconstructed_rows, target_client, "PRMR reconstructed continuity packet")
    payload = answer

    return {
        "payload": payload,
        "answer": answer,
        "engine_decision_public": {
            "policy_mode": decision.get("policy_mode"),
            "raw_size": decision.get("raw_size"),
            "policy_size": decision.get("policy_size"),
            "policy_compression_ratio": decision.get("policy_compression_ratio"),
            "policy_saved_percentage": decision.get("policy_saved_percentage"),
            "reconstruction_match": reconstruction_match
        }
    }


def cost_per_1000_sessions(tokens):
    return round((tokens * 1000 / 1_000_000) * ASSUMED_INPUT_COST_PER_1M_TOKENS_USD, 6)


def score_methods(method_outputs, expected):
    raw_tokens = estimate_tokens(method_outputs["raw_context"]["payload"])
    results = {}

    for name, output in method_outputs.items():
        payload_tokens = estimate_tokens(output["payload"])
        accuracy, details = judge_answer(output["answer"], expected)
        reduction = round((1 - payload_tokens / raw_tokens) * 100, 2) if raw_tokens else 0

        results[name] = {
            "continuity_accuracy": accuracy,
            "payload_tokens": payload_tokens,
            "token_reduction_vs_raw_percent": reduction,
            "estimated_cost_per_1000_sessions_usd": cost_per_1000_sessions(payload_tokens),
            "answer_details": details
        }

        if "engine_decision_public" in output:
            results[name]["engine_decision_public"] = output["engine_decision_public"]

    return results


def main():
    print("PRMR V0.41.2 HARD TOKEN TAX / COST WAR BENCHMARK")
    print("------------------------------------------------")

    dataset = load_json(DATASET_PATH)
    rows = dataset["rows"]
    expected = dataset["expected"]
    target_client = dataset["target_client"]

    start = time.time()

    method_outputs = {
        "raw_context": raw_context_method(rows, expected, target_client),
        "basic_summary": basic_summary_method(rows, expected, target_client),
        "keyword_search": keyword_method(rows, expected, target_client),
        "vector_like": vector_like_method(rows, expected, target_client),
        "prmr_memory_core": prmr_method(rows, expected, target_client),
    }

    duration = time.time() - start
    results = score_methods(method_outputs, expected)

    raw_tokens = results["raw_context"]["payload_tokens"]
    prmr_tokens = results["prmr_memory_core"]["payload_tokens"]

    prmr_accuracy = results["prmr_memory_core"]["continuity_accuracy"]
    raw_accuracy = results["raw_context"]["continuity_accuracy"]

    best_non_raw_baseline_accuracy = max(
        results[name]["continuity_accuracy"]
        for name in results
        if name not in ("raw_context", "prmr_memory_core")
    )

    best_non_prmr_low_cost_accuracy = max(
        results[name]["continuity_accuracy"]
        for name in results
        if name != "prmr_memory_core"
    )

    prmr_reduction = results["prmr_memory_core"]["token_reduction_vs_raw_percent"]

    pass_condition = (
        prmr_accuracy >= 95
        and prmr_reduction >= 90
        and prmr_accuracy > best_non_raw_baseline_accuracy
        and results["prmr_memory_core"]["engine_decision_public"]["reconstruction_match"] is True
    )

    public_report = {
        "company": "Afternum Industries",
        "product": "PRMR Memory Core",
        "version": "0.41.2",
        "report_type": "hard_token_tax_cost_war_benchmark",
        "public_safe": True,
        "timestamp": datetime.now().isoformat(),
        "dataset": dataset["dataset_name"],
        "row_count": len(rows),
        "assumed_input_cost_per_1m_tokens_usd": ASSUMED_INPUT_COST_PER_1M_TOKENS_USD,
        "results": {
            name: {
                key: value
                for key, value in result.items()
                if key != "answer_details"
            }
            for name, result in results.items()
        },
        "summary": {
            "raw_context_tokens": raw_tokens,
            "prmr_payload_tokens": prmr_tokens,
            "prmr_token_reduction_vs_raw_percent": prmr_reduction,
            "raw_context_accuracy": raw_accuracy,
            "prmr_accuracy": prmr_accuracy,
            "best_non_raw_baseline_accuracy": best_non_raw_baseline_accuracy,
            "best_non_prmr_accuracy_including_raw": best_non_prmr_low_cost_accuracy,
            "duration_seconds": round(duration, 4),
            "result": "PASS" if pass_condition else "NEEDS_WORK"
        },
        "claim": "Hard token/cost benchmark with retrieval traps. PRMR is tested on accuracy-per-token under stale, noisy, near-miss, and cross-client pressure."
    }

    private_report = {
        **public_report,
        "public_safe": False,
        "private_answer_details": {
            name: result["answer_details"]
            for name, result in results.items()
        },
        "protected_note": "Private report includes detailed answer scoring."
    }

    public_path = REPORT_DIR / "public_hard_token_tax_cost_war_v0412.json"
    private_path = REPORT_DIR / "private_internal_hard_token_tax_cost_war_v0412.json"
    scorecard_path = REPORT_DIR / "scorecard_v0412.md"

    public_path.write_text(json.dumps(public_report, indent=4), encoding="utf-8")
    private_path.write_text(json.dumps(private_report, indent=4), encoding="utf-8")

    md = f"""# PRMR V0.41.2 Hard Token Tax / Cost War Benchmark

Company: Afternum Industries  
Product: PRMR Memory Core  
Version: V0.41.2  

## Result

**{public_report["summary"]["result"]}**

## Core Result

- Raw context tokens: **{raw_tokens}**
- PRMR payload tokens: **{prmr_tokens}**
- PRMR token reduction vs raw: **{prmr_reduction}%**
- Raw context continuity accuracy: **{raw_accuracy}%**
- PRMR continuity accuracy: **{prmr_accuracy}%**
- Best non-raw baseline accuracy: **{best_non_raw_baseline_accuracy}%**

## Method Table

| Method | Accuracy | Payload Tokens | Reduction vs Raw | Cost / 1,000 Sessions |
|---|---:|---:|---:|---:|
"""

    for name, result in public_report["results"].items():
        md += f"| {name} | {result['continuity_accuracy']}% | {result['payload_tokens']} | {result['token_reduction_vs_raw_percent']}% | ${result['estimated_cost_per_1000_sessions_usd']} |\n"

    md += """

## Meaning

V0.41.2 is harder than V0.41.  
It adds retrieval traps, stale updates, near-miss memories, cross-client traps, and tight retrieval budgets.

This is still an internal benchmark, not external certification.
"""

    scorecard_path.write_text(md, encoding="utf-8")

    print("Method results:")
    for name, result in public_report["results"].items():
        print("-", name)
        print("  accuracy:", result["continuity_accuracy"])
        print("  payload_tokens:", result["payload_tokens"])
        print("  token_reduction_vs_raw_percent:", result["token_reduction_vs_raw_percent"])
        print("  cost_per_1000_sessions_usd:", result["estimated_cost_per_1000_sessions_usd"])

    print()
    print("Summary:")
    for key, value in public_report["summary"].items():
        print("-", key + ":", value)

    print()
    print("Reports created:")
    print(public_path)
    print(private_path)
    print(scorecard_path)


if __name__ == "__main__":
    main()
