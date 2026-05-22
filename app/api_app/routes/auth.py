"""Authentication routes for the API app."""

from fastapi import APIRouter, Request
from app.core.security import SignatureManager
from app.core.errors import UnauthorizedError
from app.schemas.auth import ClientSignatureRequest, ClientSignatureResponse

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/client-signature", response_model=ClientSignatureResponse)
async def issue_client_signature(
    request: Request,
    payload: ClientSignatureRequest,
) -> ClientSignatureResponse:
    """
    Issue a client signature and session ID.
    
    This endpoint validates the client secret and timestamp, then returns
    a signature and session ID that can be used to authenticate subsequent requests.
    
    Args:
        request: FastAPI request object
        payload: ClientSignatureRequest with clientSecret and clientUnixTimestamps
    
    Returns:
        ClientSignatureResponse with clientSignature and sessionId
    
    Raises:
        UnauthorizedError: If clientSecret is not UUIDv4 or timestamp is invalid
    """
    signature_manager: SignatureManager = request.app.state.signature_manager
    
    try:
        result = signature_manager.issue(
            payload.clientSecret,
            payload.clientUnixTimestamps,
        )
        return ClientSignatureResponse(**result)
    except UnauthorizedError:
        raise
