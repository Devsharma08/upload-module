from upload_module.contracts import UploadOutcome, UploadTrack


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
