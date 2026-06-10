from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode

import requests

from .config import Settings


@dataclass
class VideoIndexerClient:
    settings: Settings

    def get_access_token(self, allow_edit: bool = True) -> str:
        if not self.settings.has_video_indexer_config:
            raise RuntimeError("Video Indexer credentials are not configured")

        location = self.settings.video_indexer_location
        account_id = self.settings.video_indexer_account_id
        url = (
            f"https://api.videoindexer.ai/Auth/{location}/Accounts/"
            f"{account_id}/AccessToken"
        )
        response = requests.get(
            url,
            params={"allowEdit": str(allow_edit).lower()},
            headers={"Ocp-Apim-Subscription-Key": self.settings.video_indexer_api_key or ""},
            timeout=30,
        )
        response.raise_for_status()
        return response.text.strip('"')

    def submit_video_by_url(self, video_url: str, name: str) -> str:
        token = self.get_access_token(allow_edit=True)
        location = self.settings.video_indexer_location
        account_id = self.settings.video_indexer_account_id
        url = f"https://api.videoindexer.ai/{location}/Accounts/{account_id}/Videos"
        params = {
            "accessToken": token,
            "name": name,
            "videoUrl": video_url,
            "privacy": "Private",
        }
        # TODO: Confirm account-specific upload flags such as indexingPreset and streamingPreset.
        response = requests.post(url, params=params, timeout=60)
        response.raise_for_status()
        payload = response.json()
        return payload.get("id") or payload.get("videoId")

    def get_indexing_status(self, video_indexer_id: str) -> str:
        token = self.get_access_token(allow_edit=False)
        location = self.settings.video_indexer_location
        account_id = self.settings.video_indexer_account_id
        url = (
            f"https://api.videoindexer.ai/{location}/Accounts/{account_id}/Videos/"
            f"{video_indexer_id}/IndexingState"
        )
        response = requests.get(url, params={"accessToken": token}, timeout=30)
        response.raise_for_status()
        payload = response.json()
        # TODO: Normalize all Video Indexer states once real account responses are observed.
        return str(payload.get("state") or payload.get("status") or payload)

    def fetch_video_insights(self, video_indexer_id: str) -> dict[str, Any]:
        token = self.get_access_token(allow_edit=False)
        location = self.settings.video_indexer_location
        account_id = self.settings.video_indexer_account_id
        params = urlencode({"accessToken": token, "language": "English"})
        url = (
            f"https://api.videoindexer.ai/{location}/Accounts/{account_id}/Videos/"
            f"{video_indexer_id}/Index?{params}"
        )
        response = requests.get(url, timeout=60)
        response.raise_for_status()
        return response.json()


def demo_insights(blob_name: str) -> dict[str, Any]:
    if "potholes" in blob_name:
        labels = ["bad road", "pothole", "truck", "poor surface"]
        objects = ["truck", "car", "road"]
        frames = [
            (12, ["bad road", "pothole"], ["road", "car"]),
            (48, ["poor road", "pothole"], ["truck", "road"]),
            (96, ["bad road", "obstruction"], ["road", "cone"]),
        ]
    elif "market" in blob_name:
        labels = ["street market", "motorcycle", "pedestrian", "heavy traffic"]
        objects = ["motorcycle", "person", "car", "stall"]
        frames = [
            (18, ["street market"], ["person", "stall"]),
            (63, ["motorcycle", "heavy traffic"], ["motorcycle", "car"]),
            (121, ["pedestrian", "street market"], ["person", "motorcycle"]),
        ]
    else:
        labels = ["heavy traffic", "intersection", "truck", "traffic light"]
        objects = ["car", "truck", "traffic light", "bus"]
        frames = [
            (9, ["intersection", "traffic light"], ["car", "traffic light"]),
            (44, ["heavy traffic"], ["car", "bus", "truck"]),
            (117, ["truck", "intersection"], ["truck", "traffic light"]),
        ]

    return {
        "durationInSeconds": 180,
        "summarizedInsights": {"labels": labels},
        "videos": [
            {
                "insights": {
                    "labels": [{"name": label} for label in labels],
                    "detectedObjects": [{"name": obj} for obj in objects],
                    "demoFrames": [
                        {
                            "timestamp_seconds": timestamp,
                            "labels": frame_labels,
                            "objects": frame_objects,
                            "image_path": f"https://placehold.co/480x270?text={timestamp}s",
                        }
                        for timestamp, frame_labels, frame_objects in frames
                    ],
                }
            }
        ],
    }
