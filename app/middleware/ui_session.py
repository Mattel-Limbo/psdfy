"""UI session middleware for authentication."""

import itsdangerous
from fastapi import Request
from fastapi.responses import RedirectResponse
from starlette.middleware.base import BaseHTTPMiddleware
from app.core.config import settings


def _get_ui_signer() -> itsdangerous.TimestampSigner:
    """Return a TimestampSigner using the configured secret key."""
    secret = settings.CLIENT_SECRET or settings.SIGNATURE_SECRET_PEPPER or "default-secret"
    return itsdangerous.TimestampSigner(secret)


def _validate_session_cookie(cookie_value: str) -> str | None:
    """
    Validate a signed session cookie.

    Returns the session_id on success, None if the signature is invalid or
    the cookie has expired.
    """
    try:
        signer = _get_ui_signer()
        session_id = signer.unsign(
            cookie_value,
            max_age=settings.UI_SESSION_TTL_SECONDS,
        )
        if isinstance(session_id, bytes):
            session_id = session_id.decode("utf-8")
        return session_id
    except (itsdangerous.SignatureExpired, itsdangerous.BadSignature):
        return None


class UISessionMiddleware(BaseHTTPMiddleware):
    """Middleware to check UI session and redirect to login if needed."""

    async def dispatch(self, request: Request, call_next):
        """
        Check session before processing request.

        Protected paths require a valid, unexpired, signed session cookie.
        """
        # List of public paths (no login required)
        public_paths = [
            "/login",
            "/health",
            "/version",
            "/ui/login",
            "/ui/logout",
            "/api/capabilities",
        ]

        # Check if current path is public
        is_public = any(request.url.path == path for path in public_paths)

        if not is_public:
            cookie_value = request.cookies.get(settings.UI_COOKIE_NAME)

            if not cookie_value:
                return RedirectResponse(url="/login", status_code=302)

            session_id = _validate_session_cookie(cookie_value)
            if session_id is None:
                # Invalid or expired cookie — clear it and redirect to login
                response = RedirectResponse(url="/login", status_code=302)
                response.delete_cookie(settings.UI_COOKIE_NAME)
                return response

            request.state.session_id = session_id

        return await call_next(request)

