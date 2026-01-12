"""
Comprehensive JWT authentication tests.

Tests for JWT token validation to ensure authentication security
and prevent bypass attacks.
"""

import os
import time
from datetime import datetime, timedelta, timezone
from typing import Generator

import pytest
from fastapi import HTTPException

# Import jwt generation and validation functions
try:
    from jose import jwt
    JOSE_AVAILABLE = True
except ImportError:
    JOSE_AVAILABLE = False


# ============================================================
# Test Fixtures
# ============================================================


@pytest.fixture
def jwt_secret() -> str:
    """JWT secret key for testing."""
    return "test-secret-key-do-not-use-in-production"


@pytest.fixture
def jwt_config(jwt_secret: str, monkeypatch) -> dict:
    """Set up JWT configuration environment variables."""
    config = {
        "JWT_SECRET_KEY": jwt_secret,
        "JWT_ALGORITHM": "HS256",
        "JWT_ISSUER": "finance-feedback-engine-test",
        "JWT_AUDIENCE": "api-users",
    }

    for key, value in config.items():
        monkeypatch.setenv(key, value)

    return config


@pytest.fixture
def valid_token(jwt_secret: str, jwt_config: dict) -> str:
    """Generate a valid JWT token for testing."""
    if not JOSE_AVAILABLE:
        pytest.skip("python-jose not installed")

    payload = {
        "sub": "test-user-123",  # Subject (user_id)
        "exp": datetime.now(timezone.utc) + timedelta(hours=1),  # Expires in 1 hour
        "iat": datetime.now(timezone.utc),  # Issued at
        "iss": jwt_config["JWT_ISSUER"],  # Issuer
        "aud": jwt_config["JWT_AUDIENCE"],  # Audience
    }

    return jwt.encode(
        payload,
        jwt_secret,
        algorithm=jwt_config["JWT_ALGORITHM"]
    )


@pytest.fixture
def expired_token(jwt_secret: str, jwt_config: dict) -> str:
    """Generate an expired JWT token for testing."""
    if not JOSE_AVAILABLE:
        pytest.skip("python-jose not installed")

    payload = {
        "sub": "test-user-123",
        "exp": datetime.now(timezone.utc) - timedelta(hours=1),  # Expired 1 hour ago
        "iat": datetime.now(timezone.utc) - timedelta(hours=2),  # Issued 2 hours ago
        "iss": jwt_config["JWT_ISSUER"],
        "aud": jwt_config["JWT_AUDIENCE"],
    }

    return jwt.encode(
        payload,
        jwt_secret,
        algorithm=jwt_config["JWT_ALGORITHM"]
    )


@pytest.fixture
def wrong_issuer_token(jwt_secret: str, jwt_config: dict) -> str:
    """Generate a token with wrong issuer for testing."""
    if not JOSE_AVAILABLE:
        pytest.skip("python-jose not installed")

    payload = {
        "sub": "test-user-123",
        "exp": datetime.now(timezone.utc) + timedelta(hours=1),
        "iat": datetime.now(timezone.utc),
        "iss": "wrong-issuer",  # Wrong issuer
        "aud": jwt_config["JWT_AUDIENCE"],
    }

    return jwt.encode(
        payload,
        jwt_secret,
        algorithm=jwt_config["JWT_ALGORITHM"]
    )


@pytest.fixture
def wrong_audience_token(jwt_secret: str, jwt_config: dict) -> str:
    """Generate a token with wrong audience for testing."""
    if not JOSE_AVAILABLE:
        pytest.skip("python-jose not installed")

    payload = {
        "sub": "test-user-123",
        "exp": datetime.now(timezone.utc) + timedelta(hours=1),
        "iat": datetime.now(timezone.utc),
        "iss": jwt_config["JWT_ISSUER"],
        "aud": "wrong-audience",  # Wrong audience
    }

    return jwt.encode(
        payload,
        jwt_secret,
        algorithm=jwt_config["JWT_ALGORITHM"]
    )


@pytest.fixture
def no_sub_token(jwt_secret: str, jwt_config: dict) -> str:
    """Generate a token without 'sub' claim for testing."""
    if not JOSE_AVAILABLE:
        pytest.skip("python-jose not installed")

    payload = {
        # No 'sub' claim
        "exp": datetime.now(timezone.utc) + timedelta(hours=1),
        "iat": datetime.now(timezone.utc),
        "iss": jwt_config["JWT_ISSUER"],
        "aud": jwt_config["JWT_AUDIENCE"],
    }

    return jwt.encode(
        payload,
        jwt_secret,
        algorithm=jwt_config["JWT_ALGORITHM"]
    )


