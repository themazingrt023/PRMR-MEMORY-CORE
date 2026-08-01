# KM-1 Maintenance Policy

PRMR Memory Core KM-1 `v1.0.0rc1` is feature-frozen.

## Allowed Maintenance

- Critical correctness fixes.
- Security fixes.
- Migration fixes implemented through a new ordered migration.
- Documentation corrections.
- Compatibility fixes.
- Performance fixes that preserve exact deterministic behaviour.

Every maintenance change must preserve client, vault and namespace isolation,
provenance, bitemporal history, governance controls, deterministic identities,
V1/V2 packet replay, and the recorded security boundary. A changed contract or
artifact requires an explicit version change and refreshed release evidence.

## Prohibited Changes

- New memory capabilities.
- New packet semantics.
- Experimental KM2 behaviour.
- Admissionless memory.
- Breaking contract changes.
- Rewriting historical migrations.
- Changing deterministic IDs or hashes without a new version.
- Continuum-specific or other client-specific logic inside KM-1.

Existing migration files are immutable after the lock. Future schema changes
must be delivered as new migrations; they must not rewrite release history.

KM2 is a separate future architecture and must not be implemented inside the
KM-1 repository without an explicit separate project decision.

This policy does not confer production readiness, scientific validation, legal
or compliance approval, or external security certification.

The authoritative frozen source is commit
`4f756fe9c50f9700a1dee612c4113901e511f6b5`, tagged
`km1-v1.0.0rc1`. Maintenance releases must use a new version and refreshed
release evidence; they must not move or rewrite this tag.
