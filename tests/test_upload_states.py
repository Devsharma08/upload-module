import pytest

from app.domain.upload_states import (
    ALLOWED_TRANSITIONS,
    TERMINAL_STATES,
    InvalidStateTransition,
    UploadState,
    validate_transition,
)


def test_all_terminal_states_have_no_outgoing_transitions() -> None:
    for state in TERMINAL_STATES:
        with pytest.raises(InvalidStateTransition):
            validate_transition(state, UploadState.RECEIVING)


@pytest.mark.parametrize(
    ("current", "target"),
    [
        (UploadState.RECEIVING, UploadState.VALIDATING),
        (UploadState.VALIDATING, UploadState.SCANNING),
        (UploadState.SCANNING, UploadState.ENCRYPTING),
        (UploadState.ENCRYPTING, UploadState.READY),
        (UploadState.VALIDATING, UploadState.DUPLICATE),
        (UploadState.SCANNING, UploadState.BLOCKED),
    ],
)
def test_allowed_transitions(current: UploadState, target: UploadState) -> None:
    assert target in ALLOWED_TRANSITIONS[current]
    validate_transition(current, target)


@pytest.mark.parametrize(
    ("current", "target"),
    [
        (UploadState.RECEIVING, UploadState.READY),
        (UploadState.VALIDATING, UploadState.ENCRYPTING),
        (UploadState.SCANNING, UploadState.READY),
        (UploadState.READY, UploadState.FAILED),
    ],
)
def test_disallowed_transitions(
    current: UploadState,
    target: UploadState,
) -> None:
    with pytest.raises(InvalidStateTransition):
        validate_transition(current, target)


def test_terminal_state_cannot_transition_to_itself() -> None:
    with pytest.raises(InvalidStateTransition):
        validate_transition(UploadState.READY, UploadState.READY)
