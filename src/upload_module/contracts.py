from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


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


class CreateUploadRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    owner_id: str = Field(min_length=1, max_length=128)
    job_id: str = Field(min_length=1, max_length=128)
    track: UploadTrack
    filename: str = Field(min_length=1, max_length=255)
    declared_content_type: str | None = Field(default=None, max_length=127)
    declared_size_bytes: int | None = Field(default=None, gt=0)
