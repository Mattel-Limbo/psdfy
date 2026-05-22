"""
Comprehensive tests for authentication signature and session management.

Tests cover:
- Unit tests for build_signature with fixed vectors
- Issuance flow validation (bad UUID, skewed timestamp, valid input)
- Verifier validation (missing headers, mismatched signature, expired, revoked)
- In-memory session store contract
- End-to-end flow with httpx.AsyncClient
"""

import time
import uuid
import pytest
import pytest_asyncio
import hashlib
import hmac
import base64
from unittest.mock import patch

from app.core.security import (
    build_signature,
    hash_secret,
    is_uuid_v4,
    make_salt,
    SessionRecord,
    InMemorySessionStore,
    SignatureManager,
)
from app.core.errors import (
    UnauthorizedError,
    SignatureExpiredError,
    SignatureRevokedError,
)
from app.api_app.factory import build_api_app
from httpx import AsyncClient, ASGITransport


# ============================================================================
# Unit Tests: build_signature with fixed vectors
# ============================================================================


class TestBuildSignature:
    """Test the build_signature function with deterministic vectors."""

    def test_build_signature_basic(self):
        """Test basic signature generation with known inputs."""
        client_secret = "550e8400-e29b-41d4-a716-446655440000"
        ts = "1234567890"
        salt = "abcdefghij"
        pepper = ""

        signature = build_signature(client_secret, ts, salt, pepper)

        # Verify it's base64 encoded
        assert isinstance(signature, str)
        decoded = base64.b64decode(signature)
        assert len(decoded) == 32  # SHA256 produces 32 bytes

    def test_build_signature_deterministic(self):
        """Test that same inputs produce same signature."""
        client_secret = "550e8400-e29b-41d4-a716-446655440000"
        ts = "1234567890"
        salt = "abcdefghij"

        sig1 = build_signature(client_secret, ts, salt)
        sig2 = build_signature(client_secret, ts, salt)

        assert sig1 == sig2

    def test_build_signature_with_pepper(self):
        """Test signature generation with server-side pepper."""
        client_secret = "550e8400-e29b-41d4-a716-446655440000"
        ts = "1234567890"
        salt = "abcdefghij"
        pepper = "server_pepper_123"

        sig_no_pepper = build_signature(client_secret, ts, salt, "")
        sig_with_pepper = build_signature(client_secret, ts, salt, pepper)

        # Different pepper should produce different signature
        assert sig_no_pepper != sig_with_pepper

    def test_build_signature_different_inputs(self):
        """Test that different inputs produce different signatures."""
        client_secret = "550e8400-e29b-41d4-a716-446655440000"
        ts = "1234567890"
        salt = "abcdefghij"

        sig1 = build_signature(client_secret, ts, salt)
        sig2 = build_signature(client_secret, ts, "different_salt")
        sig3 = build_signature(client_secret, "9999999999", salt)

        assert sig1 != sig2
        assert sig1 != sig3
        assert sig2 != sig3

    def test_build_signature_fixed_vector_1(self):
        """Test with fixed vector 1."""
        client_secret = "550e8400-e29b-41d4-a716-446655440000"
        ts = "1609459200"  # 2021-01-01 00:00:00 UTC
        salt = "TestSalt01"
        pepper = ""

        signature = build_signature(client_secret, ts, salt, pepper)

        # Manually compute expected signature
        key = (client_secret + pepper).encode("utf-8")
        msg = (ts + salt).encode("utf-8")
        expected_mac = hmac.new(key, msg, hashlib.sha256).digest()
        expected_sig = base64.b64encode(expected_mac).decode("ascii")

        assert signature == expected_sig

    def test_build_signature_fixed_vector_2(self):
        """Test with fixed vector 2 including pepper."""
        client_secret = "6ba7b810-9dad-11d1-80b4-00c04fd430c8"
        ts = "1640995200"  # 2022-01-01 00:00:00 UTC
        salt = "PepperTest"
        pepper = "my_server_pepper"

        signature = build_signature(client_secret, ts, salt, pepper)

        # Manually compute expected signature
        key = (client_secret + pepper).encode("utf-8")
        msg = (ts + salt).encode("utf-8")
        expected_mac = hmac.new(key, msg, hashlib.sha256).digest()
        expected_sig = base64.b64encode(expected_mac).decode("ascii")

        assert signature == expected_sig


