# PRMR Memory Core v1.0 RC1

PRMR Memory Core is private engineering software for deterministic, provenance-backed memory continuity. Core Sprints 1-13 provide source ingestion, candidate extraction, controlled admission, bitemporal evolution, temporal dynamics, entities and relationships, deterministic query, consolidation, bounded interpretation, canonical signals, governance, durable jobs, quality validation, and Epistemic Continuity Packet V2.

This package is a private release candidate. It is not public SaaS, production certification, scientific validation, legal certification, or external security certification.

## Install

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -U pip
.\.venv\Scripts\python -m pip install .
.\.venv\Scripts\prmr-core version
```

For PostgreSQL, install `.[postgres]`. Python 3.11 is validated in the current Windows environment. Python 3.12 and Linux remain secondary validation targets until CI evidence exists.

## SQLite Quickstart

```powershell
prmr-core config init --mode sqlite_local --output prmr.toml
prmr-core --config prmr.toml config validate
prmr-core --config prmr.toml engine init
prmr-core --config prmr.toml engine ready
prmr-core --config prmr.toml engine self-test
prmr-core --config prmr.toml integrity sweep --mode release-smoke
prmr-core --config prmr.toml worker run-once
```

See [installation](docs/installation.md), [configuration](docs/configuration.md), and the [operations runbook](docs/operations-runbook.md).
