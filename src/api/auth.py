"""JWT authentication and role checks for the API."""

from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import secrets
from typing import Annotated, Any

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .settings import APISettings


def hash_password(password: str, salt: bytes | None = None) -> str:
    """Hash a password with PBKDF2-HMAC-SHA256 and a random salt."""
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 210_000)
    return f"{salt.hex()}${digest.hex()}"


def verify_password(password: str, encoded: str) -> bool:
    """Constant-time verification of a PBKDF2 password hash."""
    try:
        salt_hex, digest_hex = encoded.split("$", 1)
        expected = bytes.fromhex(digest_hex)
        actual = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), bytes.fromhex(salt_hex), 210_000
        )
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


def issue_token(subject: str, role: str, settings: APISettings) -> str:
    """Issue a short-lived signed access token."""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": subject,
        "role": role,
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def build_current_user(settings: APISettings):
    """Build a FastAPI dependency bound to one settings instance."""
    bearer = HTTPBearer(auto_error=False)

    def dependency(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)) -> dict[str, Any]:
        if not settings.require_auth:
            return {"sub": "anonymous", "role": "admin"}
        if credentials is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
        try:
            if settings.auth_mode == "oidc":
                jwks = jwt.PyJWKClient(f"{settings.oidc_issuer.rstrip('/')}/.well-known/jwks.json")
                key = jwks.get_signing_key_from_jwt(credentials.credentials).key
                claims = jwt.decode(
                    credentials.credentials,
                    key,
                    algorithms=["RS256"],
                    audience=settings.oidc_audience,
                    issuer=settings.oidc_issuer,
                    options={"require": ["sub", "exp", "iat"]},
                )
                claims["role"] = claims.get("role", "user")
            else:
                claims = jwt.decode(
                    credentials.credentials,
                    settings.jwt_secret,
                    algorithms=[settings.jwt_algorithm],
                    options={"require": ["sub", "role", "exp", "iat"]},
                )
        except jwt.PyJWTError as exc:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid access token") from exc
        return claims

    return dependency


def require_role(role: str, settings: APISettings):
    """Create a dependency that enforces a minimum role."""
    current = build_current_user(settings)

    def dependency(user: Annotated[dict[str, Any], Depends(current)]) -> dict[str, Any]:
        if role == "admin" and user.get("role") != "admin":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin role required")
        return user

    return dependency
