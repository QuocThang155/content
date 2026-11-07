"""Transactional, single-project SQLite persistence with legacy JSON v2 compatibility."""
from __future__ import annotations
import json
import shutil
import sqlite3
from datetime import datetime, timezone
from contextlib import contextmanager, closing
from pathlib import Path
from typing import Iterator
from . import core


LEGACY_DATABASE_PATH = Path.home() / '.story42_web' / 'story42.sqlite3'
DEFAULT_DATABASE_PATH = Path.home() / '.thangmia' / 'thangmia.sqlite3'


def migrate_legacy_database(path: Path) -> None:
    """Copy the legacy web database without overwriting an existing target."""
    target = path.expanduser()
    legacy = LEGACY_DATABASE_PATH if target == DEFAULT_DATABASE_PATH else target.with_name('story42.sqlite3')
    if target.exists() or not legacy.exists():
        return

    target.parent.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    backup = legacy.with_name(
        f'{legacy.name}.migration-backup-{timestamp}'
    )
    suffix = 1
    while backup.exists():
        backup = legacy.with_name(
            f'{legacy.name}.migration-backup-{timestamp}-{suffix}'
        )
        suffix += 1
    created_target = False
    try:
        shutil.copy2(legacy, backup)
        with legacy.open('rb') as source, target.open('xb') as destination:
            created_target = True
            shutil.copyfileobj(source, destination)
    except Exception as exc:
        if created_target and target.exists():
            target.unlink()
        raise RuntimeError(
            f'Không thể chuyển database cũ sang {target}. '
            f'Dữ liệu cũ vẫn được giữ nguyên; bản sao lưu: {backup}'
        ) from exc


class Store:
    def __init__(self, path: str | Path):
        self.path = Path(path).expanduser()
        migrate_legacy_database(self.path)
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
