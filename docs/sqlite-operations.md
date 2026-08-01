# SQLite Operations

SQLite mode is for private local, development, deterministic single-node, and bounded one-worker use.

```powershell
prmr-core config init --mode sqlite_local --output prmr.toml
prmr-core --config prmr.toml engine init
prmr-core --config prmr.toml worker run-once
prmr-core --config prmr.toml engine ready
```

More than one worker is refused. Use `backup create --backend sqlite --destination PATH` for the SQLite backup API; it uses the SQLite backup operation, verifies integrity, hashes the artifact, and writes a manifest.
