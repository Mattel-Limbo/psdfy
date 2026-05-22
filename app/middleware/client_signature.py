"""Client signature verification middleware."""

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
import uuid

from app.core.security import SignatureManager
from app.core.errors import UnauthorizedError, SignatureExpiredError, SignatureRevokedError


class ClientSignatureMiddleware(BaseHTTPMiddleware):
    """Middleware to verify X-Session-Id and X-Client-Signature headers."""
    
    def __init__(self, app, signature_manager: SignatureManager, protected_paths: list = None):
        super().__init__(app)
        self.signature_manager = signature_manager
        self.protected_paths = protected_paths or ["/convert", "/files"]
    
    async def dispatch(self, request: Request, call_next):
        """Process request and verify signature if needed."""
        # Add request ID for logging
        request.state.request_id = str(uuid.uuid4())
        
        # Check if this path requires authentication
        if not self._requires_auth(request.url.path):
            return await call_next(request)
        
        # Extract headers
        session_id = request.headers.get("X-Session-Id")
        client_signature = request.headers.get("X-Client-Signature")
        
        # Verify signature
        try:
            if not session_id or not client_signature:
                raise UnauthorizedError("Missing X-Session-Id or X-Client-Signature header")
            
            record = self.signature_manager.verify(session_id, client_signature)
            request.state.session = record
            
        except UnauthorizedError as e:
            return self._error_response(401, "UNAUTHORIZED", str(e), request.state.request_id)
        except SignatureExpiredError as e:
            return self._error_response(403, "SIGNATURE_EXPIRED", str(e), request.state.request_id)
        except SignatureRevokedError as e:
            return self._error_response(403, "SIGNATURE_REVOKED", str(e), request.state.request_id)
        
        return await call_next(request)
    
    def _requires_auth(self, path: str) -> bool:
        """Check if path requires authentication."""
        for protected_path in self.protected_paths:
            if path.startswith(protected_path):
                return True
        return False
    
    def _error_response(self, status_code: int, code: str, message: str, request_id: str):
        """Create a standardized error response."""
        return JSONResponse(
            status_code=status_code,
            content={
                "error": {
                    "code": code,
                    "message": message,
                    "request_id": request_id,
                }
            },
        )
