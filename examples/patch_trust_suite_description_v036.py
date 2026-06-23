from pathlib import Path

path = Path("benchmarks/runners/run_trust_suite_v036.py")
text = path.read_text(encoding="utf-8")

old = '''        engine_datasets.append({
            "name": dataset.get("name") or dataset.get("dataset_name"),
            "dataset_name": dataset.get("dataset_name") or dataset.get("name"),
            "type": dataset.get("type"),
            "data": dataset.get("data") or dataset.get("events") or dataset,
            "events": dataset.get("events") or dataset.get("data") or []
        })'''

new = '''        dataset_name = dataset.get("name") or dataset.get("dataset_name")
        dataset_type = dataset.get("type", "benchmark_dataset")
        dataset_events = dataset.get("events") or dataset.get("data") or []

        engine_datasets.append({
            "name": dataset_name,
            "dataset_name": dataset_name,
            "description": dataset.get("description") or f"V0.36 trust benchmark dataset: {dataset_name} ({dataset_type})",
            "type": dataset_type,
            "data": dataset_events,
            "events": dataset_events,
            "items": dataset_events
        })'''

if old not in text:
    print("Could not find the adapter block. It may already be patched or formatted differently.")
else:
    text = text.replace(old, new)
    path.write_text(text, encoding="utf-8")
    print("V0.36 dataset description adapter patched ✅")