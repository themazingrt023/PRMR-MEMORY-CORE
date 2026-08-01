"""Retention helpers for the source ledger."""

from __future__ import annotations

from datetime import datetime, timezone

from .source_models import RetentionPolicy, SourceLedgerError


def parse_timestamp(value: str | None, *, field_name: str) -> datetime | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise SourceLedgerError(
            "SOURCE_PAYLOAD_INVALID",
            f"{field_name} must be an ISO-8601 timestamp.",
        ) from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def normalize_timestamp(value: str | None, *, field_name: str) -> str | None:
    parsed = parse_timestamp(value, field_name=field_name)
    return parsed.isoformat().replace("+00:00", "Z") if parsed else None


def validate_retention(policy: RetentionPolicy | str, expires_at: str | None) -> tuple[str, str | None]:
    try:
        normalized_policy = RetentionPolicy(str(getattr(policy, "value", policy))).value
    except ValueError as exc:
        raise SourceLedgerError(
            "SOURCE_PAYLOAD_INVALID",
            "retention_policy must be standard or ephemeral.",
        ) from exc
    normalized_expiry = normalize_timestamp(expires_at, field_name="expires_at")
    if normalized_policy == RetentionPolicy.EPHEMERAL.value and not normalized_expiry:
        raise SourceLedgerError(
            "SOURCE_PAYLOAD_INVALID",
            "ephemeral sources require expires_at.",
        )
    return normalized_policy, normalized_expiry


def is_expired(expires_at: str | None, now: datetime) -> bool:
    expiry = parse_timestamp(expires_at, field_name="expires_at")
    return bool(expiry and expiry <= now.astimezone(timezone.utc))


__all__ = ["is_expired", "normalize_timestamp", "parse_timestamp", "validate_retention"]