@pytest.fixture
def tampered_token(valid_token: str) -> str:
    """Generate a tampered JWT token (modified after signing)."""
    # Tamper with the token by changing one character
    return valid_token[:-1] + ("A" if valid_token[-1] != "A" else "B")


# ============================================================
# Import validation function (late import to allow monkeypatch)
# ============================================================


def get_validate_jwt_token():
    """Import _validate_jwt_token function dynamically."""
    from finance_feedback_engine.api.routes import _validate_jwt_token
    return _validate_jwt_token


# ============================================================
# Test Cases
# ============================================================


@pytest.mark.skipif(not JOSE_AVAILABLE, reason="python-jose not installed")
class TestJWTValidation:
    """Test JWT token validation."""

    def test_valid_token_accepted(self, valid_token: str, jwt_config: dict):
        """Test that a valid JWT token is accepted."""
        _validate_jwt_token = get_validate_jwt_token()

        user_id = _validate_jwt_token(valid_token)

        assert user_id == "test-user-123"

    def test_expired_token_rejected(self, expired_token: str, jwt_config: dict):
        """Test that an expired JWT token is rejected."""
        _validate_jwt_token = get_validate_jwt_token()

        with pytest.raises(HTTPException) as exc_info:
            _validate_jwt_token(expired_token)

        assert exc_info.value.status_code == 401
        assert "expired" in exc_info.value.detail.lower()

    def test_wrong_issuer_rejected(self, wrong_issuer_token: str, jwt_config: dict):
        """Test that a token with wrong issuer is rejected."""
        _validate_jwt_token = get_validate_jwt_token()

        with pytest.raises(HTTPException) as exc_info:
            _validate_jwt_token(wrong_issuer_token)

        assert exc_info.value.status_code == 401
        assert "issuer" in exc_info.value.detail.lower()

    def test_wrong_audience_rejected(self, wrong_audience_token: str, jwt_config: dict):
        """Test that a token with wrong audience is rejected."""
        _validate_jwt_token = get_validate_jwt_token()

        with pytest.raises(HTTPException) as exc_info:
            _validate_jwt_token(wrong_audience_token)

        assert exc_info.value.status_code == 401
        assert "audience" in exc_info.value.detail.lower()

    def test_no_sub_claim_rejected(self, no_sub_token: str, jwt_config: dict):
        """Test that a token without 'sub' claim is rejected."""
        _validate_jwt_token = get_validate_jwt_token()

        with pytest.raises(HTTPException) as exc_info:
            _validate_jwt_token(no_sub_token)

        assert exc_info.value.status_code == 401
        assert "user identifier" in exc_info.value.detail.lower()

    def test_tampered_token_rejected(self, tampered_token: str, jwt_config: dict):
        """Test that a tampered JWT token is rejected."""
        _validate_jwt_token = get_validate_jwt_token()

        with pytest.raises(HTTPException) as exc_info:
            _validate_jwt_token(tampered_token)

        assert exc_info.value.status_code == 401
        assert "signature" in exc_info.value.detail.lower()

    def test_malformed_token_rejected(self, jwt_config: dict):
        """Test that a malformed JWT token is rejected."""
        _validate_jwt_token = get_validate_jwt_token()

        with pytest.raises(HTTPException) as exc_info:
            _validate_jwt_token("not.a.valid.jwt.token")

        assert exc_info.value.status_code == 401

    def test_empty_token_rejected(self, jwt_config: dict):
        """Test that an empty token is rejected."""
        _validate_jwt_token = get_validate_jwt_token()

        with pytest.raises(HTTPException) as exc_info:
            _validate_jwt_token("")

        assert exc_info.value.status_code == 401

    def test_wrong_algorithm_token_rejected(self, jwt_secret: str, jwt_config: dict):
        """Test that a token signed with wrong algorithm is rejected."""
        # Create token with HS512 instead of HS256
        payload = {
            "sub": "test-user-123",
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
            "iat": datetime.now(timezone.utc),
            "iss": jwt_config["JWT_ISSUER"],
            "aud": jwt_config["JWT_AUDIENCE"],
        }

        wrong_algo_token = jwt.encode(
            payload,
            jwt_secret,
            algorithm="HS512"  # Wrong algorithm
        )

        _validate_jwt_token = get_validate_jwt_token()

        with pytest.raises(HTTPException) as exc_info:
            _validate_jwt_token(wrong_algo_token)

        assert exc_info.value.status_code == 401


