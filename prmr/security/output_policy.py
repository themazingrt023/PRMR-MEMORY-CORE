MINIMUM_SAVINGS_PERCENT = 10.0


PUBLIC_SAFE_POSITIONING = (
    "PRMR Memory Core is continuity infrastructure for intelligent systems. "
    "It helps compress, reconstruct, and preserve useful memory/context patterns over time."
)


PRIVATE_PROTECTION_WARNING = (
    "Private report. Do not publish. Contains internal decision data, compressed packages, "
    "rule data, reconstruction details, and protected implementation information."
)


def is_public_safe_report(report_type):
    return report_type in [
        "public_safe_engine_demo",
        "public_safe_unified_demo"
    ]