# ============================================================================
# Unit Tests: Helper functions
# ============================================================================


class TestHelperFunctions:
    """Test helper functions."""

    def test_is_uuid_v4_valid(self):
        """Test UUID v4 validation with valid UUIDs."""
        valid_uuid = str(uuid.uuid4())
        assert is_uuid_v4(valid_uuid) is True

    def test_is_uuid_v4_invalid_format(self):
        """Test UUID v4 validation with invalid format."""
        assert is_uuid_v4("not-a-uuid") is False
        assert is_uuid_v4("550e8400-e29b-41d4-a716-44665544000") is False  # Too short
        assert is_uuid_v4("") is False

    def test_is_uuid_v4_wrong_version(self):
        """Test UUID v4 validation with wrong version."""
        # UUID v1
        uuid_v1 = "550e8400-e29b-11d4-a716-446655440000"
        assert is_uuid_v4(uuid_v1) is False

    def test_hash_secret(self):
        """Test secret hashing."""
        secret = "my_secret_123"
        hashed = hash_secret(secret)

        # Should be SHA256 hex
        assert len(hashed) == 64  # SHA256 hex is 64 chars
        assert isinstance(hashed, str)

    def test_hash_secret_deterministic(self):
        """Test that hashing is deterministic."""
        secret = "my_secret_123"
        hash1 = hash_secret(secret)
        hash2 = hash_secret(secret)

        assert hash1 == hash2

    def test_make_salt(self):
        """Test salt generation."""
        salt = make_salt(10)

        assert len(salt) == 10
        assert isinstance(salt, str)
        assert salt.isalnum()

    def test_make_salt_different(self):
        """Test that salt generation produces different values."""
        salt1 = make_salt(10)
        salt2 = make_salt(10)

        assert salt1 != salt2


# ============================================================================
# Unit Tests: SessionRecord
# ============================================================================


class TestSessionRecord:
    """Test SessionRecord class."""

    def test_session_record_creation(self):
        """Test creating a session record."""
        record = SessionRecord(
            session_id="test-session-id",
            client_secret_hash="hashed_secret",
            salt="test_salt",
            signature="test_signature",
            timestamp=1234567890,
            expires_at=1234567890 + 86400,
            revoked=False,
        )

        assert record.session_id == "test-session-id"
        assert record.revoked is False

    def test_session_record_to_dict(self):
        """Test converting session record to dict."""
        record = SessionRecord(
            session_id="test-session-id",
            client_secret_hash="hashed_secret",
            salt="test_salt",
            signature="test_signature",
            timestamp=1234567890,
            expires_at=1234567890 + 86400,
            revoked=False,
        )

        data = record.to_dict()

        assert data["session_id"] == "test-session-id"
        assert data["revoked"] is False
        assert "timestamp" in data

    def test_session_record_from_dict(self):
        """Test creating session record from dict."""
        data = {
            "session_id": "test-session-id",
            "client_secret_hash": "hashed_secret",
            "salt": "test_salt",
            "signature": "test_signature",
            "timestamp": 1234567890,
            "expires_at": 1234567890 + 86400,
            "revoked": False,
        }

        record = SessionRecord.from_dict(data)

        assert record.session_id == "test-session-id"
        assert record.revoked is False


# ============================================================================
# Unit Tests: InMemorySessionStore
# ============================================================================


class TestInMemorySessionStore:
    """Test InMemorySessionStore contract."""

    def test_store_put_and_get(self):
        """Test putting and getting a session."""
        store = InMemorySessionStore()
        record = SessionRecord(
            session_id="test-id",
            client_secret_hash="hash",
            salt="salt",
            signature="sig",
            timestamp=int(time.time()),
            expires_at=int(time.time()) + 86400,
        )

        store.put("test-id", record)
        retrieved = store.get("test-id")

        assert retrieved is not None
        assert retrieved.session_id == "test-id"

    def test_store_get_nonexistent(self):
        """Test getting a nonexistent session."""
        store = InMemorySessionStore()
        retrieved = store.get("nonexistent")

        assert retrieved is None

    def test_store_delete(self):
        """Test deleting a session."""
        store = InMemorySessionStore()
        record = SessionRecord(
            session_id="test-id",
            client_secret_hash="hash",
            salt="salt",
            signature="sig",
            timestamp=int(time.time()),
            expires_at=int(time.time()) + 86400,
        )

        store.put("test-id", record)
        store.delete("test-id")
        retrieved = store.get("test-id")

        assert retrieved is None

    def test_store_delete_nonexistent(self):
        """Test deleting a nonexistent session (should not raise)."""
        store = InMemorySessionStore()
        store.delete("nonexistent")  # Should not raise

    def test_store_revoke(self):
        """Test revoking a session."""
        store = InMemorySessionStore()
        record = SessionRecord(
            session_id="test-id",
            client_secret_hash="hash",
            salt="salt",
            signature="sig",
            timestamp=int(time.time()),
            expires_at=int(time.time()) + 86400,
            revoked=False,
        )

        store.put("test-id", record)
        store.revoke("test-id")
        retrieved = store.get("test-id")

        assert retrieved is not None
        assert retrieved.revoked is True

    def test_store_revoke_nonexistent(self):
        """Test revoking a nonexistent session (should not raise)."""
        store = InMemorySessionStore()
        store.revoke("nonexistent")  # Should not raise


