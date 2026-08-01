# Release Process

1. Run `python -m build`.
2. Run compilation and diff checks.
3. Run SQLite RC validation, failure tests, benchmark smoke, and clean-wheel install.
4. Run guarded PostgreSQL release proof in the isolated database.
5. Run Core Sprint 1-13 regressions and secret hygiene.
6. Run `prmr-core release check` and the independent release audit.
7. Hash wheel, source distribution, documents, revisions, and evidence.

RC1 is `1.0.0rc1`. Stable command, configuration, health, and manifest changes require their revision identifiers to change.
