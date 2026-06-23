from pathlib import Path

path = Path("benchmarks/runners/run_trust_suite_v036.py")
text = path.read_text(encoding="utf-8")

old = '''def run_prmr(datasets):
    engine = PRMRMemoryCore()
    return normalize_prmr_result(engine.run(datasets))
'''

new = '''def run_prmr(datasets):
    engine = PRMRMemoryCore()

    # Adapter:
    # V0.36 benchmark datasets use dataset_name/events.
    # Existing PRMR engine expects name/data.
    engine_datasets = []

    for dataset in datasets:
        engine_datasets.append({
            "name": dataset.get("name") or dataset.get("dataset_name"),
            "dataset_name": dataset.get("dataset_name") or dataset.get("name"),
            "type": dataset.get("type"),
            "data": dataset.get("data") or dataset.get("events") or dataset,
            "events": dataset.get("events") or dataset.get("data") or []
        })

    return normalize_prmr_result(engine.run(engine_datasets))
'''

if old not in text:
    print("Could not find original run_prmr block. It may already be patched.")
else:
    text = text.replace(old, new)
    path.write_text(text, encoding="utf-8")
    print("V0.36 PRMR dataset adapter patched ✅")