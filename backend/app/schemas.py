from typing import Any, Optional

from pydantic import BaseModel, Field


class VideoOut(BaseModel):
    id: int
    blob_name: str
    blob_url: str
    sas_url: Optional[str] = None
    video_indexer_id: Optional[str] = None
    duration: Optional[float] = None
    status: str
    created_at: str
    updated_at: str


class VideoDetail(VideoOut):
    raw_insights_json: Optional[Any] = None
    frames: list["FrameOut"] = Field(default_factory=list)


class FrameOut(BaseModel):
    id: int
    video_id: int
    timestamp_seconds: float
    image_path: Optional[str] = None
    labels: list[str] = Field(default_factory=list)
    objects: list[str] = Field(default_factory=list)
    metadata_text: str = ""
    user_labels: list[str] = Field(default_factory=list)


class DiscoverResponse(BaseModel):
    demo_mode: bool
    discovered: int
    videos: list[VideoOut]


class IndexResponse(BaseModel):
    demo_mode: bool
    submitted: int
    completed: int
    failed: int = 0
    videos: list[VideoOut]


class SearchRequest(BaseModel):
    query: str = ""
    status: Optional[str] = None
    detected_object: Optional[str] = None
    road_quality_label: Optional[str] = None
    min_score: float = Field(default=0.0, ge=0.0, le=1.0)
    limit: int = Field(default=20, ge=1, le=100)


class SearchResult(BaseModel):
    frame_id: int
    video_id: int
    blob_name: str
    blob_url: str
    timestamp_seconds: float
    image_path: Optional[str] = None
    labels: list[str] = Field(default_factory=list)
    objects: list[str] = Field(default_factory=list)
    user_labels: list[str] = Field(default_factory=list)
    metadata_text: str
    similarity_score: float
    keyword_score: float
    score: float


class SearchResponse(BaseModel):
    results: list[SearchResult]


class LabelRequest(BaseModel):
    label_type: str = "road_quality"
    value: str


class LabelOut(BaseModel):
    id: int
    frame_id: int
    label_type: str
    value: str
    created_at: str
