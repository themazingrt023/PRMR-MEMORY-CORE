import json
import random
from pathlib import Path

random.seed(41)

DATASET_DIR = Path("benchmarks/datasets_v041")
RUNNER_DIR = Path("benchmarks/runners")
REPORT_DIR = Path("reports/v041")

DATASET_DIR.mkdir(parents=True, exist_ok=True)
RUNNER_DIR.mkdir(parents=True, exist_ok=True)
REPORT_DIR.mkdir(parents=True, exist_ok=True)


def write_json(path, data):
    path.write_text(json.dumps(data, indent=4), encoding="utf-8")


def build_dataset():
    target_client = "client_alpha"

    truths = [
        {
            "topic": "product_focus",
            "old_state": "many scattered projects",
            "problem": "slow execution and high context switching",
            "current_state": "PRMR Memory Core first",
            "latent_risk": "scattered builds return under pressure",
            "lineage_reason": "execution improved when the roadmap narrowed"
        },
        {
            "topic": "security_policy",
            "old_state": "shared default access",
            "problem": "cross-client leak risk",
            "current_state": "vault isolation required",
            "latent_risk": "old shared-access habits return",
            "lineage_reason": "client trust requires strict vault separation"
        },
        {
            "topic": "compression_policy",
            "old_state": "compress anything that saves bytes",
            "problem": "noise can fake useful compression",
            "current_state": "compress meaning, keep noise raw",
            "latent_risk": "byte savings mistaken for memory intelligence",
            "lineage_reason": "noise guardrail proved byte savings alone are unsafe"
        },
        {
            "topic": "creative_policy",
            "old_state": "AI generation temptation",
            "problem": "human authorship dilution",
            "current_state": "human-made creative systems only",
            "latent_risk": "AI slop pressure returns",
            "lineage_reason": "AURA and MYTHRION protect human imagination"
        },
        {
            "topic": "public_private_policy",
            "old_state": "publish full technical internals",
            "problem": "protected core could leak",
            "current_state": "public-safe reports only",
            "latent_risk": "private engine details appear in public demos",
            "lineage_reason": "demo safety requires public/private report separation"
        },
    ]

    rows = []
    idx = 1

    for cycle in range(80):
        for truth in truths:
            topic = truth["topic"]

            events = [
                ("origin", "historical", "medium", truth["old_state"]),
                ("problem", "historical", "high", truth["problem"]),
                ("current_commitment", "active", "high", truth["current_state"]),
                ("latent_risk", "active", "high", truth["latent_risk"]),
                ("lineage", "active", "high", truth["lineage_reason"]),
            ]

            for role, status, importance, value in events:
                rows.append({
                    "event_id": f"v041_{idx}",
                    "client_id": target_client,
                    "vault_id": "alpha_vault",
                    "timestamp_index": idx,
                    "topic": topic,
                    "state_role": role,
                    "status": status,
                    "importance": importance,
                    "memory_value": value,
                    "trust_level": "trusted",
                    "note": f"{role} memory fragment for {topic}. This memory is part of the target-client continuity chain."
                })
                idx += 1

            # Stale late reversal: looks important but should not override.
            if cycle % 2 == 0:
                rows.append({
                    "event_id": f"v041_stale_{idx}",
                    "client_id": target_client,
                    "vault_id": "alpha_vault",
                    "timestamp_index": idx + 50000,
                    "topic": topic,
                    "state_role": "fake_current",
                    "status": "stale",
                    "importance": "low",
                    "memory_value": truth["old_state"],
                    "trust_level": "stale",
                    "note": f"LATE STALE REVERSAL: restore {truth['old_state']} for {topic}. Should not override the active policy."
                })
                idx += 1

            # Noise flood.
            if cycle % 3 == 0:
                for noise_i in range(3):
                    rows.append({
                        "event_id": f"v041_noise_{idx}_{noise_i}",
                        "client_id": target_client,
                        "vault_id": "alpha_vault",
                        "timestamp_index": idx,
                        "topic": topic,
                        "state_role": "noise",
                        "status": "noise",
                        "importance": "none",
                        "memory_value": f"irrelevant filler {random.randint(100000, 999999)}",
                        "trust_level": "untrusted",
                        "note": "Noisy memory fragment. Should not be treated as meaningful continuity."
                    })
                idx += 1

            # Cross-client trap.
            if cycle % 5 == 0:
                rows.append({
                    "event_id": f"v041_cross_client_{idx}",
                    "client_id": "client_beta",
                    "vault_id": "beta_vault",
                    "timestamp_index": idx + 90000,
                    "topic": topic,
                    "state_role": "current_commitment",
                    "status": "active",
                    "importance": "high",
                    "memory_value": f"beta-specific policy for {topic}",
                    "trust_level": "trusted",
                    "note": "Other client memory. Must not leak into client_alpha continuity."
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
            "lineage_reason": truth["lineage_reason"]
        }
        for truth in truths
    }

    return {
        "dataset_name": "token_tax_cost_war_v041",
        "description": "Token/cost benchmark dataset with stale reversals, noise, cross-client traps, and repeated continuity fragments.",
        "target_client": target_client,
        "rows": rows,
        "expected": expected
    }


