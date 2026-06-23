def evaluate(dataset, keywords=None):
    keywords = keywords or []
    text = str(dataset).lower()
    hits = sum(1 for keyword in keywords if keyword.lower() in text)
    score = hits / max(len(keywords), 1)
    return {
        "method": "keyword_search",
        "keyword_hit_score": score,
        "storage_bytes": len(text.encode("utf-8")),
        "accuracy_estimate": score,
        "continuity_estimate": min(score, 0.65),
        "noise_resistance_estimate": 0.55
    }
