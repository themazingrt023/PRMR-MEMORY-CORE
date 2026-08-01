# PostgreSQL Operations

PostgreSQL single-node mode supports validated concurrent repositories and leased workers. Set `PRMR_DATABASE_URL` in the process or an explicitly supplied environment file.

```powershell
prmr-core config init --mode postgres_single_node --output prmr-postgres.toml
prmr-core --config prmr-postgres.toml config validate
prmr-core --config prmr-postgres.toml db migrate
prmr-core --config prmr-postgres.toml engine init
prmr-core --config prmr-postgres.toml worker run --workers 2 --until-idle
```

The destructive test variable and guarded test URL are only for isolated release tests. They are not ordinary runtime configuration. RC1 does not claim failover, multi-region durability, or zero downtime.
