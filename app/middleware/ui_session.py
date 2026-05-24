"""UI session middleware for authentication."""

from fastapi import Request
from fastapi.responses import RedirectResponse
from starlette.middleware.base import BaseHTTPMiddleware
from app.core.config import settings


class UISessionMiddleware(BaseHTTPMiddleware):
    """Middleware to check UI session and redirect to login if needed."""
    
    async def dispatch(self, request: Request, call_next):
        """
        Check session before processing request.
        
        Protected paths require valid session cookie.
        """
        # List of public paths (no login required)
        public_paths = ["/login", "/health", "/version", "/ui/login", "/ui/logout"]
        
        # Check if current path is public
        is_public = any(request.url.path == path for path in public_paths)
        
        # If path is not public, check for session cookie
        if not is_public:
            session_cookie = request.cookies.get(settings.UI_COOKIE_NAME)
            
            if not session_cookie:
                # No session, redirect to login
                return RedirectResponse(url="/login", status_code=302)
            
            # Session cookie exists, store in request state
            request.state.session_id = session_cookie
        
        # Process request
        response = await call_next(request)
        return response