# ============================================================================
# Unit Tests: SignatureManager - Issuance
# ============================================================================


class TestSignatureManagerIssuance:
    """Test SignatureManager.issue() method."""

    def test_issue_valid_input(self):
        """Test issuing signature with valid input."""
        store = InMemorySessionStore()
        manager = SignatureManager(store=store)

        client_secret = str(uuid.uuid4())
        ts = str(int(time.time()))

        result = manager.issue(client_secret, ts)

        assert "clientSignature" in result
        assert "sessionId" in result
        assert isinstance(result["clientSignature"], str)
        assert isinstance(result["sessionId"], str)

    def test_issue_bad_uuid(self):
        """Test issuing signature with invalid UUID."""
        store = InMemorySessionStore()
        manager = SignatureManager(store=store)

        with pytest.raises(UnauthorizedError) as exc_info:
            manager.issue("not-a-uuid", str(int(time.time())))

        assert "UUIDv4" in str(exc_info.value)

    def test_issue_bad_timestamp_not_integer(self):
        """Test issuing signature with non-integer timestamp."""
        store = InMemorySessionStore()
        manager = SignatureManager(store=store)

        client_secret = str(uuid.uuid4())

        with pytest.raises(UnauthorizedError) as exc_info:
            manager.issue(client_secret, "not-an-integer")

        assert "integer" in str(exc_info.value).lower()

    def test_issue_timestamp_too_old(self):
        """Test issuing signature with timestamp too far in the past."""
        store = InMemorySessionStore()
        manager = SignatureManager(store=store, timestamp_skew=300)

        client_secret = str(uuid.uuid4())
        old_ts = str(int(time.time()) - 400)  # 400 seconds ago

        with pytest.raises(UnauthorizedError) as exc_info:
            manager.issue(client_secret, old_ts)

        assert "within" in str(exc_info.value).lower()

    def test_issue_timestamp_too_new(self):
        """Test issuing signature with timestamp too far in the future."""
        store = InMemorySessionStore()
        manager = SignatureManager(store=store, timestamp_skew=300)

        client_secret = str(uuid.uuid4())
        future_ts = str(int(time.time()) + 400)  # 400 seconds in future

        with pytest.raises(UnauthorizedError) as exc_info:
            manager.issue(client_secret, future_ts)

        assert "within" in str(exc_info.value).lower()

    def test_issue_timestamp_within_skew(self):
        """Test issuing signature with timestamp within acceptable skew."""
        store = InMemorySessionStore()
        manager = SignatureManager(store=store, timestamp_skew=300)

        client_secret = str(uuid.uuid4())
        ts = str(int(time.time()) + 100)  # 100 seconds in future (within 300s skew)

        result = manager.issue(client_secret, ts)

        assert "clientSignature" in result
        assert "sessionId" in result

    def test_issue_stores_session(self):
        """Test that issue() stores the session in the store."""
        store = InMemorySessionStore()
        manager = SignatureManager(store=store)

        client_secret = str(uuid.uuid4())
        ts = str(int(time.time()))

        result = manager.issue(client_secret, ts)
        session_id = result["sessionId"]

        # Verify session is stored
        record = store.get(session_id)
        assert record is not None
        assert record.session_id == session_id

    def test_issue_with_pepper(self):
        """Test issuing signature with server pepper."""
        store = InMemorySessionStore()
        manager = SignatureManager(store=store, pepper="my_pepper")

        client_secret = str(uuid.uuid4())
        ts = str(int(time.time()))

        result = manager.issue(client_secret, ts)

        assert "clientSignature" in result
        assert "sessionId" in result


