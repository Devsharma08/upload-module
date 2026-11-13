from enum import StrEnum


class UploadState(StrEnum):
    RECEIVING = "RECEIVING"
    VALIDATING = "VALIDATING"
    SCANNING = "SCANNING"
    ENCRYPTING = "ENCRYPTING"

    READY = "READY"
    REJECTED = "REJECTED"
    BLOCKED = "BLOCKED"
    FAILED = "FAILED"
    EXPIRED = "EXPIRED"
    DUPLICATE = "DUPLICATE"


TERMINAL_STATES = frozenset({
    UploadState.READY,
    UploadState.REJECTED,
    UploadState.BLOCKED,
    UploadState.FAILED,
    UploadState.EXPIRED,
    UploadState.DUPLICATE,
})


ALLOWED_TRANSITIONS: dict[UploadState, frozenset[UploadState]] = {
    UploadState.RECEIVING: frozenset({
        UploadState.VALIDATING,
        UploadState.REJECTED,
        UploadState.FAILED,
        UploadState.EXPIRED,
    }),
    UploadState.VALIDATING: frozenset({
        UploadState.DUPLICATE,
        UploadState.REJECTED,
        UploadState.SCANNING,
        UploadState.FAILED,
    }),
    UploadState.SCANNING: frozenset({
        UploadState.BLOCKED,
        UploadState.REJECTED,
        UploadState.ENCRYPTING,
        UploadState.FAILED,
    }),
    UploadState.ENCRYPTING: frozenset({
        UploadState.READY,
        UploadState.FAILED,
    }),
}


class InvalidStateTransition(ValueError):
    pass


def validate_transition(current: UploadState, target: UploadState) -> None:
    if target not in ALLOWED_TRANSITIONS.get(current, frozenset()):
        raise InvalidStateTransition(
            f"Transition {current.value} -> {target.value} is not allowed"
        )