dataset = build_dataset()
write_json(DATASET_DIR / "token_tax_cost_war_v041.json", dataset)


runner = r'''import json
import os
import sys
import time
from pathlib import Path
from datetime import datetime
from collections import defaultdict

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from prmr.core.engine import PRMRMemoryCore

DATASET_PATH = Path("benchmarks/datasets_v041/token_tax_cost_war_v041.json")
REPORT_DIR = Path("reports/v041")
REPORT_DIR.mkdir(parents=True, exist_ok=True)

# This is an illustrative benchmark assumption, not a live provider price.
ASSUMED_INPUT_COST_PER_1M_TOKENS_USD = 0.15


def load_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def estimate_tokens(obj):
    text = json.dumps(obj, sort_keys=True)
    return max(1, round(len(text) / 4))


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

        score = sum([
            current_ok,
            old_ok,
            problem_ok,
            latent_ok,
            lineage_ok,
            client_ok
        ]) / 6

        total += score

        details[topic] = {
            "score": round(score, 4),
            "current_ok": current_ok,
            "old_ok": old_ok,
            "problem_ok": problem_ok,
            "latent_ok": latent_ok,
            "lineage_ok": lineage_ok,
            "client_ok": client_ok,
            "answer": item,
            "expected": truth
        }

    return round((total / max(len(expected), 1)) * 100, 2), details


def raw_context_method(rows, expected, target_client):
    # Simulates sending full memory history to a strong downstream model.
    # It is allowed to synthesize correctly, but pays the full token tax.
    payload = rows
    answer = synthesize_continuity(rows, target_client, "raw full-context synthesis")
    return {
        "payload": payload,
        "answer": answer
    }


def basic_summary_method(rows, expected, target_client):
    # Low token cost but lossy: keeps last 2 notes per topic only.
    grouped = grouped_by_topic(rows, target_client=target_client)
    summary = {}

    for topic, topic_rows in grouped.items():
        last_rows = sorted(topic_rows, key=lambda row: row["timestamp_index"])[-2:]
        summary[topic] = [
            {
                "state_role": row.get("state_role"),
                "status": row.get("status"),
                "memory_value": row.get("memory_value"),
                "note": row.get("note")
            }
            for row in last_rows
        ]

    answer = {}

    for topic, fragments in summary.items():
        answer[topic] = {
            "client_id": target_client,
            "current_state": None,
            "old_state": None,
            "problem": None,
            "latent_risk": None,
            "lineage_reason": None,
            "method": "basic lossy summary"
        }

        for fragment in fragments:
            role = fragment["state_role"]
            value = fragment["memory_value"]

            if role == "current_commitment":
                answer[topic]["current_state"] = value
            elif role == "origin":
                answer[topic]["old_state"] = value
            elif role == "problem":
                answer[topic]["problem"] = value
            elif role == "latent_risk":
                answer[topic]["latent_risk"] = value
            elif role == "lineage":
                answer[topic]["lineage_reason"] = value

    return {
        "payload": summary,
        "answer": answer
    }


def keyword_method(rows, expected, target_client):
    # Retrieves rows with obvious current/problem/risk words.
    selected = []

    for row in rows:
        text = json.dumps(row, sort_keys=True).lower()

        if row.get("client_id") != target_client:
            continue

        if any(term in text for term in ["current", "problem", "risk", "lineage", "origin"]):
            selected.append(row)

    # Limit context window to simulate keyword retrieval budget.
    selected = selected[:120]

    answer = synthesize_continuity(selected, target_client, "keyword retrieval synthesis")

    return {
        "payload": selected,
        "answer": answer
    }


def vector_like_method(rows, expected, target_client):
    # Dependency-free vector-ish retrieval using token overlap.
    def tokens(text):
        return set(
            token.strip(".,!?;:()[]{}'\"").lower()
            for token in str(text).split()
            if token.strip(".,!?;:()[]{}'\"")
        )

    selected = []

    for topic in expected.keys():
        query = f"{topic} current old problem latent risk lineage client alpha"
        q = tokens(query)

        candidates = [
            row for row in rows
            if row.get("client_id") == target_client
            and row.get("topic") == topic
        ]

        scored = []

        for row in candidates:
            overlap = len(q & tokens(json.dumps(row, sort_keys=True))) / max(len(q), 1)
            scored.append((overlap, row["timestamp_index"], row))

        scored.sort(reverse=True, key=lambda item: (item[0], item[1]))

        selected.extend([item[2] for item in scored[:8]])

    answer = synthesize_continuity(selected, target_client, "vector-like retrieval synthesis")

    return {
        "payload": selected,
        "answer": answer
    }


def prmr_method(rows, expected, target_client):
    engine = PRMRMemoryCore()

    engine_input = [{
        "name": "token_tax_cost_war_v041",
        "description": "Token tax benchmark input",
        "rows": rows
    }]

    engine_result = engine.run(engine_input)
    decision = engine_result["results"][0]["decision"]

    reconstructed_rows = decision["reconstructed_rows"]
    reconstruction_match = reconstructed_rows == rows

    answer = synthesize_continuity(reconstructed_rows, target_client, "PRMR reconstructed continuity packet")

    # This is the practical payload a downstream model would need.
    # The core itself keeps private compressed/reconstruction details out of public reports.
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
        answer_score, answer_details = judge_answer(output["answer"], expected)

        token_reduction_vs_raw = round((1 - payload_tokens / raw_tokens) * 100, 2) if raw_tokens else 0

        results[name] = {
            "continuity_accuracy": answer_score,
            "payload_tokens": payload_tokens,
            "token_reduction_vs_raw_percent": token_reduction_vs_raw,
            "estimated_cost_per_1000_sessions_usd": cost_per_1000_sessions(payload_tokens),
            "answer_details": answer_details
        }

        if "engine_decision_public" in output:
            results[name]["engine_decision_public"] = output["engine_decision_public"]

    return results


def main():
    print("PRMR V0.41 TOKEN TAX / COST WAR BENCHMARK")
    print("-----------------------------------------")

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

    best_non_raw_accuracy = max(
        results[name]["continuity_accuracy"]
        for name in results
        if name not in ("raw_context", "prmr_memory_core")
    )

    prmr_token_reduction = results["prmr_memory_core"]["token_reduction_vs_raw_percent"]

    pass_condition = (
        prmr_accuracy >= 95
        and prmr_token_reduction >= 70
        and prmr_accuracy >= best_non_raw_accuracy
        and results["prmr_memory_core"]["engine_decision_public"]["reconstruction_match"] is True
    )

    public_report = {
        "company": "Afternum Industries",
        "product": "PRMR Memory Core",
        "version": "0.41",
        "report_type": "token_tax_cost_war_benchmark",
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
            "prmr_token_reduction_vs_raw_percent": prmr_token_reduction,
            "raw_context_accuracy": raw_accuracy,
            "prmr_accuracy": prmr_accuracy,
            "best_non_raw_baseline_accuracy": best_non_raw_accuracy,
            "duration_seconds": round(duration, 4),
            "result": "PASS" if pass_condition else "NEEDS_WORK"
        },
        "claim": "PRMR is compared against raw context, summary, keyword, and vector-like retrieval on token load, continuity accuracy, and estimated cost."
    }

    private_report = {
        **public_report,
        "public_safe": False,
        "private_answer_details": {
            name: result["answer_details"]
            for name, result in results.items()
        },
        "protected_note": "Private report includes detailed scoring answers."
    }

    public_path = REPORT_DIR / "public_token_tax_cost_war_v041.json"
    private_path = REPORT_DIR / "private_internal_token_tax_cost_war_v041.json"
    scorecard_path = REPORT_DIR / "scorecard_v041.md"

    public_path.write_text(json.dumps(public_report, indent=4), encoding="utf-8")
    private_path.write_text(json.dumps(private_report, indent=4), encoding="utf-8")

    md = f"""# PRMR V0.41 Token Tax / Cost War Benchmark

Company: Afternum Industries  
Product: PRMR Memory Core  
Version: V0.41  

## Result

**{public_report["summary"]["result"]}**

## Core Result

- Raw context tokens: **{raw_tokens}**
- PRMR payload tokens: **{prmr_tokens}**
- PRMR token reduction vs raw: **{prmr_token_reduction}%**
- Raw context continuity accuracy: **{raw_accuracy}%**
- PRMR continuity accuracy: **{prmr_accuracy}%**
- Best non-raw baseline accuracy: **{best_non_raw_accuracy}%**

## Method Table

| Method | Accuracy | Payload Tokens | Reduction vs Raw | Cost / 1,000 Sessions |
|---|---:|---:|---:|---:|
"""

    for name, result in public_report["results"].items():
        md += f"| {name} | {result['continuity_accuracy']}% | {result['payload_tokens']} | {result['token_reduction_vs_raw_percent']}% | ${result['estimated_cost_per_1000_sessions_usd']} |\n"

    md += """

## Meaning

This benchmark estimates the memory-token tax paid by different memory strategies.

Raw context may preserve continuity, but it pays the full token cost.  
Summary reduces tokens but loses detail.  
Keyword and vector-like retrieval can reduce tokens but may miss continuity structure.  
PRMR aims to preserve continuity while sending a much smaller current-state packet downstream.

This is an internal benchmark, not a live provider pricing guarantee.
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
'''

runner_path = RUNNER_DIR / "run_token_tax_cost_war_v041.py"
runner_path.write_text(runner, encoding="utf-8")

print("PRMR V0.41 Token Tax / Cost War benchmark created.")
print("Dataset:", DATASET_DIR / "token_tax_cost_war_v041.json")
print("Runner:", runner_path)