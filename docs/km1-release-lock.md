# KM-1 Release Lock

PRMR Memory Core v1.0 RC1 (`1.0.0rc1`) is feature-frozen.

The authoritative release source is commit
`4f756fe9c50f9700a1dee612c4113901e511f6b5`, identified by annotated tag
`km1-v1.0.0rc1`. The verified wheel and source distribution were built from
that commit. The documentation-only lock commit is intentionally separate and
is not self-referenced.

The permanent human-readable attestation is `KM1_RELEASE_LOCK.md`. The safe
machine-readable record is
`reports/core_release_candidate/km1_release_lock.json`, and the reviewed source
selection is recorded in
`reports/core_release_candidate/km1_release_file_manifest.json`.

The lock preserves migration, event, source, candidate, admission, governance,
query, Continuity Packet V1, Epistemic Continuity Packet V2, CLI,
configuration-precedence, and release-manifest contracts under the recorded
hashes.

No credential, database URL, memory source content, or private runtime evidence
belongs in a lock record or release commit. KM2 is a separate future
architecture and must not be implemented inside KM-1 without an explicit
separate project decision.