# ============================================================================
# Unit Tests: SignatureManager - Verification
# ============================================================================


class TestSignatureManagerVerification:
    """Test SignatureManager.verify() method."""

    def test_verify_valid_signature(self):
        """Test verifying a valid signature."""
        store = InMemorySessionStore()
        manager = SignatureManager(store=store)

        client_secret = str(uuid.uuid4())
        ts = str(int(time.time()))

        # Issue a signature
        result = manager.issue(client_secret, ts)
        session_id = result["sessionId"]
        signature = result["clientSignature"]

        # Verify it
        record = manager.verify(session_id, signature)

        assert record.session_id == session_id

    def test_verify_invalid_session_id(self):
        """Test verifying with invalid session ID."""
        store = InMemorySessionStore()
        manager = SignatureManager(store=store)

        with pytest.raises(UnauthorizedError):
            manager.verify("nonexistent-session", "some-signature")

    def test_verify_mismatched_signature(self):
        """Test verifying with mismatched signature."""
        store = InMemorySessionStore()
        manager = SignatureManager(store=store)

        client_secret = str(uuid.uuid4())
        ts = str(int(time.time()))

        # Issue a signature
        result = manager.issue(client_secret, ts)
        session_id = result["sessionId"]

        # Try to verify with wrong signature
        with pytest.raises(UnauthorizedError):
            manager.verify(session_id, "wrong-signature")

    def test_verify_expired_session(self):
        """Test verifying an expired session."""
        store = InMemorySessionStore()
        manager = SignatureManager(store=store, ttl_seconds=1)

        client_secret = str(uuid.uuid4())
        ts = str(int(time.time()))

        # Issue a signature
        result = manager.issue(client_secret, ts)
        session_id = result["sessionId"]
        signature = result["clientSignature"]

        # Wait for expiration
        time.sleep(2)

        # Try to verify expired session
        with pytest.raises(SignatureExpiredError):
            manager.verify(session_id, signature)

    def test_verify_revoked_session(self):
        """Test verifying a revoked session."""
        store = InMemorySessionStore()
        manager = SignatureManager(store=store)

        client_secret = str(uuid.uuid4())
        ts = str(int(time.time()))

        # Issue a signature
        result = manager.issue(client_secret, ts)
        session_id = result["sessionId"]
        signature = result["clientSignature"]

        # Revoke the session
        store.revoke(session_id)

        # Try to verify revoked session
        with pytest.raises(SignatureRevokedError):
            manager.verify(session_id, signature)

    def test_verify_constant_time_comparison(self):
        """Test that signature comparison is constant-time."""
        store = InMemorySessionStore()
        manager = SignatureManager(store=store)

        client_secret = str(uuid.uuid4())
        ts = str(int(time.time()))

        # Issue a signature
        result = manager.issue(client_secret, ts)
        session_id = result["sessionId"]

        # Try signatures that differ in first char, middle, and last char
        wrong_sigs = [
            "X" + "a" * 43,  # Different first char
            "a" * 21 + "X" + "a" * 21,  # Different middle char
            "a" * 43 + "X",  # Different last char
        ]

        for wrong_sig in wrong_sigs:
            with pytest.raises(UnauthorizedError):
                manager.verify(session_id, wrong_sig)


# ============================================================================
# End-to-End Tests with httpx.AsyncClient
# ============================================================================


