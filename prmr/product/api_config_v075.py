"""V0.75 API wrapper configuration."""

from __future__ import annotations

import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class PRMRAPIConfig:
    api_mode: str
    storage_path: Path
    synthetic_only: bool
    public_reports_dir: Path
    private_reports_dir: Path
    allowed_alpha_mode: bool
    default_max_events_per_day: int
    default_max_packets_per_day: int
    default_max_reports_per_day: int
    allowed_origins: list[str]

    def public_safe(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["storage_path"] = str(self.storage_path)
        payload["public_reports_dir"] = str(self.public_reports_dir)
        payload["private_reports_dir"] = str(self.private_reports_dir)
        return payload


def env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


def load_api_config() -> PRMRAPIConfig:
    api_mode = os.getenv("PRMR_API_MODE", "local_alpha")
    storage_path = Path(os.getenv("PRMR_STORAGE_PATH", str(ROOT / "reports" / "v075" / "prmr_api_wrapper_v075.sqlite")))
    public_reports_dir = Path(os.getenv("PRMR_PUBLIC_REPORTS_DIR", str(ROOT / "reports" / "v075")))
    private_reports_dir = Path(os.getenv("PRMR_PRIVATE_REPORTS_DIR", str(ROOT / "reports" / "v075")))
    allowed_origins = [
        origin.strip()
        for origin in os.getenv("PRMR_ALLOWED_ORIGINS", "http://localhost:3000").split(",")
        if origin.strip()
    ]
    return PRMRAPIConfig(
        api_mode=api_mode,
        storage_path=storage_path,
        synthetic_only=env_bool("PRMR_SYNTHETIC_ONLY", True),
        public_reports_dir=public_reports_dir,
        private_reports_dir=private_reports_dir,
        allowed_alpha_mode=api_mode == "local_alpha",
        default_max_events_per_day=env_int("PRMR_DEFAULT_MAX_EVENTS_PER_DAY", 3),
        default_max_packets_per_day=env_int("PRMR_DEFAULT_MAX_PACKETS_PER_DAY", 4),
        default_max_reports_per_day=env_int("PRMR_DEFAULT_MAX_REPORTS_PER_DAY", 4),
        allowed_origins=allowed_origins,
    )
