"""Authoritative PRMR Memory Core release identity constants."""

from __future__ import annotations

__version__ = "1.0.0rc1"
ENGINE_NAME = "PRMR Memory Core"
HUMAN_VERSION = "PRMR Memory Core v1.0 RC1"
RELEASE_CHANNEL = "private_release_candidate"

RELEASE_SCHEMA_REVISION = "prmr_release_v1"
RELEASE_MANIFEST_REVISION = "prmr_release_manifest_v1"
RELEASE_CONFIGURATION_REVISION = "prmr_configuration_v1"
RELEASE_CLI_REVISION = "prmr_cli_v1"
RELEASE_HEALTH_REVISION = "prmr_health_v1"
RELEASE_READINESS_REVISION = "prmr_readiness_v1"
RELEASE_SELF_TEST_REVISION = "prmr_self_test_v1"
RELEASE_DIAGNOSTICS_REVISION = "prmr_diagnostics_v1"
RELEASE_BACKUP_REVISION = "prmr_backup_procedure_v1"
RELEASE_COMPATIBILITY_REVISION = "prmr_compatibility_v1"
RELEASE_RUNBOOK_REVISION = "prmr_operational_runbook_v1"

SUPPORTED_PACKET_VERSIONS = ("continuity_packet_v1", "epistemic_continuity_v2")
SUPPORTED_DATABASE_BACKENDS = ("sqlite", "postgres")
SUPPORTED_PYTHON = ("3.11", "3.12")

__all__ = [
    "__version__",
    "ENGINE_NAME",
    "HUMAN_VERSION",
    "RELEASE_CHANNEL",
    "SUPPORTED_DATABASE_BACKENDS",
    "SUPPORTED_PACKET_VERSIONS",
    "SUPPORTED_PYTHON",
]
