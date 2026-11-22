import pytest
from pydantic import ValidationError
from upload_module.contracts import (
    CreateUploadRequest,
    UploadOutcome,
    UploadTrack,
)


def test_create_upload_request_accepts_valid_metadata() -> None:
    request = CreateUploadRequest(
        owner_id="owner-1",
        job_id="job-1",
        track="resume",
        filename="resume.pdf",
        declared_content_type="application/pdf",
        declared_size_bytes=1024,
    )

    assert request.track.value == "resume"
    assert request.declared_size_bytes == 1024


def test_upload_tracks_match_the_stage_one_contract() -> None:
    assert [track.value for track in UploadTrack] == [
        "resume",
        "job_description",
    ]


def test_upload_outcomes_match_the_stage_one_contract() -> None:
    assert [outcome.value for outcome in UploadOutcome] == [
        "READY",
        "DUPLICATE",
        "REJECTED",
        "BLOCKED",
        "FAILED",
        "EXPIRED",
    ]

def test_create_upload_request_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        CreateUploadRequest(
            owner_id="owner-1",
            job_id="job-1",
            track="resume",
            filename="resume.pdf",
            unexpected="not allowed",
        )


def test_create_upload_request_rejects_nonpositive_size() -> None:
    with pytest.raises(ValidationError):
        CreateUploadRequest(
            owner_id="owner-1",
            job_id="job-1",
            track="resume",
            filename="resume.pdf",
            declared_size_bytes=0,
        )