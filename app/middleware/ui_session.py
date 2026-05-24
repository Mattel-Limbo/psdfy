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
        # List of protected paths (require login)
        protected_paths = ["/", "/ui/convert"]
        
        # List of public paths (no login required)
        public_paths = ["/login", "/health", "/version", "/ui/login", "/ui/logout"]
        
        # Check if path is protected
        is_protected = any(request.url.path.startswith(path) for path in protected_paths)
        is_public = any(request.url.path == path for path in public_paths)
        
        if is_protected and not is_public:
            # Check for session cookie
            session_cookie = request.cookies.get(settings.UI_COOKIE_NAME)
            
            if not session_cookie:
                # No session, redirect to login
                return RedirectResponse(url="/login", status_code=302)
            
            # Session cookie exists, continue
            request.state.session_id = session_cookie
        
        # Process request
        response = await call_next(request)
        return response

