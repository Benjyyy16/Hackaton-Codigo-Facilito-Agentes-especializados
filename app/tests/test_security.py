"""Tests de utilidades de seguridad.

Cubren todos los caminos documentados: timing-safe comparison, HMAC GitHub, shared secret
Jira, SSRF, sanitización, payload size y CORS por entorno.
"""

from __future__ import annotations

import hashlib
import hmac as hmac_mod

import pytest

from app.core.security import (
    MAX_PAYLOAD_BYTES,
    PayloadTooLargeError,
    assert_payload_size,
    compare_secret,
    cors_origins_for,
    is_safe_url,
    sanitize_log_value,
    verify_github_signature,
    verify_shared_secret,
)


# =============================================================================
# compare_secret
# =============================================================================


class TestCompareSecret:
    def test_correct_match(self) -> None:
        assert compare_secret("my-secret", "my-secret") is True

    def test_incorrect_mismatch(self) -> None:
        assert compare_secret("wrong", "my-secret") is False

    def test_different_lengths(self) -> None:
        assert compare_secret("short", "a-much-longer-secret") is False

    def test_empty_provided(self) -> None:
        assert compare_secret("", "expected") is False

    def test_empty_expected(self) -> None:
        assert compare_secret("provided", "") is False

    def test_none_provided(self) -> None:
        assert compare_secret(None, "expected") is False

    def test_none_expected(self) -> None:
        assert compare_secret("provided", None) is False

    def test_both_none(self) -> None:
        assert compare_secret(None, None) is False


# =============================================================================
# verify_github_signature
# =============================================================================


class TestVerifyGithubSignature:
    def _sign(self, payload: bytes, secret: str) -> str:
        sig = hmac_mod.HMAC(secret.encode(), payload, hashlib.sha256).hexdigest()
        return f"sha256={sig}"

    def test_valid_signature(self) -> None:
        payload = b'{"action":"opened"}'
        secret = "webhook-secret"
        header = self._sign(payload, secret)
        assert verify_github_signature(payload, header, secret) is True

    def test_invalid_signature(self) -> None:
        payload = b'{"action":"opened"}'
        assert verify_github_signature(payload, "sha256=deadbeef", "secret") is False

    def test_absent_header(self) -> None:
        assert verify_github_signature(b"body", None, "secret") is False

    def test_empty_header(self) -> None:
        assert verify_github_signature(b"body", "", "secret") is False

    def test_malformed_prefix(self) -> None:
        """Prefijo diferente al esperado sha256="""
        assert verify_github_signature(b"body", "sha1=abc123", "secret") is False

    def test_wrong_secret(self) -> None:
        payload = b"test-body"
        header = self._sign(payload, "correct-secret")
        assert verify_github_signature(payload, header, "wrong-secret") is False


# =============================================================================
# verify_shared_secret (Jira)
# =============================================================================


class TestVerifySharedSecret:
    def test_correct(self) -> None:
        assert verify_shared_secret("jira-secret", "jira-secret") is True

    def test_incorrect(self) -> None:
        assert verify_shared_secret("wrong", "jira-secret") is False

    def test_none(self) -> None:
        assert verify_shared_secret(None, "jira-secret") is False


# =============================================================================
# is_safe_url (SSRF)
# =============================================================================


