from pathlib import Path

path = Path("benchmarks/runners/run_trust_suite_v036.py")
text = path.read_text(encoding="utf-8")

old = '''            "data": dataset_events,
            "events": dataset_events,
            "items": dataset_events
        })'''

new = '''            "data": dataset_events,
            "events": dataset_events,
            "items": dataset_events,
            "rows": dataset_events
        })'''

if old not in text:
    print("Could not find the data/events/items block. It may already be patched or formatted differently.")
else:
    text = text.replace(old, new)
    path.write_text(text, encoding="utf-8")
    print("V0.36 dataset rows adapter patched ✅")