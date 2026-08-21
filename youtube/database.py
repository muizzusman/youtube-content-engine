import sqlite3
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DATABASE_PATH = DATA_DIR / "youtube.db"


def get_connection() -> sqlite3.Connection:
    DATA_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    connection = sqlite3.connect(
        DATABASE_PATH
    )

    connection.row_factory = sqlite3.Row

    return connection


def initialize_database(
    connection: sqlite3.Connection,
) -> None:

    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS videos (
            video_id TEXT PRIMARY KEY,

            channel_id TEXT NOT NULL,
            channel_name TEXT NOT NULL,
            subscriber_count INTEGER NOT NULL,

            title TEXT NOT NULL,
            published_at TEXT NOT NULL,

            duration_seconds INTEGER NOT NULL,
            format TEXT NOT NULL,

            thumbnail_url TEXT,
            video_url TEXT NOT NULL
        )
        """
    )

    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            video_id TEXT NOT NULL,
            checked_at TEXT NOT NULL,

            views INTEGER NOT NULL,
            likes INTEGER NOT NULL,
            comments INTEGER NOT NULL,

            FOREIGN KEY(video_id)
                REFERENCES videos(video_id)
        )
        """
    )

    connection.commit()


def save_video(
    connection: sqlite3.Connection,
    video: dict,
) -> None:

    connection.execute(
        """
        INSERT INTO videos (
            video_id,
            channel_id,
            channel_name,
            subscriber_count,
            title,
            published_at,
            duration_seconds,
            format,
            thumbnail_url,
            video_url
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)

        ON CONFLICT(video_id)
        DO UPDATE SET
            channel_name = excluded.channel_name,
            subscriber_count = excluded.subscriber_count,
            title = excluded.title,
            published_at = excluded.published_at,
            duration_seconds = excluded.duration_seconds,
            format = excluded.format,
            thumbnail_url = excluded.thumbnail_url,
            video_url = excluded.video_url
        """,
        (
            video["video_id"],
            video["channel_id"],
            video["channel_name"],
            video["subscriber_count"],
            video["title"],
            video["published_at"],
            video["duration_seconds"],
            video["format"],
            video["thumbnail_url"],
            video["video_url"],
        ),
    )


def save_snapshot(
    connection: sqlite3.Connection,
    video: dict,
) -> None:

    connection.execute(
        """
        INSERT INTO snapshots (
            video_id,
            checked_at,
            views,
            likes,
            comments
        )
        VALUES (
            ?,
            datetime('now'),
            ?,
            ?,
            ?
        )
        """,
        (
            video["video_id"],
            video["views"],
            video["likes"],
            video["comments"],
        ),
    )

def get_all_videos(
    connection: sqlite3.Connection,
) -> list[dict]:
    rows = connection.execute(
        """
        SELECT
            video_id,
            channel_id,
            channel_name,
            subscriber_count,
            title,
            published_at,
            duration_seconds,
            format,
            thumbnail_url,
            video_url
        FROM videos
        """
    ).fetchall()

    return [dict(row) for row in rows]

def close_connection(
    connection: sqlite3.Connection,
) -> None:
    connection.close()