class TestIsSafeUrl:
    def test_rejects_file_scheme(self) -> None:
        assert is_safe_url("file:///etc/passwd") is False

    def test_rejects_ftp_scheme(self) -> None:
        assert is_safe_url("ftp://internal.server/data") is False

    def test_rejects_localhost(self) -> None:
        assert is_safe_url("http://localhost/admin") is False

    def test_rejects_127_0_0_1(self) -> None:
        assert is_safe_url("http://127.0.0.1/") is False

    def test_rejects_cloud_metadata(self) -> None:
        assert is_safe_url("http://169.254.169.254/latest/meta-data/") is False

    def test_rejects_10_x(self) -> None:
        assert is_safe_url("http://10.0.0.1/internal") is False

    def test_rejects_192_168_x(self) -> None:
        assert is_safe_url("http://192.168.1.1/admin") is False

    def test_rejects_172_16_x(self) -> None:
        assert is_safe_url("http://172.16.0.1/") is False

    def test_rejects_ipv6_loopback(self) -> None:
        assert is_safe_url("http://[::1]/") is False

    def test_accepts_public_https(self) -> None:
        assert is_safe_url("https://api.github.com/repos") is True

    def test_accepts_public_http(self) -> None:
        assert is_safe_url("http://example.com/webhook") is True

    def test_allowed_hosts_accepts(self) -> None:
        assert is_safe_url("https://trusted.io/path", allowed_hosts={"trusted.io"}) is True

    def test_allowed_hosts_rejects_unlisted(self) -> None:
        assert is_safe_url("https://evil.io/", allowed_hosts={"trusted.io"}) is False

    def test_rejects_empty_url(self) -> None:
        assert is_safe_url("") is False

    def test_rejects_no_scheme(self) -> None:
        assert is_safe_url("just-a-hostname.com") is False


# =============================================================================
# sanitize_log_value
# =============================================================================


class TestSanitizeLogValue:
    def test_redacts_bearer_token(self) -> None:
        result = sanitize_log_value("Authorization: Bearer eyJhbGciOiJIUz...")
        assert "Bearer" not in result or "eyJ" not in result
        assert "[REDACTED]" in result

    def test_redacts_sk_key(self) -> None:
        result = sanitize_log_value("key=sk-1234567890abcdef")
        assert "sk-1234567890" not in result
        assert "[REDACTED]" in result

    def test_redacts_ghp_token(self) -> None:
        result = sanitize_log_value("token ghp_ABCDEFabcdef1234567890")
        assert "ghp_" not in result
        assert "[REDACTED]" in result

    def test_redacts_gho_token(self) -> None:
        result = sanitize_log_value("auth gho_TokenValue123456")
        assert "gho_" not in result
        assert "[REDACTED]" in result

    def test_redacts_jwt(self) -> None:
        result = sanitize_log_value("session=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9")
        assert "eyJhbGciOi" not in result
        assert "[REDACTED]" in result

    def test_redacts_password_param(self) -> None:
        result = sanitize_log_value("url?password=super_secret&user=admin")
        assert "super_secret" not in result
        assert "[REDACTED]" in result

    def test_redacts_token_param(self) -> None:
        result = sanitize_log_value("callback?token=abc123xyz")
        assert "abc123xyz" not in result
        assert "[REDACTED]" in result

    def test_preserves_safe_text(self) -> None:
        safe = "GET /health returned 200"
        assert sanitize_log_value(safe) == safe


# =============================================================================
# assert_payload_size
# =============================================================================


class TestAssertPayloadSize:
    def test_under_limit_passes(self) -> None:
        assert_payload_size(1024)  # no debe elevar

    def test_at_limit_passes(self) -> None:
        assert_payload_size(MAX_PAYLOAD_BYTES)  # exacto, no excede

    def test_over_limit_raises(self) -> None:
        with pytest.raises(PayloadTooLargeError):
            assert_payload_size(MAX_PAYLOAD_BYTES + 1)

    def test_zero_passes(self) -> None:
        assert_payload_size(0)


# =============================================================================
# cors_origins_for
# =============================================================================


class TestCorsOriginsFor:
    def _make_settings(self, env: str, frontend: str = "https://app.example.com"):
        """Crea un mock mínimo de Settings."""
        from app.core.config import Environment

        class FakeSettings:
            FRONTEND_URL = frontend
            ENV = Environment(env)

        return FakeSettings()

    def test_production_no_localhost(self) -> None:
        settings = self._make_settings("production")
        origins = cors_origins_for(settings)
        assert "https://app.example.com" in origins
        assert not any("localhost" in o for o in origins)

    def test_development_includes_localhost(self) -> None:
        settings = self._make_settings("development")
        origins = cors_origins_for(settings)
        assert "http://localhost:3000" in origins
        assert "http://localhost:5173" in origins

    def test_production_only_frontend(self) -> None:
        settings = self._make_settings("production", "https://prod.app")
        origins = cors_origins_for(settings)
        assert origins == ["https://prod.app"]
