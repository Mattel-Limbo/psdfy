"""UI session middleware for authentication."""

from fastapi import Request
from fastapi.responses import RedirectResponse
from starlette.middleware.base import BaseHTTPMiddleware
from app.core.config import settings
import sys


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
        
        # Debug logging
        print(f"[MIDDLEWARE] Path: {request.url.path}, Public: {is_public}", file=sys.stderr)
        print(f"[MIDDLEWARE] Cookies: {dict(request.cookies)}", file=sys.stderr)
        
        # If path is not public, check for session cookie
        if not is_public:
            session_cookie = request.cookies.get(settings.UI_COOKIE_NAME)
            print(f"[MIDDLEWARE] Looking for cookie '{settings.UI_COOKIE_NAME}': {session_cookie}", file=sys.stderr)
            
            if not session_cookie:
                # No session, redirect to login
                print(f"[MIDDLEWARE] No session cookie found, redirecting to login", file=sys.stderr)
                return RedirectResponse(url="/login", status_code=302)
            
            # Session cookie exists, store in request state
            request.state.session_id = session_cookie
            print(f"[MIDDLEWARE] Session cookie found, allowing access", file=sys.stderr)
        
        # Process request
        response = await call_next(request)
        return response



