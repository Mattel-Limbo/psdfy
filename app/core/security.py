"""Security utilities for client signature authentication."""

import base64
import hashlib
import hmac
import secrets
import string
import time
import uuid
from abc import ABC, abstractmethod
from typing import Dict, Optional

from app.core.errors import UnauthorizedError, SignatureExpiredError, SignatureRevokedError


def make_salt(n: int = 10) -> str:
    """Generate a random alphanumeric salt of length n."""
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(n))


def is_uuid_v4(value: str) -> bool:
    """Check if a string is a valid UUIDv4."""
    try:
        parsed = uuid.UUID(value, version=4)
        return str(parsed) == value
    except (ValueError, AttributeError):
        return False


def build_signature(
    client_secret: str,
    ts: str,
    salt: str,
    pepper: str = "",
) -> str:
    """
    Build HMAC-SHA256 signature.
    
    Args:
        client_secret: The client's secret (UUIDv4)
        ts: Unix timestamp as string
        salt: Random alphanumeric salt
        pepper: Optional server-side pepper
    
    Returns:
        Base64-encoded HMAC-SHA256 digest
    """
    key = (client_secret + pepper).encode("utf-8")
    msg = (ts + salt).encode("utf-8")
    mac = hmac.new(key, msg, hashlib.sha256).digest()
    return base64.b64encode(mac).decode("ascii")


def hash_secret(secret: str) -> str:
    """Hash a secret for storage (SHA256 hex)."""
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()


class SessionRecord:
    """Represents a stored session record."""
    
    def __init__(
        self,
        session_id: str,
        client_secret_hash: str,
        salt: str,
        signature: str,
        timestamp: int,
        expires_at: int,
        revoked: bool = False,
    ):
        self.session_id = session_id
        self.client_secret_hash = client_secret_hash
        self.salt = salt
        self.signature = signature
        self.timestamp = timestamp
        self.expires_at = expires_at
        self.revoked = revoked
    
    def to_dict(self) -> dict:
        """Convert to dictionary for storage."""
        return {
            "session_id": self.session_id,
            "client_secret_hash": self.client_secret_hash,
            "salt": self.salt,
            "signature": self.signature,
            "timestamp": self.timestamp,
            "expires_at": self.expires_at,
            "revoked": self.revoked,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "SessionRecord":
        """Create from dictionary."""
        return cls(**data)


class SessionStore(ABC):
    """Abstract base class for session storage."""
    
    @abstractmethod
    def put(self, session_id: str, record: SessionRecord) -> None:
        """Store a session record."""
        pass
    
    @abstractmethod
    def get(self, session_id: str) -> Optional[SessionRecord]:
        """Retrieve a session record by ID."""
        pass
    
    @abstractmethod
    def delete(self, session_id: str) -> None:
        """Delete a session record."""
        pass
    
    @abstractmethod
    def revoke(self, session_id: str) -> None:
        """Mark a session as revoked."""
        pass


class InMemorySessionStore(SessionStore):
    """In-memory session store (suitable for MVP)."""
    
    def __init__(self):
        self._store: Dict[str, SessionRecord] = {}
    
    def put(self, session_id: str, record: SessionRecord) -> None:
        """Store a session record."""
        self._store[session_id] = record
    
    def get(self, session_id: str) -> Optional[SessionRecord]:
        """Retrieve a session record by ID."""
        return self._store.get(session_id)
    
    def delete(self, session_id: str) -> None:
        """Delete a session record."""
        self._store.pop(session_id, None)
    
    def revoke(self, session_id: str) -> None:
        """Mark a session as revoked."""
        record = self._store.get(session_id)
        if record:
            record.revoked = True


class SignatureManager:
    """Manages signature issuance and verification."""
    
    def __init__(
        self,
        store: SessionStore,
        ttl_seconds: int = 86400,
        timestamp_skew: int = 300,
        pepper: str = "",
        salt_length: int = 10,
    ):
        self.store = store
        self.ttl_seconds = ttl_seconds
        self.timestamp_skew = timestamp_skew
        self.pepper = pepper
        self.salt_length = salt_length
    
    def issue(self, client_secret: str, client_ts: str) -> dict:
        """
        Issue a new signature and session ID.
        
        Args:
            client_secret: Client's secret (must be UUIDv4)
            client_ts: Unix timestamp as string
        
        Returns:
            Dict with clientSignature and sessionId
        
        Raises:
            UnauthorizedError: If inputs are invalid
        """
        # Validate clientSecret is UUIDv4
        if not is_uuid_v4(client_secret):
            raise UnauthorizedError("clientSecret must be a valid UUIDv4")
        
        # Validate timestamp
        try:
            ts_int = int(client_ts)
        except ValueError:
            raise UnauthorizedError("clientUnixTimestamps must be an integer")
        
        now = int(time.time())
        if abs(now - ts_int) > self.timestamp_skew:
            raise UnauthorizedError(
                f"clientUnixTimestamps must be within {self.timestamp_skew}s of server time"
            )
        
        # Generate session ID and salt
        session_id = str(uuid.uuid4())
        salt = make_salt(self.salt_length)
        
        # Build signature
        signature = build_signature(client_secret, client_ts, salt, self.pepper)
        
        # Create and store session record
        record = SessionRecord(
            session_id=session_id,
            client_secret_hash=hash_secret(client_secret),
            salt=salt,
            signature=signature,
            timestamp=ts_int,
            expires_at=now + self.ttl_seconds,
            revoked=False,
        )
        self.store.put(session_id, record)
        
        return {
            "clientSignature": signature,
            "sessionId": session_id,
        }
    
    def verify(self, session_id: str, client_signature: str) -> SessionRecord:
        """
        Verify a signature and session.
        
        Args:
            session_id: Session ID from header
            client_signature: Signature from header
        
        Returns:
            SessionRecord if valid
        
        Raises:
            UnauthorizedError: If session not found or signature mismatch
            SignatureExpiredError: If session expired
            SignatureRevokedError: If session revoked
        """
        # Load session record
        record = self.store.get(session_id)
        if not record:
            raise UnauthorizedError("Invalid session")
        
        # Check if revoked
        if record.revoked:
            raise SignatureRevokedError()
        
        # Check if expired
        now = int(time.time())
        if record.expires_at < now:
            raise SignatureExpiredError()
        
        # Constant-time comparison of signatures
        if not hmac.compare_digest(client_signature, record.signature):
            raise UnauthorizedError("Invalid signature")
        
        return record
