# Installation

RC1 supports Python 3.11 and targets Python 3.12 pending independent CI confirmation. Windows PowerShell is the primary validated environment.

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install .
```

PostgreSQL mode requires:

```powershell
.\.venv\Scripts\python -m pip install ".[postgres]"
```

Verify with `prmr-core version`, then follow the SQLite or PostgreSQL operations guide. A built wheel can be installed from `dist/` without the source tree.
