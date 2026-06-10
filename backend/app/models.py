from enum import Enum


class VideoStatus(str, Enum):
    DISCOVERED = "discovered"
    SUBMITTED = "submitted"
    INDEXING = "indexing"
    COMPLETED = "completed"
    FAILED = "failed"


ROAD_LABEL_VALUES = {
    "good road",
    "fair road",
    "poor road",
    "pothole",
    "flooding",
    "obstruction",
    "false match",
}
