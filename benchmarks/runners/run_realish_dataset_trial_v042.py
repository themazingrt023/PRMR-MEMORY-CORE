import json
import os
import sys
import time
from pathlib import Path
from datetime import datetime
from collections import defaultdict

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from prmr.core.engine import PRMRMemoryCore

DATASET_PATH = Path("benchmarks/datasets_v042/realish_dataset_trial_v042.json")
REPORT_DIR = Path("reports/v042")
REPORT_DIR.mkdir(parents=True, exist_ok=True)


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


def newest_trusted_signal(rows, signal_type):
    candidates = [
        row for row in rows
        if row.get("signal_type") == signal_type
        and row.get("trust_level") == "trusted"
        and row.get("status") in ("active", "historical")
    ]

    return newest(candidates)


def synthesize_realish_continuity(rows, target_client, method):
    grouped = grouped_by_topic(rows, target_client=target_client)
    answer = {}

    for topic, topic_rows in grouped.items():
        old = newest_trusted_signal(topic_rows, "origin")
        current = newest_trusted_signal(topic_rows, "current_state")
        reason = newest_trusted_signal(topic_rows, "decision_reason")
        risk = newest_trusted_signal(topic_rows, "latent_risk")
        next_action = newest_trusted_signal(topic_rows, "next_action")

        answer[topic] = {
            "client_id": target_client,
            "old_state": old.get("memory_value") if old else None,
            "current_state": current.get("memory_value") if current else None,
            "decision_reason": reason.get("memory_value") if reason else None,
            "latent_risk": risk.get("memory_value") if risk else None,
            "next_action": next_action.get("memory_value") if next_action else None,
            "method": method
        }

    return answer


def fragment_answer_from_rows(rows, target_client, method):
    grouped = grouped_by_topic(rows, target_client=target_client)
    answer = {}

    for topic, topic_rows in grouped.items():
        answer[topic] = {
            "client_id": target_client,
            "old_state": None,
            "current_state": None,
            "decision_reason": None,
            "latent_risk": None,
            "next_action": None,
            "method": method
        }

        for row in sorted(topic_rows, key=lambda item: item["timestamp_index"]):
            signal = row.get("signal_type")
            value = row.get("memory_value")

            if signal == "origin":
                answer[topic]["old_state"] = value
            elif signal in ("current_state", "fake_current", "near_miss", "stale_update"):
                answer[topic]["current_state"] = value
            elif signal == "decision_reason":
                answer[topic]["decision_reason"] = value
            elif signal == "latent_risk":
                answer[topic]["latent_risk"] = value
            elif signal == "next_action":
                answer[topic]["next_action"] = value

    return answer


def judge_answer(answer, expected):
    total = 0
    details = {}

    for topic, truth in expected.items():
        item = answer.get(topic, {})

        old_ok = item.get("old_state") == truth["old_state"]
        current_ok = item.get("current_state") == truth["current_state"]
        reason_ok = item.get("decision_reason") == truth["decision_reason"]
        risk_ok = item.get("latent_risk") == truth["latent_risk"]
        next_ok = item.get("next_action") == truth["next_action"]
        client_ok = item.get("client_id") == truth["client_id"]

        wrong_values = truth.get("must_not_return", [])
        item_text = json.dumps(item)
        avoided_wrong = all(value not in item_text for value in wrong_values)

        score = sum([
            old_ok,
            current_ok,
            reason_ok,
            risk_ok,
            next_ok,
            client_ok,
            avoided_wrong
        ]) / 7

        total += score

        details[topic] = {
            "score": round(score, 4),
            "old_ok": old_ok,
            "current_ok": current_ok,
            "reason_ok": reason_ok,
            "risk_ok": risk_ok,
            "next_ok": next_ok,
            "client_ok": client_ok,
            "avoided_wrong": avoided_wrong,
            "answer": item,
            "expected": truth
        }

    return round((total / max(len(expected), 1)) * 100, 2), details


def raw_context_method(rows, expected, target_client):
    answer = synthesize_realish_continuity(rows, target_client, "raw full-context real-ish synthesis")
    return {"payload": rows, "answer": answer}


def basic_summary_method(rows, expected, target_client):
    grouped = grouped_by_topic(rows, target_client=target_client)
    selected = []

    for topic, topic_rows in grouped.items():
        selected.extend(sorted(topic_rows, key=lambda row: row["timestamp_index"])[-3:])

    answer = fragment_answer_from_rows(selected, target_client, "basic latest-note summary")
    return {"payload": selected, "answer": answer}


def keyword_method(rows, expected, target_client):
    query_terms = ["current", "decision", "reason", "risk", "next", "official", "urgent", "update"]
    selected = []

    for row in rows:
        if row.get("client_id") != target_client:
            continue

        text = json.dumps(row, sort_keys=True).lower()
        score = sum(1 for term in query_terms if term in text)

        if score > 0:
            selected.append((score, row["timestamp_index"], row))

    selected.sort(reverse=True, key=lambda item: (item[0], item[1]))
    payload = [item[2] for item in selected[:60]]

    answer = fragment_answer_from_rows(payload, target_client, "keyword messy-memory retrieval")
    return {"payload": payload, "answer": answer}


def tokenize(text):
    return set(
        token.strip(".,!?;:()[]{}'\"").lower()
        for token in str(text).split()
        if token.strip(".,!?;:()[]{}'\"")
    )


def vector_like_method(rows, expected, target_client):
    selected = []

    for topic in expected.keys():
        query = f"{topic} current decision reason risk next action old state"
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
        selected.extend([item[2] for item in scored[:5]])

    answer = fragment_answer_from_rows(selected, target_client, "vector-like messy-memory retrieval")
    return {"payload": selected, "answer": answer}


