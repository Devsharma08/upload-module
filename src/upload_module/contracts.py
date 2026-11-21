from enum import StrEnum


class UploadTrack(StrEnum):
    RESUME = "resume"
    JOB_DESCRIPTION = "job_description"


class UploadOutcome(StrEnum):
    READY = "READY"
    DUPLICATE = "DUPLICATE"
    REJECTED = "REJECTED"
    BLOCKED = "BLOCKED"
    FAILED = "FAILED"
    EXPIRED = "EXPIRED"
