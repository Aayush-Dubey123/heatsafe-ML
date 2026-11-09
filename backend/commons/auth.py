from datetime import UTC, datetime, timedelta
from typing import Any

import jwt

from backend.commons.logger import get_logger
from backend.core.config.settings import get_settings

logging = get_logger(__name__)


def _signing_key() -> str:
    """
    Return the configured JWT signing secret.

    There is deliberately no fallback value: admin auth is unusable until a
    secret is configured via HEATSAFE_JWT_SECRET_KEY.

    Returns:
        str: The secret key.

    Raises:
        RuntimeError: If no JWT secret is configured.
    """
    secret = get_settings().jwt_secret_key
    if secret is None or not secret.get_secret_value():
        logging.error("Error in auth signing key lookup: HEATSAFE_JWT_SECRET_KEY is not configured")
        raise RuntimeError("HEATSAFE_JWT_SECRET_KEY is not configured.")
    return secret.get_secret_value()


def create_access_token(
    data: dict[str, Any],
    expires_delta: timedelta | None = None,
) -> str:
    """
    Generate a signed JSON Web Token (JWT) payload with an expiration claim.

    Encodes provided claims with the configured HMAC algorithm and an absolute UTC expiry.

    Args:
        data (dict[str, Any]): Dictionary of claims to include in token payload.
        expires_delta (timedelta | None): Custom expiration duration override.

    Returns:
        str: Encoded JWT token string.

    Raises:
        ValueError: If data dictionary is empty.
        RuntimeError: If no JWT secret is configured.
    """
    if not data:
        logging.error("Error in create_access_token: empty data payload")
        raise ValueError("Token data payload must not be empty.")

    settings = get_settings()
    to_encode = data.copy()
    expire = datetime.now(UTC) + (
        expires_delta if expires_delta else timedelta(minutes=settings.access_token_expire_minutes)
    )
    to_encode.update({"exp": expire})
    logging.info("Executing create_access_token for subject")
    return jwt.encode(to_encode, _signing_key(), algorithm=settings.jwt_algorithm)


def verify_access_token(token: str) -> dict[str, Any]:
    """
    Decode, validate signature, and verify freshness of an inbound JWT.

    Only the configured algorithm is accepted, which blocks algorithm-confusion attacks.

    Args:
        token (str): Raw JWT token string extracted from request header.

    Returns:
        dict[str, Any]: Decoded claims dictionary if valid.

    Raises:
        jwt.PyJWTError: If signature is invalid or token has expired.
        RuntimeError: If no JWT secret is configured.
    """
    settings = get_settings()
    try:
        payload: dict[str, Any] = jwt.decode(token, _signing_key(), algorithms=[settings.jwt_algorithm])
        logging.info("Executing verify_access_token: token verified successfully")
        return payload
    except jwt.PyJWTError as err:
        logging.warning(f"Token rejected in verify_access_token: {type(err).__name__}")
        raise