def prmr_method(rows, expected, target_client):
    engine = PRMRMemoryCore()

    engine_input = [{
        "name": "realish_dataset_trial_v042",
        "description": "Real-ish messy memory trial input",
        "rows": rows
    }]

    engine_result = engine.run(engine_input)
    decision = engine_result["results"][0]["decision"]

    reconstructed_rows = decision["reconstructed_rows"]
    reconstruction_match = reconstructed_rows == rows

    answer = synthesize_realish_continuity(reconstructed_rows, target_client, "PRMR reconstructed real-ish continuity packet")

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


def score_methods(method_outputs, expected):
    raw_tokens = estimate_tokens(method_outputs["raw_context"]["payload"])
    results = {}

    for name, output in method_outputs.items():
        payload_tokens = estimate_tokens(output["payload"])
        accuracy, details = judge_answer(output["answer"], expected)
        reduction = round((1 - payload_tokens / raw_tokens) * 100, 2) if raw_tokens else 0

        results[name] = {
            "useful_reconstruction_accuracy": accuracy,
            "payload_tokens": payload_tokens,
            "token_reduction_vs_raw_percent": reduction,
            "answer_details": details
        }

        if "engine_decision_public" in output:
            results[name]["engine_decision_public"] = output["engine_decision_public"]

    return results


def main():
    print("PRMR V0.42 REAL-ISH DATASET TRIAL")
    print("---------------------------------")

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

    prmr = results["prmr_memory_core"]
    raw = results["raw_context"]

    best_non_raw_baseline = max(
        results[name]["useful_reconstruction_accuracy"]
        for name in results
        if name not in ("raw_context", "prmr_memory_core")
    )

    pass_condition = (
        prmr["useful_reconstruction_accuracy"] >= 90
        and prmr["useful_reconstruction_accuracy"] >= raw["useful_reconstruction_accuracy"]
        and prmr["useful_reconstruction_accuracy"] > best_non_raw_baseline
        and prmr["engine_decision_public"]["reconstruction_match"] is True
    )

    public_report = {
        "company": "Afternum Industries",
        "product": "PRMR Memory Core",
        "version": "0.42",
        "report_type": "realish_dataset_trial",
        "public_safe": True,
        "timestamp": datetime.now().isoformat(),
        "dataset": dataset["dataset_name"],
        "row_count": len(rows),
        "results": {
            name: {
                key: value
                for key, value in result.items()
                if key != "answer_details"
            }
            for name, result in results.items()
        },
        "summary": {
            "raw_context_accuracy": raw["useful_reconstruction_accuracy"],
            "prmr_accuracy": prmr["useful_reconstruction_accuracy"],
            "best_non_raw_baseline_accuracy": best_non_raw_baseline,
            "raw_context_tokens": raw["payload_tokens"],
            "prmr_payload_tokens": prmr["payload_tokens"],
            "prmr_token_reduction_vs_raw_percent": prmr["token_reduction_vs_raw_percent"],
            "duration_seconds": round(duration, 4),
            "result": "PASS" if pass_condition else "NEEDS_WORK"
        },
        "claim": "PRMR is tested on messy real-ish memory made of project notes, dev logs, chat-style entries, fake docs, stale notes, near-misses, noise, and cross-client traps."
    }

    private_report = {
        **public_report,
        "public_safe": False,
        "private_answer_details": {
            name: result["answer_details"]
            for name, result in results.items()
        },
        "protected_note": "Private report includes detailed answer scoring and should not be published."
    }

    public_path = REPORT_DIR / "public_realish_dataset_trial_v042.json"
    private_path = REPORT_DIR / "private_internal_realish_dataset_trial_v042.json"
    scorecard_path = REPORT_DIR / "scorecard_v042.md"

    public_path.write_text(json.dumps(public_report, indent=4), encoding="utf-8")
    private_path.write_text(json.dumps(private_report, indent=4), encoding="utf-8")

    md = f"""# PRMR V0.42 Real-ish Dataset Trial

Company: Afternum Industries  
Product: PRMR Memory Core  
Version: V0.42  

## Result

**{public_report["summary"]["result"]}**

## Core Result

- Raw context useful reconstruction: **{raw["useful_reconstruction_accuracy"]}%**
- PRMR useful reconstruction: **{prmr["useful_reconstruction_accuracy"]}%**
- Best non-raw baseline: **{best_non_raw_baseline}%**
- Raw context tokens: **{raw["payload_tokens"]}**
- PRMR payload tokens: **{prmr["payload_tokens"]}**
- PRMR reduction vs raw: **{prmr["token_reduction_vs_raw_percent"]}%**

## Method Table

| Method | Useful Reconstruction | Payload Tokens | Reduction vs Raw |
|---|---:|---:|---:|
"""

    for name, result in public_report["results"].items():
        md += f"| {name} | {result['useful_reconstruction_accuracy']}% | {result['payload_tokens']} | {result['token_reduction_vs_raw_percent']}% |\n"

    md += """

## Meaning

V0.42 tests whether PRMR can preserve useful continuity in messier human-style memory, not just clean benchmark rows.

This remains an internal benchmark, not production certification.
"""

    scorecard_path.write_text(md, encoding="utf-8")

    print("Method results:")
    for name, result in public_report["results"].items():
        print("-", name)
        print("  useful_reconstruction_accuracy:", result["useful_reconstruction_accuracy"])
        print("  payload_tokens:", result["payload_tokens"])
        print("  token_reduction_vs_raw_percent:", result["token_reduction_vs_raw_percent"])

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
