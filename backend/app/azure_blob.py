from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from .config import Settings


@dataclass
class BlobVideo:
    blob_name: str
    blob_url: str
    sas_url: str | None = None


VIDEO_EXTENSIONS = (".mp4", ".mov", ".m4v", ".avi", ".mkv")


def discover_blob_videos(settings: Settings) -> list[BlobVideo]:
    if not settings.has_blob_config:
        return demo_blob_videos()

    try:
        from azure.storage.blob import (
            BlobSasPermissions,
            BlobServiceClient,
            generate_blob_sas,
        )
    except ImportError as exc:
        raise RuntimeError(
            "azure-storage-blob is not installed. Run `pip install -r backend/requirements.txt`."
        ) from exc

    service = BlobServiceClient.from_connection_string(
        settings.azure_storage_connection_string
    )
    container_name = settings.azure_blob_container_name or ""
    container = service.get_container_client(container_name)
    account_name = service.account_name
    credential = getattr(service, "credential", None)
    account_key = getattr(credential, "account_key", None)

    videos: list[BlobVideo] = []
    for blob in container.list_blobs():
        if not _is_video_blob(blob.name):
            continue
        blob_client = container.get_blob_client(blob.name)
        sas_url = None
        if account_key:
            sas = generate_blob_sas(
                account_name=account_name,
                container_name=container_name,
                blob_name=blob.name,
                account_key=account_key,
                permission=BlobSasPermissions(read=True),
                expiry=datetime.now(timezone.utc) + timedelta(hours=6),
            )
            sas_url = f"{blob_client.url}?{sas}"
        videos.append(BlobVideo(blob_name=blob.name, blob_url=blob_client.url, sas_url=sas_url))
    return videos


def demo_blob_videos() -> list[BlobVideo]:
    return [
        BlobVideo(
            blob_name="demo/heavy-traffic-intersection.mp4",
            blob_url="https://example.com/demo/heavy-traffic-intersection.mp4",
            sas_url="https://example.com/demo/heavy-traffic-intersection.mp4?demo=1",
        ),
        BlobVideo(
            blob_name="demo/bad-road-potholes.mp4",
            blob_url="https://example.com/demo/bad-road-potholes.mp4",
            sas_url="https://example.com/demo/bad-road-potholes.mp4?demo=1",
        ),
        BlobVideo(
            blob_name="demo/street-market-motorcycles.mp4",
            blob_url="https://example.com/demo/street-market-motorcycles.mp4",
            sas_url="https://example.com/demo/street-market-motorcycles.mp4?demo=1",
        ),
    ]


def _is_video_blob(blob_name: str) -> bool:
    return blob_name.lower().endswith(VIDEO_EXTENSIONS)