@pytest.mark.skipif(not JOSE_AVAILABLE, reason="python-jose not installed")
class TestJWTConfiguration:
    """Test JWT configuration validation."""

    def test_missing_secret_key_rejected(self, monkeypatch):
        """Test that missing JWT_SECRET_KEY is rejected."""
        # Clear all JWT environment variables
        monkeypatch.delenv("JWT_SECRET_KEY", raising=False)
        monkeypatch.delenv("JWT_PUBLIC_KEY", raising=False)

        _validate_jwt_token = get_validate_jwt_token()

        # Try to validate a token (any token)
        with pytest.raises(HTTPException) as exc_info:
            _validate_jwt_token("any.token.here")

        assert exc_info.value.status_code == 401
        assert "not configured" in exc_info.value.detail.lower()

    def test_invalid_algorithm_rejected(self, jwt_secret: str, monkeypatch):
        """Test that invalid JWT_ALGORITHM is rejected."""
        monkeypatch.setenv("JWT_SECRET_KEY", jwt_secret)
        monkeypatch.setenv("JWT_ALGORITHM", "none")  # Dangerous 'none' algorithm

        _validate_jwt_token = get_validate_jwt_token()

        with pytest.raises(HTTPException) as exc_info:
            _validate_jwt_token("any.token.here")

        assert exc_info.value.status_code == 401
        assert "configuration" in exc_info.value.detail.lower()


@pytest.mark.skipif(not JOSE_AVAILABLE, reason="python-jose not installed")
class TestJWTSecurityFeatures:
    """Test JWT security features and attack prevention."""

    def test_algorithm_confusion_attack_prevented(self, jwt_secret: str, jwt_config: dict):
        """
        Test that algorithm confusion attacks are prevented.

        Algorithm confusion: attacker changes algorithm from RS256 to HS256
        and uses the public key as the secret key.
        """
        # This test verifies the 'algorithms' parameter is explicit
        # and not vulnerable to algorithm confusion

        payload = {
            "sub": "test-user-123",
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
            "iat": datetime.now(timezone.utc),
            "iss": jwt_config["JWT_ISSUER"],
            "aud": jwt_config["JWT_AUDIENCE"],
            "alg": "none",  # Try to trick validator
        }

        # Create token with 'none' algorithm (should be rejected)
        none_token = jwt.encode(
            payload,
            "",  # No key
            algorithm="none"
        )

        _validate_jwt_token = get_validate_jwt_token()

        with pytest.raises(HTTPException) as exc_info:
            _validate_jwt_token(none_token)

        assert exc_info.value.status_code == 401

    def test_token_reuse_after_expiry(self, jwt_secret: str, jwt_config: dict):
        """Test that tokens cannot be reused after expiry."""
        # Create a token that expires in 1 second
        payload = {
            "sub": "test-user-123",
            "exp": datetime.now(timezone.utc) + timedelta(seconds=1),
            "iat": datetime.now(timezone.utc),
            "iss": jwt_config["JWT_ISSUER"],
            "aud": jwt_config["JWT_AUDIENCE"],
        }

        short_lived_token = jwt.encode(
            payload,
            jwt_secret,
            algorithm=jwt_config["JWT_ALGORITHM"]
        )

        _validate_jwt_token = get_validate_jwt_token()

        # Token should be valid now
        user_id = _validate_jwt_token(short_lived_token)
        assert user_id == "test-user-123"

        # Wait for expiry
        time.sleep(2)

        # Token should now be expired
        with pytest.raises(HTTPException) as exc_info:
            _validate_jwt_token(short_lived_token)

        assert exc_info.value.status_code == 401
        assert "expired" in exc_info.value.detail.lower()

    def test_forged_token_rejected(self, jwt_secret: str, jwt_config: dict):
        """Test that forged tokens (signed with wrong key) are rejected."""
        wrong_secret = "wrong-secret-key"

        payload = {
            "sub": "attacker",
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
            "iat": datetime.now(timezone.utc),
            "iss": jwt_config["JWT_ISSUER"],
            "aud": jwt_config["JWT_AUDIENCE"],
        }

        # Sign with wrong key
        forged_token = jwt.encode(
            payload,
            wrong_secret,
            algorithm=jwt_config["JWT_ALGORITHM"]
        )

        _validate_jwt_token = get_validate_jwt_token()

        with pytest.raises(HTTPException) as exc_info:
            _validate_jwt_token(forged_token)

        assert exc_info.value.status_code == 401
        assert "signature" in exc_info.value.detail.lower()


