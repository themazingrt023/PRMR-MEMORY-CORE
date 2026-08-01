# PRMR Memory Core KM-1 Release Lock

## Locked Release Identity

- Release: **PRMR Memory Core v1.0 RC1**
- Package version: `1.0.0rc1`
- Release date: `2026-08-01`
- Lock status: **LOCKED**
- Authoritative source commit: `4f756fe9c50f9700a1dee612c4113901e511f6b5`
- Annotated source tag: `km1-v1.0.0rc1`
- Supported Python versions: `3.11`, `3.12`
- Supported databases: `sqlite`, `postgres`

The annotated tag identifies the source commit from which both release
artifacts were built. The later documentation-only lock commit is deliberately
not part of the source identity and is not embedded here.

## Deterministic Hashes

| Field | Locked value |
| --- | --- |
| Migration registry | `c24d05ff4e396563bf3e5f2e71fc93eee0a67aeb0567d0c32f0e691bd3af0ac9` |
| Core revision manifest | `361203a52618744507c0497aadaf6dcf9fda5e99a4d1a34f4077e8f53df65931` |
| Release manifest | `f3ca22c827dbedf018b050eedef87eb8fe3e4b72ef5c7fcbe98ab717cc445e65` |
| Wheel SHA-256 | `5b26d92bcc8ae8d1798ed396d7bb28dcabb8acdca6e3dc1a553b9a5fb7c2605e` |
| Source distribution SHA-256 | `a5f5f4a88861deb5244a2585013b0f5916967d0d54ae6c35be6a5ae0c5e33d69` |

Artifacts:

- `dist/prmr_memory_core-1.0.0rc1-py3-none-any.whl`
- `dist/prmr_memory_core-1.0.0rc1.tar.gz`

Packet revisions:

- Continuity Packet V1: `continuity_packet_v1`
- Epistemic Continuity Packet V2: `epistemic_continuity_v2`

## Release Evidence

### Sprint 11: PostgreSQL runtime

- Guarded matrix: `PASS_FULL_POSTGRES_MATRIX`, 74/74 checks.
- Independent audit: 84/84 checks.
- Twelve ordered migrations and 94 expected relations were verified.
- Migration replay, guard preservation, parity, transaction isolation,
  concurrency, durable jobs, recovery, tenant isolation, query plans, and the
  Core Sprint 1-10 PostgreSQL lifecycle executed.

### Sprint 12: memory quality

- Result: `PASS WITH DOCUMENTED LIMITATIONS`.
- Corpus: 270 cases and 1,100 assertions per backend.
- SQLite/PostgreSQL result parity: 270/270, with zero mismatches.
- Critical mutations detected: 18/18; independent audit: 39/39.
- This is deterministic engineering evidence, not scientific validation.

### Sprint 13: packet evidence

- V2 packet runner: 79/79 checks.
- Corpus: 120 cases and 608 assertions.
- SQLite and PostgreSQL packet results: PASS.
- Critical mutations: 12/12; exact acceleration equivalence and the bounded
  performance regression gate passed.
- A fresh-database replay of the historical Sprint 1-12 aggregate ledger is
  not a locked claim: legacy Sprints 1-3 use an older unqualified
  `DATABASE_URL` relation path. The modern guarded PostgreSQL matrix and the
  mandatory V1/V2 release proofs pass.

### Sprint 14: release evidence

- Release runner: 11/11 mandatory checks.
- SQLite release proof: PASS; PostgreSQL release proof: PASS.
- Independent release audit: 33/33 PASS.
- Failure tests: 12/12 PASS; performance smoke: PASS.
- Wheel install, source-distribution install, and installed-wheel PostgreSQL
  proof: PASS.
- Installed CLI `release check`: 15/15 PASS.
- Repeated source-distribution builds with the source commit epoch produced
  byte-identical archives.
- Secret hygiene: 31/31 PASS, zero tracked secret-pattern hits and zero public
  report secret hits.

## Frozen Contracts

The following KM-1 contracts are frozen at the source commit and hashes above:

- migration history
- event contract
- source contract
- candidate contract
- admission contract
- governance contract
- query contract
- Continuity Packet V1
- Epistemic Continuity Packet V2
- CLI command contract
- configuration precedence
- release manifest schema

Existing migrations are immutable. Every future schema change must use a new
ordered migration and a new compatible release identity.

## Maintenance Restrictions

KM-1 `v1.0.0rc1` is feature-frozen. Permitted work is limited to critical
correctness fixes, security fixes, new migration fixes, documentation
corrections, compatibility fixes, and behaviour-preserving performance fixes.

New memory capabilities, new packet semantics, admissionless memory, breaking
contract changes, rewritten historical migrations, silent deterministic-ID or
hash changes, client-specific logic, and KM2 experiments are prohibited.

KM2 is a separate future architecture and requires an explicit separate project
decision.

## Documented Limitations

- This is a private engineering release candidate, not production readiness,
  scientific validation, legal or compliance approval, or external security
  certification.
- SQLite is limited to bounded single-node operation.
- PostgreSQL logical backup was not executed because `pg_dump` tooling is not
  available in the release environment.
- Automatic failover, multi-region durability, and external security review are
  not included.
- The legacy aggregate regression path described in Sprint 13 is not claimed as
  a fresh-schema PostgreSQL pass.

## Reproduction

Build artifacts from the authoritative source commit with
`SOURCE_DATE_EPOCH` set to that commit's Unix timestamp, then run the release
runner, independent audit, clean-install proof, failure tests, installed CLI
release check, secret scan, compile check, and `git diff --check`.
