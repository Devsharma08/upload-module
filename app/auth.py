import hmac
import os
from dataclasses import dataclass

from fastapi import Header, HTTPException, status


@dataclass(frozen=True)
class TrustedGatewayIdentity:
    principal_id: str
    authorized_slot_id: str
    slot_reservation_id: str


async def require_trusted_gateway(
    gateway_token: str | None = Header(default=None, alias="X-Gateway-Token"),
    principal_id: str | None = Header(
        default=None,
        alias="X-Authenticated-Principal",
    ),
    authorized_slot_id: str | None = Header(
        default=None,
        alias="X-Authorized-Slot",
    ),
    slot_reservation_id: str | None = Header(
        default=None,
        alias="X-Slot-Reservation",
    ),
) -> TrustedGatewayIdentity:
    configured_token = os.environ.get("TRUSTED_GATEWAY_TOKEN")
    if not configured_token or len(configured_token) < 32:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Trusted gateway authentication is not securely configured",
        )
    if gateway_token is None or not hmac.compare_digest(
        gateway_token.encode("utf-8"),
        configured_token.encode("utf-8"),
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Trusted gateway authentication failed",
        )
    if (
        principal_id is None
        or not principal_id.strip()
        or principal_id != principal_id.strip()
        or len(principal_id) > 255
        or authorized_slot_id is None
        or not authorized_slot_id.strip()
        or authorized_slot_id != authorized_slot_id.strip()
        or len(authorized_slot_id) > 255
        or slot_reservation_id is None
        or not slot_reservation_id.strip()
        or slot_reservation_id != slot_reservation_id.strip()
        or len(slot_reservation_id) > 255
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Trusted gateway identity is incomplete",
        )

    return TrustedGatewayIdentity(
        principal_id=principal_id,
        authorized_slot_id=authorized_slot_id,
        slot_reservation_id=slot_reservation_id,
    )
