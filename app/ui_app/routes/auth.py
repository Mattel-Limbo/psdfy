"""UI authentication routes."""

from fastapi import APIRouter, Request, Form, Response
from pydantic import BaseModel
import hmac
import uuid

from app.core.config import settings
from app.core.errors import UnauthorizedError
from app.middleware.ui_session import _get_ui_signer

router = APIRouter(tags=["ui-auth"])


class LoginRequest(BaseModel):
    """Login request model."""
    password: str


class LoginResponse(BaseModel):
    """Login response model."""
    status: str
    message: str


@router.post("/ui/login", response_model=LoginResponse)
async def login(
    request: Request,
    password: str = Form(...),
):
    """
    Authenticate user with password and create session.
    
    Args:
        request: FastAPI request
        password: User password
        
    Returns:
        LoginResponse with status
        
    Raises:
        UnauthorizedError: If password is incorrect
    """
    # Verify password (from config or default)
    correct_password = settings.UI_PASSWORD
    
    if not hmac.compare_digest(password, correct_password):
        raise UnauthorizedError("Invalid password")
    
    # Generate session ID
    session_id = str(uuid.uuid4())
    
    # Create signed cookie using the same signer as UISessionMiddleware
    signer = _get_ui_signer()
    cookie_value = signer.sign(session_id)
    
    # Ensure cookie_value is string (not bytes)
    if isinstance(cookie_value, bytes):
        cookie_value = cookie_value.decode('utf-8')
    
    # Create response
    response = Response(
        content='{"status": "success", "message": "Logged in"}',
        status_code=200,
        media_type="application/json",
    )
    
    # Set cookie
    response.set_cookie(
        key=settings.UI_COOKIE_NAME,
        value=cookie_value,
        max_age=settings.UI_SESSION_TTL_SECONDS,
        httponly=True,
        samesite="lax",
    )
    
    return response


@router.post("/ui/logout")
async def logout(request: Request):
    """
    Logout user and clear session.
    
    Args:
        request: FastAPI request
        
    Returns:
        Logout response
    """
    # Create response
    response = Response(
        content='{"status": "success", "message": "Logged out"}',
        status_code=200,
        media_type="application/json",
    )
    
    # Clear cookie
    response.delete_cookie(key=settings.UI_COOKIE_NAME)
    
    return response

