"""Pydantic schemas for authentication."""

from pydantic import BaseModel, Field


class ClientSignatureRequest(BaseModel):
    """Request body for POST /auth/client-signature."""
    
    clientSecret: str = Field(
        ...,
        description="Client secret (must be UUIDv4)",
        example="28bf6f2e-fd48-4778-bcd1-edc20726ea0e",
    )
    clientUnixTimestamps: str = Field(
        ...,
        description="Unix timestamp as string",
        example="1779424129",
    )


class ClientSignatureResponse(BaseModel):
    """Response body for POST /auth/client-signature."""
    
    clientSignature: str = Field(
        ...,
        description="Base64-encoded HMAC-SHA256 signature",
    )
    sessionId: str = Field(
        ...,
        description="Session ID (UUIDv4)",
    )


class ErrorResponse(BaseModel):
    """Standard error response."""
    
    error: dict = Field(
        ...,
        description="Error details",
    )


class ErrorDetail(BaseModel):
    """Error detail structure."""
    
    code: str
    message: str
    request_id: str
