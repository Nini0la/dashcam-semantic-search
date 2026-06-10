from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .azure_blob import discover_blob_videos
from .config import get_settings
from .db import get_connection, init_db, utc_now
from .models import ROAD_LABEL_VALUES, VideoStatus
from .schemas import (
    DiscoverResponse,
    IndexResponse,
    LabelOut,
    LabelRequest,
    SearchRequest,
    SearchResponse,
    VideoDetail,
    VideoOut,
)
from .search import (
    add_frame_label,
    get_video,
    list_videos,
    search_frames,
    store_insights,
    update_video_submission,
    upsert_discovered_video,
)
from .video_indexer import VideoIndexerClient, demo_insights


app = FastAPI(title="Dashcam Semantic Search Console")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup() -> None:
    init_db()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/videos", response_model=list[VideoOut])
def videos() -> list[dict]:
    return list_videos()


@app.post("/videos/discover", response_model=DiscoverResponse)
def discover_videos() -> dict:
    settings = get_settings()
    if not settings.use_demo_mode and not settings.has_blob_config:
        raise HTTPException(
            status_code=400,
            detail="Azure Blob settings are required when DEMO_MODE=false",
        )
    blobs = discover_blob_videos(settings)
    for blob in blobs:
        upsert_discovered_video(blob.blob_name, blob.blob_url, blob.sas_url)
    videos_out = list_videos()
    return {
        "demo_mode": settings.use_demo_mode,
        "discovered": len(blobs),
        "videos": videos_out,
    }


@app.post("/videos/index", response_model=IndexResponse)
def index_videos() -> dict:
    settings = get_settings()
    videos_to_index = [
        video
        for video in list_videos()
        if video["status"] in {VideoStatus.DISCOVERED, VideoStatus.FAILED}
    ]
    submitted = 0
    completed = 0
    failed = 0

    if settings.use_demo_mode:
        for video in videos_to_index:
            store_insights(video["id"], demo_insights(video["blob_name"]))
            completed += 1
        return {
            "demo_mode": True,
            "submitted": submitted,
            "completed": completed,
            "failed": failed,
            "videos": list_videos(),
        }

    if not settings.has_video_indexer_config:
        raise HTTPException(
            status_code=400,
            detail="Video Indexer settings are required when DEMO_MODE=false",
        )

    client = VideoIndexerClient(settings)
    for video in videos_to_index:
        video_url = video.get("sas_url") or video["blob_url"]
        try:
            indexer_id = client.submit_video_by_url(video_url, video["blob_name"])
            update_video_submission(video["id"], indexer_id, VideoStatus.SUBMITTED)
            submitted += 1
        except Exception:
            update_video_submission(video["id"], None, VideoStatus.FAILED)
            failed += 1

    return {
        "demo_mode": False,
        "submitted": submitted,
        "completed": completed,
        "failed": failed,
        "videos": list_videos(),
    }


@app.get("/videos/{video_id}", response_model=VideoDetail)
def video_detail(video_id: int) -> dict:
    video = get_video(video_id)
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    return video


@app.get("/videos/{video_id}/status", response_model=VideoOut)
def video_status(video_id: int) -> dict:
    video = get_video(video_id)
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    settings = get_settings()
    if (
        settings.has_video_indexer_config
        and video.get("video_indexer_id")
        and video["status"] in {VideoStatus.SUBMITTED, VideoStatus.INDEXING}
    ):
        client = VideoIndexerClient(settings)
        state = client.get_indexing_status(video["video_indexer_id"])
        normalized = _normalize_indexer_state(state)
        update_video_submission(video_id, video.get("video_indexer_id"), normalized)
        if normalized == VideoStatus.COMPLETED:
            insights = client.fetch_video_insights(video["video_indexer_id"])
            store_insights(video_id, insights)
    refreshed = get_video(video_id)
    if not refreshed:
        raise HTTPException(status_code=404, detail="Video not found")
    refreshed.pop("raw_insights_json", None)
    refreshed.pop("frames", None)
    return refreshed


@app.post("/videos/{video_id}/refresh-insights", response_model=VideoDetail)
def refresh_insights(video_id: int) -> dict:
    video = get_video(video_id)
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    settings = get_settings()
    if settings.use_demo_mode or not video.get("video_indexer_id"):
        store_insights(video_id, demo_insights(video["blob_name"]))
    else:
        client = VideoIndexerClient(settings)
        insights = client.fetch_video_insights(video["video_indexer_id"])
        store_insights(video_id, insights)

    refreshed = get_video(video_id)
    if not refreshed:
        raise HTTPException(status_code=404, detail="Video not found")
    return refreshed


@app.post("/search", response_model=SearchResponse)
def search(request: SearchRequest) -> dict:
    return {
        "results": search_frames(
            query=request.query,
            status=request.status,
            detected_object=request.detected_object,
            road_quality_label=request.road_quality_label,
            min_score=request.min_score,
            limit=request.limit,
        )
    }


@app.post("/frames/{frame_id}/label", response_model=LabelOut)
def label_frame(frame_id: int, request: LabelRequest) -> dict:
    if request.label_type == "road_quality" and request.value not in ROAD_LABEL_VALUES:
        raise HTTPException(status_code=400, detail="Unsupported road quality label")
    label = add_frame_label(frame_id, request.label_type, request.value)
    if not label:
        raise HTTPException(status_code=404, detail="Frame not found")
    _touch_video_for_frame(frame_id)
    return label


def _normalize_indexer_state(state: str) -> str:
    normalized = state.lower()
    if normalized in {"processed", "succeeded", "completed"}:
        return VideoStatus.COMPLETED
    if normalized in {"failed", "error"}:
        return VideoStatus.FAILED
    return VideoStatus.INDEXING


def _touch_video_for_frame(frame_id: int) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE videos
            SET updated_at = ?
            WHERE id = (SELECT video_id FROM frames WHERE id = ?)
            """,
            (utc_now(), frame_id),
        )
