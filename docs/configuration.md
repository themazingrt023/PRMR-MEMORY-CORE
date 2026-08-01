# Configuration

Configuration precedence is CLI override, process environment, explicitly supplied `--env-file`, explicitly supplied TOML, then safe defaults. No `.env` file is loaded silently.

Use `prmr-core config init --mode sqlite_local --output prmr.toml`, then `prmr-core --config prmr.toml config validate`. PostgreSQL TOML refers to `PRMR_DATABASE_URL`; credentials never belong in the file. `config show --redacted` never prints a database URL, password, token, or API key.

Important environment variables: `PRMR_MODE`, `PRMR_DATABASE_BACKEND`, `PRMR_SQLITE_PATH`, `PRMR_DATABASE_URL`, `PRMR_LOG_FORMAT`, `PRMR_LOG_LEVEL`, `PRMR_EXPORT_PATH`, `PRMR_DIAGNOSTICS_PATH`, and `PRMR_PACKET_DEFAULT`.
