"""Transactional, single-project SQLite persistence with legacy JSON v2 compatibility."""
from __future__ import annotations
import json
import sqlite3
from contextlib import contextmanager, closing
from pathlib import Path
from typing import Iterator
from . import core


class Store:
    def __init__(self, path: str | Path):
        self.path = Path(path).expanduser()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as conn:
            conn.execute('CREATE TABLE IF NOT EXISTS projects (id INTEGER PRIMARY KEY CHECK(id=1), payload TEXT NOT NULL)')
            if conn.execute('SELECT 1 FROM projects WHERE id=1').fetchone() is None:
                conn.execute('INSERT INTO projects (id, payload) VALUES (1, ?)', (json.dumps(core.default_db(), ensure_ascii=False),))
            conn.commit()

    def _connect(self):
        conn = sqlite3.connect(self.path, timeout=15, isolation_level=None)
        conn.execute('PRAGMA busy_timeout=15000')
        return conn

    def read(self):
        with closing(self._connect()) as conn:
            row = conn.execute('SELECT payload FROM projects WHERE id=1').fetchone()
            return core.normalized_db(json.loads(row[0]))

    @contextmanager
    def edit(self) -> Iterator[dict]:
        """Serialize all read-modify-write operations, including concurrent requests."""
        with closing(self._connect()) as conn:
            conn.execute('BEGIN IMMEDIATE')
            try:
                data = json.loads(conn.execute('SELECT payload FROM projects WHERE id=1').fetchone()[0])
                yield data
                conn.execute('UPDATE projects SET payload=? WHERE id=1', (json.dumps(data, ensure_ascii=False),))
                conn.commit()
            except BaseException:
                conn.rollback()
                raise
