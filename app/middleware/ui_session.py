"""UI session middleware for cookie-based authentication."""

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import RedirectResponse
import uuid

from app.core.security import SignatureManager


class UISessionMiddleware(BaseHTTPMiddleware):
    """Middleware for validating UI session cookies."""
    
    def __init__(self, app, signature_manager: SignatureManager, protected_paths: list = None):
        """
        Initialize middleware.
        
        Args:
            app: FastAPI app
            signature_manager: SignatureManager instance
            protected_paths: List of paths that require authentication
        """
        super().__init__(app)
        self.signature_manager = signature_manager
        self.protected_paths = protected_paths or ["/"]
    
    async def dispatch(self, request: Request, call_next):
        """Process request."""
        # Add request ID
        request.state.request_id = str(uuid.uuid4())
        
        # Check if path is protected
        is_protected = any(
            request.url.path.startswith(path) for path in self.protected_paths
        )
        
        if not is_protected:
            return await call_next(request)
        
        # Check for session cookie
        session_cookie = request.cookies.get("psdfy_ui")
        
        if not session_cookie:
            # Redirect to login
            return RedirectResponse(url="/login", status_code=302)
        
        # Validate session (would need to verify signature)
        # For now, just pass through
        request.state.session = {"cookie": session_cookie}
        
        return await call_next(request)
