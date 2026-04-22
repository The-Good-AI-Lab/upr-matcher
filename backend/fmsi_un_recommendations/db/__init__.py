from __future__ import annotations

from pathlib import Path
from typing import Optional

from ..settings import Settings
from .base import DatabaseAdapter
from .local import LocalDatabase
from .postgres import PostgresDatabase

_DB_INSTANCE: DatabaseAdapter | None = None


def get_database(settings: Settings | None = None) -> DatabaseAdapter:
    global _DB_INSTANCE
    if _DB_INSTANCE is not None:
        return _DB_INSTANCE

    config = settings or Settings()
    if config.db_backend == "postgres":
        if not config.database_url:
            raise ValueError("DATABASE_URL is required when db_backend=postgres")
        _DB_INSTANCE = PostgresDatabase(config.database_url)
    elif config.db_backend == "local":
        local_path = Path(config.local_db_path) if config.local_db_path else None
        _DB_INSTANCE = LocalDatabase(db_path=local_path)
    else:
        raise ValueError(f"Unsupported db_backend '{config.db_backend}'. Use 'local' or 'postgres'.")
    return _DB_INSTANCE
