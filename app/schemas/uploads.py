from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.domain.upload_states import UploadState


Sha256 = Annotated[str, Field(pattern=r"^[a-fA-F0-9]{64}$")]


class ApiModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CreateUploadSessionRequest(ApiModel):
    filename: str = Field(min_length=1, max_length=255)
    declared_size: int = Field(gt=0)
    declared_media_type: str | None = Field(default=None, max_length=127)
    client_sha256: Sha256 | None = None
    replace_existing: bool = False


class UploadSessionCreated(ApiModel):
    upload_id: UUID
    state: UploadState
    expires_at: datetime
    content_path: str | None = None


class AdvisorySeverity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    HIGH = "high"


class Stage1Advisory(ApiModel):
    code: str = Field(min_length=1, max_length=100)
    severity: AdvisorySeverity
    details: dict[str, str] | None = None


class Stage1ReadyHandoff(ApiModel):
    contract_version: Literal[1] = 1
    document_id: UUID
    slot_id: str = Field(min_length=1, max_length=255)
    sha256: Sha256
    byte_size: int = Field(ge=0)
    media_type: str = Field(min_length=1, max_length=127)
    encrypted_object_ref: str = Field(min_length=1, max_length=2048)
    advisories: list[Stage1Advisory] = Field(default_factory=list)
    created_at: datetime


class UploadStatusResponse(ApiModel):
    upload_id: UUID
    state: UploadState
    reason_code: str | None = None
    created_at: datetime
    updated_at: datetime
    handoff: Stage1ReadyHandoff | None = None


class ApiError(ApiModel):
    code: str
    message: str
    request_id: str