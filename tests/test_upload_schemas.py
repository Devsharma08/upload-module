from datetime import datetime, timezone
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.domain.upload_states import UploadState
from app.schemas.uploads import (
    CreateUploadSessionRequest,
    Stage1ReadyHandoff,
    UploadStatusResponse,
)


def valid_handoff() -> dict[str, object]:
    return {
        "document_id": uuid4(),
        "slot_id": "application-123",
        "sha256": "a" * 64,
        "byte_size": 1024,
        "media_type": "application/pdf",
        "encrypted_object_ref": "vault://opaque-object-reference",
        "created_at": datetime.now(timezone.utc),
    }


def test_create_session_accepts_optional_untrusted_hints() -> None:
    request = CreateUploadSessionRequest(
        filename="application.pdf",
        declared_size=1024,
        declared_media_type="application/pdf",
        client_sha256="b" * 64,
    )

    assert request.declared_size == 1024
    assert request.client_sha256 == "b" * 64


@pytest.mark.parametrize(
    "payload",
    [
        {"filename": "", "declared_size": 1},
        {"filename": "file.pdf", "declared_size": 0},
        {"filename": "file.pdf", "declared_size": 1, "client_sha256": "not-a-hash"},
        {"filename": "file.pdf", "declared_size": 1, "unexpected": True},
    ],
)
def test_create_session_rejects_invalid_input(payload: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        CreateUploadSessionRequest.model_validate(payload)


def test_ready_handoff_defaults_to_contract_v1() -> None:
    handoff = Stage1ReadyHandoff.model_validate(valid_handoff())

    assert handoff.contract_version == 1


def test_ready_handoff_rejects_invalid_digest() -> None:
    payload = valid_handoff()
    payload["sha256"] = "bad"

    with pytest.raises(ValidationError):
        Stage1ReadyHandoff.model_validate(payload)


def test_ready_handoff_rejects_unsupported_contract_version() -> None:
    payload = valid_handoff()
    payload["contract_version"] = 2

    with pytest.raises(ValidationError):
        Stage1ReadyHandoff.model_validate(payload)


def test_status_response_can_represent_terminal_failure_without_handoff() -> None:
    now = datetime.now(timezone.utc)
    response = UploadStatusResponse(
        upload_id=uuid4(),
        state=UploadState.REJECTED,
        reason_code="UNSUPPORTED_FORMAT",
        created_at=now,
        updated_at=now,
    )

    assert response.handoff is None


def test_status_response_can_include_ready_handoff() -> None:
    now = datetime.now(timezone.utc)
    response = UploadStatusResponse(
        upload_id=uuid4(),
        state=UploadState.READY,
        created_at=now,
        updated_at=now,
        handoff=Stage1ReadyHandoff.model_validate(valid_handoff()),
    )

    assert response.handoff is not None
    assert response.handoff.contract_version == 1