@pytest.mark.skipif(not JOSE_AVAILABLE, reason="python-jose not installed")
class TestJWTEdgeCases:
    """Test JWT edge cases and boundary conditions."""

    def test_very_long_user_id(self, jwt_secret: str, jwt_config: dict):
        """Test token with very long user_id."""
        long_user_id = "x" * 10000  # 10KB user_id

        payload = {
            "sub": long_user_id,
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
            "iat": datetime.now(timezone.utc),
            "iss": jwt_config["JWT_ISSUER"],
            "aud": jwt_config["JWT_AUDIENCE"],
        }

        long_id_token = jwt.encode(
            payload,
            jwt_secret,
            algorithm=jwt_config["JWT_ALGORITHM"]
        )

        _validate_jwt_token = get_validate_jwt_token()

        user_id = _validate_jwt_token(long_id_token)
        assert user_id == long_user_id

    def test_special_characters_in_user_id(self, jwt_secret: str, jwt_config: dict):
        """Test token with special characters in user_id."""
        special_user_id = "user@example.com|admin=true&role=superuser"

        payload = {
            "sub": special_user_id,
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
            "iat": datetime.now(timezone.utc),
            "iss": jwt_config["JWT_ISSUER"],
            "aud": jwt_config["JWT_AUDIENCE"],
        }

        special_token = jwt.encode(
            payload,
            jwt_secret,
            algorithm=jwt_config["JWT_ALGORITHM"]
        )

        _validate_jwt_token = get_validate_jwt_token()

        user_id = _validate_jwt_token(special_token)
        assert user_id == special_user_id

    def test_token_about_to_expire(self, jwt_secret: str, jwt_config: dict):
        """Test token that's about to expire (within 1 second)."""
        payload = {
            "sub": "test-user-123",
            "exp": datetime.now(timezone.utc) + timedelta(milliseconds=500),  # 500ms
            "iat": datetime.now(timezone.utc),
            "iss": jwt_config["JWT_ISSUER"],
            "aud": jwt_config["JWT_AUDIENCE"],
        }

        almost_expired_token = jwt.encode(
            payload,
            jwt_secret,
            algorithm=jwt_config["JWT_ALGORITHM"]
        )

        _validate_jwt_token = get_validate_jwt_token()

        # Should still be valid (even if milliseconds away from expiry)
        user_id = _validate_jwt_token(almost_expired_token)
        assert user_id == "test-user-123"


# ============================================================
# Integration Tests
# ============================================================


@pytest.mark.integration
@pytest.mark.skipif(not JOSE_AVAILABLE, reason="python-jose not installed")
class TestJWTIntegration:
    """Integration tests for JWT validation in API context."""

    def test_end_to_end_jwt_flow(self, jwt_secret: str, jwt_config: dict):
        """Test complete JWT flow: generate → validate → extract user."""
        # 1. Generate token (simulates auth service)
        payload = {
            "sub": "integration-test-user",
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
            "iat": datetime.now(timezone.utc),
            "iss": jwt_config["JWT_ISSUER"],
            "aud": jwt_config["JWT_AUDIENCE"],
        }

        token = jwt.encode(
            payload,
            jwt_secret,
            algorithm=jwt_config["JWT_ALGORITHM"]
        )

        # 2. Validate token (simulates API endpoint)
        _validate_jwt_token = get_validate_jwt_token()
        user_id = _validate_jwt_token(token)

        # 3. Verify user_id extracted correctly
        assert user_id == "integration-test-user"

    def test_jwt_validation_performance(self, valid_token: str, jwt_config: dict):
        """Test JWT validation performance (should be fast)."""
        _validate_jwt_token = get_validate_jwt_token()

        start_time = time.time()

        # Validate token 100 times
        for _ in range(100):
            _validate_jwt_token(valid_token)

        elapsed = time.time() - start_time

        # Should complete 100 validations in under 1 second
        assert elapsed < 1.0, f"JWT validation too slow: {elapsed:.2f}s for 100 validations"
