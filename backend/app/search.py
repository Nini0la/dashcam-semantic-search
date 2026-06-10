import json
from typing import Any

from .db import get_connection, utc_now
from .embeddings import (
    cosine_similarity,
    dumps_embedding,
    get_embedding_provider,
    loads_embedding,
)


def row_to_video(row: Any) -> dict[str, Any]:
    return {
        "id": row["id"],
        "blob_name": row["blob_name"],
        "blob_url": row["blob_url"],
        "sas_url": row["sas_url"],
        "video_indexer_id": row["video_indexer_id"],
        "duration": row["duration"],
        "status": row["status"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def row_to_frame(row: Any, user_labels: list[str] | None = None) -> dict[str, Any]:
    return {
        "id": row["id"],
        "video_id": row["video_id"],
        "timestamp_seconds": row["timestamp_seconds"],
        "image_path": row["image_path"],
        "labels": _loads_list(row["labels_json"]),
        "objects": _loads_list(row["objects_json"]),
        "metadata_text": row["metadata_text"] or "",
        "user_labels": user_labels or [],
    }


def upsert_discovered_video(blob_name: str, blob_url: str, sas_url: str | None) -> None:
    now = utc_now()
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO videos (blob_name, blob_url, sas_url, status, created_at, updated_at)
            VALUES (?, ?, ?, 'discovered', ?, ?)
            ON CONFLICT(blob_name) DO UPDATE SET
                blob_url = excluded.blob_url,
                sas_url = excluded.sas_url,
                updated_at = excluded.updated_at
            """,
            (blob_name, blob_url, sas_url, now, now),
        )


def list_videos() -> list[dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute("SELECT * FROM videos ORDER BY created_at DESC, id DESC").fetchall()
    return [row_to_video(row) for row in rows]


def get_video(video_id: int) -> dict[str, Any] | None:
    with get_connection() as conn:
        video = conn.execute("SELECT * FROM videos WHERE id = ?", (video_id,)).fetchone()
        if not video:
            return None
        frames = conn.execute(
            "SELECT * FROM frames WHERE video_id = ? ORDER BY timestamp_seconds",
            (video_id,),
        ).fetchall()
        label_rows = conn.execute(
            """
            SELECT frame_id, value FROM labels
            WHERE frame_id IN (SELECT id FROM frames WHERE video_id = ?)
            ORDER BY created_at DESC
            """,
            (video_id,),
        ).fetchall()
    labels_by_frame: dict[int, list[str]] = {}
    for row in label_rows:
        labels_by_frame.setdefault(row["frame_id"], []).append(row["value"])
    result = row_to_video(video)
    result["raw_insights_json"] = _loads_json(video["raw_insights_json"])
    result["frames"] = [row_to_frame(row, labels_by_frame.get(row["id"], [])) for row in frames]
    return result


def update_video_submission(video_id: int, video_indexer_id: str | None, status: str) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE videos
            SET video_indexer_id = COALESCE(?, video_indexer_id),
                status = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (video_indexer_id, status, utc_now(), video_id),
        )


def store_insights(video_id: int, insights: dict[str, Any], status: str = "completed") -> None:
    frames = extract_frames_from_insights(insights)
    duration = extract_duration(insights)
    provider = get_embedding_provider()
    now = utc_now()
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE videos
            SET duration = COALESCE(?, duration),
                status = ?,
                raw_insights_json = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (duration, status, json.dumps(insights), now, video_id),
        )
        for frame in frames:
            metadata_text = build_metadata_text(frame["labels"], frame["objects"])
            embedding = provider.embed_text(metadata_text)
            conn.execute(
                """
                INSERT INTO frames (
                    video_id, timestamp_seconds, image_path, labels_json, objects_json,
                    embedding_json, metadata_text
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(video_id, timestamp_seconds) DO UPDATE SET
                    image_path = excluded.image_path,
                    labels_json = excluded.labels_json,
                    objects_json = excluded.objects_json,
                    embedding_json = excluded.embedding_json,
                    metadata_text = excluded.metadata_text
                """,
                (
                    video_id,
                    frame["timestamp_seconds"],
                    frame.get("image_path"),
                    json.dumps(frame["labels"]),
                    json.dumps(frame["objects"]),
                    dumps_embedding(embedding),
                    metadata_text,
                ),
            )


def extract_duration(insights: dict[str, Any]) -> float | None:
    for key in ("durationInSeconds", "duration"):
        value = insights.get(key)
        if isinstance(value, (int, float)):
            return float(value)
    videos = insights.get("videos") or []
    for video in videos:
        value = video.get("durationInSeconds") or video.get("duration")
        if isinstance(value, (int, float)):
            return float(value)
    return None


def extract_frames_from_insights(insights: dict[str, Any]) -> list[dict[str, Any]]:
    videos = insights.get("videos") or []
    all_labels: list[str] = []
    all_objects: list[str] = []
    frames: list[dict[str, Any]] = []

    for video in videos:
        video_insights = video.get("insights", {})
        all_labels.extend(_names_from_items(video_insights.get("labels", [])))
        all_objects.extend(_names_from_items(video_insights.get("detectedObjects", [])))
        all_objects.extend(_names_from_items(video_insights.get("objects", [])))

        for demo_frame in video_insights.get("demoFrames", []):
            frames.append(
                {
                    "timestamp_seconds": float(demo_frame["timestamp_seconds"]),
                    "image_path": demo_frame.get("image_path"),
                    "labels": sorted(set(demo_frame.get("labels", []))),
                    "objects": sorted(set(demo_frame.get("objects", []))),
                }
            )

        for shot in video_insights.get("shots", []):
            for key_frame in shot.get("keyFrames", []):
                instances = key_frame.get("instances") or []
                timestamp = _first_timestamp(instances)
                if timestamp is None:
                    continue
                frames.append(
                    {
                        "timestamp_seconds": timestamp,
                        "image_path": None,
                        "labels": sorted(set(all_labels)),
                        "objects": sorted(set(all_objects)),
                    }
                )

    if frames:
        return _dedupe_frames(frames)

    labels = sorted(set(all_labels or _names_from_items(insights.get("labels", []))))
    objects = sorted(set(all_objects))
    if not labels and not objects:
        labels = ["dashcam video"]
    return [
        {
            "timestamp_seconds": 0.0,
            "image_path": None,
            "labels": labels,
            "objects": objects,
        }
    ]


def build_metadata_text(labels: list[str], objects: list[str]) -> str:
    parts = []
    if labels:
        parts.append("labels: " + ", ".join(labels))
    if objects:
        parts.append("objects: " + ", ".join(objects))
    return " | ".join(parts)


def search_frames(
    query: str,
    status: str | None = None,
    detected_object: str | None = None,
    road_quality_label: str | None = None,
    min_score: float = 0.0,
    limit: int = 20,
) -> list[dict[str, Any]]:
    provider = get_embedding_provider()
    query_embedding = provider.embed_text(query)
    query_terms = set(_tokenize(query))
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT
                frames.*,
                videos.blob_name,
                videos.blob_url,
                videos.status,
                GROUP_CONCAT(labels.value, '|||') AS user_label_values
            FROM frames
            JOIN videos ON videos.id = frames.video_id
            LEFT JOIN labels ON labels.frame_id = frames.id
            GROUP BY frames.id
            """
        ).fetchall()

    results: list[dict[str, Any]] = []
    for row in rows:
        labels = _loads_list(row["labels_json"])
        objects = _loads_list(row["objects_json"])
        user_labels = _split_group_concat(row["user_label_values"])
        if status and row["status"] != status:
            continue
        if detected_object and detected_object.lower() not in [obj.lower() for obj in objects]:
            continue
        if road_quality_label and road_quality_label.lower() not in [
            value.lower() for value in user_labels
        ]:
            continue

        metadata_text = row["metadata_text"] or ""
        similarity = cosine_similarity(query_embedding, loads_embedding(row["embedding_json"]))
        keyword_score = _keyword_score(query_terms, metadata_text, labels, objects, user_labels)
        score = max(similarity, keyword_score)
        if score < min_score:
            continue
        results.append(
            {
                "frame_id": row["id"],
                "video_id": row["video_id"],
                "blob_name": row["blob_name"],
                "blob_url": row["blob_url"],
                "timestamp_seconds": row["timestamp_seconds"],
                "image_path": row["image_path"],
                "labels": labels,
                "objects": objects,
                "user_labels": user_labels,
                "metadata_text": metadata_text,
                "similarity_score": round(similarity, 4),
                "keyword_score": round(keyword_score, 4),
                "score": round(score, 4),
            }
        )
    return sorted(results, key=lambda item: item["score"], reverse=True)[:limit]


def add_frame_label(frame_id: int, label_type: str, value: str) -> dict[str, Any] | None:
    now = utc_now()
    with get_connection() as conn:
        frame = conn.execute("SELECT id FROM frames WHERE id = ?", (frame_id,)).fetchone()
        if not frame:
            return None
        cursor = conn.execute(
            """
            INSERT INTO labels (frame_id, label_type, value, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (frame_id, label_type, value, now),
        )
        label_id = cursor.lastrowid
    return {
        "id": label_id,
        "frame_id": frame_id,
        "label_type": label_type,
        "value": value,
        "created_at": now,
    }


def _names_from_items(items: list[Any]) -> list[str]:
    names: list[str] = []
    for item in items:
        if isinstance(item, str):
            names.append(item)
        elif isinstance(item, dict):
            value = item.get("name") or item.get("text") or item.get("label")
            if value:
                names.append(str(value))
    return names


def _first_timestamp(instances: list[dict[str, Any]]) -> float | None:
    for instance in instances:
        for key in ("adjustedStart", "start", "thumbnailId"):
            value = instance.get(key)
            parsed = _parse_timestamp(value)
            if parsed is not None:
                return parsed
    return None


def _parse_timestamp(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    if not isinstance(value, str) or ":" not in value:
        return None
    try:
        parts = [float(part) for part in value.split(":")]
    except ValueError:
        return None
    seconds = 0.0
    for part in parts:
        seconds = seconds * 60 + part
    return seconds


def _dedupe_frames(frames: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_timestamp: dict[float, dict[str, Any]] = {}
    for frame in frames:
        timestamp = float(frame["timestamp_seconds"])
        existing = by_timestamp.setdefault(
            timestamp,
            {
                "timestamp_seconds": timestamp,
                "image_path": frame.get("image_path"),
                "labels": [],
                "objects": [],
            },
        )
        existing["labels"] = sorted(set(existing["labels"]) | set(frame.get("labels", [])))
        existing["objects"] = sorted(set(existing["objects"]) | set(frame.get("objects", [])))
        existing["image_path"] = existing.get("image_path") or frame.get("image_path")
    return sorted(by_timestamp.values(), key=lambda item: item["timestamp_seconds"])


def _keyword_score(
    query_terms: set[str],
    metadata_text: str,
    labels: list[str],
    objects: list[str],
    user_labels: list[str],
) -> float:
    if not query_terms:
        return 0.0
    haystack = " ".join([metadata_text, *labels, *objects, *user_labels])
    haystack_terms = set(_tokenize(haystack))
    if not haystack_terms:
        return 0.0
    matches = len(query_terms & haystack_terms)
    phrase_bonus = 0.25 if " ".join(query_terms) in haystack.lower() else 0.0
    return min(1.0, matches / max(len(query_terms), 1) + phrase_bonus)


def _tokenize(text: str) -> list[str]:
    normalized = "".join(ch.lower() if ch.isalnum() else " " for ch in text)
    return [token for token in normalized.split() if token]


def _loads_list(raw: str | None) -> list[str]:
    value = _loads_json(raw)
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]


def _loads_json(raw: str | None) -> Any:
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


def _split_group_concat(raw: str | None) -> list[str]:
    if not raw:
        return []
    return [value for value in raw.split("|||") if value]