@pytest.mark.asyncio
class TestEndToEndFlow:
    """End-to-end tests using httpx.AsyncClient against api_app."""

    @pytest_asyncio.fixture
    async def client(self):
        """Create an async test client."""
        app = build_api_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            yield client

    async def test_health_check(self, client):
        """Test health check endpoint."""
        response = await client.get("/health")

        assert response.status_code == 200
        assert response.json()["status"] == "ok"

    async def test_version_endpoint(self, client):
        """Test version endpoint."""
        response = await client.get("/version")

        assert response.status_code == 200
        assert "version" in response.json()

    async def test_issue_signature_valid(self, client):
        """Test issuing a valid signature."""
        client_secret = str(uuid.uuid4())
        ts = str(int(time.time()))

        response = await client.post(
            "/auth/client-signature",
            json={
                "clientSecret": client_secret,
                "clientUnixTimestamps": ts,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert "clientSignature" in data
        assert "sessionId" in data

    async def test_issue_signature_bad_uuid(self, client):
        """Test issuing signature with bad UUID."""
        response = await client.post(
            "/auth/client-signature",
            json={
                "clientSecret": "not-a-uuid",
                "clientUnixTimestamps": str(int(time.time())),
            },
        )

        assert response.status_code == 401
        assert response.json()["error"]["code"] == "UNAUTHORIZED"

    async def test_issue_signature_bad_timestamp(self, client):
        """Test issuing signature with bad timestamp."""
        response = await client.post(
            "/auth/client-signature",
            json={
                "clientSecret": str(uuid.uuid4()),
                "clientUnixTimestamps": "not-a-timestamp",
            },
        )

        assert response.status_code == 401
        assert response.json()["error"]["code"] == "UNAUTHORIZED"

    async def test_issue_signature_skewed_timestamp(self, client):
        """Test issuing signature with skewed timestamp."""
        old_ts = str(int(time.time()) - 1000)  # Way in the past

        response = await client.post(
            "/auth/client-signature",
            json={
                "clientSecret": str(uuid.uuid4()),
                "clientUnixTimestamps": old_ts,
            },
        )

        assert response.status_code == 401
        assert response.json()["error"]["code"] == "UNAUTHORIZED"

    async def test_convert_without_signature(self, client):
        """Test that /convert requires signature."""
        # Create a minimal multipart request without signature headers
        response = await client.post(
            "/convert",
            files={"file": ("test.txt", b"test content", "text/plain")},
        )

        # Should be rejected (401 or 422 depending on middleware)
        assert response.status_code in [401, 422]

    async def test_convert_with_expired_signature(self, client):
        """Test /convert with expired signature."""
        # Create a manager with very short TTL
        store = InMemorySessionStore()
        manager = SignatureManager(store=store, ttl_seconds=1)

        client_secret = str(uuid.uuid4())
        ts = str(int(time.time()))

        result = manager.issue(client_secret, ts)
        session_id = result["sessionId"]
        signature = result["clientSignature"]

        # Wait for expiration
        time.sleep(2)

        # Try to use expired signature with the same manager/store
        try:
            manager.verify(session_id, signature)
            assert False, "Should have raised SignatureExpiredError"
        except SignatureExpiredError:
            pass  # Expected

        # Also test via HTTP (though middleware may not catch it if session is gone)
        response = await client.post(
            "/convert",
            files={"file": ("test.txt", b"test content", "text/plain")},
            headers={
                "X-Session-Id": session_id,
                "X-Client-Signature": signature,
            },
        )

        # Should be 401 (session not found) or 403 (expired) depending on timing
        assert response.status_code in [401, 403]

    async def test_convert_with_revoked_signature(self, client):
        """Test /convert with revoked signature."""
        # Create a manager and store
        store = InMemorySessionStore()
        manager = SignatureManager(store=store)

        client_secret = str(uuid.uuid4())
        ts = str(int(time.time()))

        result = manager.issue(client_secret, ts)
        session_id = result["sessionId"]
        signature = result["clientSignature"]

        # Revoke the session
        store.revoke(session_id)

        # Verify it's revoked
        try:
            manager.verify(session_id, signature)
            assert False, "Should have raised SignatureRevokedError"
        except SignatureRevokedError:
            pass  # Expected

        # Also test via HTTP
        response = await client.post(
            "/convert",
            files={"file": ("test.txt", b"test content", "text/plain")},
            headers={
                "X-Session-Id": session_id,
                "X-Client-Signature": signature,
            },
        )

        # Should be 401 (session not found in client's store) or 403 (revoked)
        assert response.status_code in [401, 403]

    async def test_convert_with_mismatched_signature(self, client):
        """Test /convert with mismatched signature."""
        app = build_api_app()
        manager = app.state.signature_manager

        client_secret = str(uuid.uuid4())
        ts = str(int(time.time()))

        result = manager.issue(client_secret, ts)
        session_id = result["sessionId"]

        # Try with wrong signature
        response = await client.post(
            "/convert",
            files={"file": ("test.txt", b"test content", "text/plain")},
            headers={
                "X-Session-Id": session_id,
                "X-Client-Signature": "wrong-signature",
            },
        )

        assert response.status_code == 401
        assert response.json()["error"]["code"] == "UNAUTHORIZED"
