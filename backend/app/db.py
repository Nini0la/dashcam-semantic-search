import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

from .config import get_settings


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_db_path() -> Path:
    settings = get_settings()
    return settings.db_path


@contextmanager
def get_connection() -> Iterator[sqlite3.Connection]:
    db_path = get_db_path()
    if db_path.parent != Path("."):
        db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with get_connection() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS videos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                blob_name TEXT NOT NULL UNIQUE,
                blob_url TEXT NOT NULL,
                sas_url TEXT,
                video_indexer_id TEXT,
                duration REAL,
                status TEXT NOT NULL DEFAULT 'discovered',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                raw_insights_json TEXT
            );

            CREATE TABLE IF NOT EXISTS frames (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                video_id INTEGER NOT NULL REFERENCES videos(id) ON DELETE CASCADE,
                timestamp_seconds REAL NOT NULL,
                image_path TEXT,
                labels_json TEXT NOT NULL DEFAULT '[]',
                objects_json TEXT NOT NULL DEFAULT '[]',
                embedding_json TEXT,
                metadata_text TEXT NOT NULL DEFAULT '',
                UNIQUE(video_id, timestamp_seconds)
            );

            CREATE TABLE IF NOT EXISTS labels (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                frame_id INTEGER NOT NULL REFERENCES frames(id) ON DELETE CASCADE,
                label_type TEXT NOT NULL,
                value TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_videos_status ON videos(status);
            CREATE INDEX IF NOT EXISTS idx_frames_video_id ON frames(video_id);
            CREATE INDEX IF NOT EXISTS idx_labels_frame_id ON labels(frame_id);
            """
        )
