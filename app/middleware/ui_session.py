"""UI session middleware for authentication."""

from fastapi import Request
from fastapi.responses import RedirectResponse
from starlette.middleware.base import BaseHTTPMiddleware
import itsdangerous
from app.core.config import settings


class UISessionMiddleware(BaseHTTPMiddleware):
    """Middleware to check UI session and redirect to login if needed."""
    
    async def dispatch(self, request: Request, call_next):
        """
        Check session before processing request.
        
        Protected paths require valid session cookie.
        """
        # List of protected paths (require login)
        protected_paths = ["/", "/ui/convert"]
        
        # List of public paths (no login required)
        public_paths = ["/login", "/health", "/version", "/ui/login", "/ui/logout"]
        
        # Check if path is protected
        is_protected = any(request.url.path.startswith(path) for path in protected_paths)
        is_public = any(request.url.path == path for path in public_paths)
        
        if is_protected and not is_public:
            # Check for valid session cookie
            session_cookie = request.cookies.get(settings.UI_COOKIE_NAME)
            
            if not session_cookie:
                # No session, redirect to login
                return RedirectResponse(url="/login", status_code=302)
            
            # Try to verify session
            try:
                signer = itsdangerous.TimestampSigner(
                    settings.SIGNATURE_SECRET_PEPPER or "default-secret"
                )
                session_id = signer.unsign(
                    session_cookie,
                    max_age=settings.UI_SESSION_TTL_SECONDS
                )
                # Session is valid, continue
                request.state.session_id = session_id
            except (itsdangerous.SignatureExpired, itsdangerous.BadSignature):
                # Invalid or expired session, redirect to login
                response = RedirectResponse(url="/login", status_code=302)
                response.delete_cookie(key=settings.UI_COOKIE_NAME)
                return response
        
        # Process request
        response = await call_next(request)
        return response
