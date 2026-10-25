import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional
import jwt
from backend.commons.logger import get_logger

logging = get_logger(__name__)

SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", "heatsafe_insecure_development_secret_key_change_in_prod")
ALGORITHM: str = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES: int = 60


def create_access_token(
    data: Dict[str, Any],
    expires_delta: Optional[timedelta] = None,
) -> str:
    """
    Generate a signed JSON Web Token (JWT) payload with an expiration claim.

    Encodes provided claims with SHA256 HMAC and an absolute UTC expiry time.

    Args:
        data (Dict[str, Any]): Dictionary of claims to include in token payload.
        expires_delta (Optional[timedelta]): Custom expiration duration override.

    Returns:
        str: Encoded JWT token string.

    Raises:
        ValueError: If data dictionary is empty.
    """
    if not data:
        logging.error("Executing create_access_token failed: empty data payload")
        raise ValueError("Token data payload must not be empty.")

    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta if expires_delta else timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire})
    logging.info("Executing create_access_token for subject")
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def verify_access_token(token: str) -> Dict[str, Any]:
    """
    Decode, validate signature, and verify freshness of an inbound JWT.

    Validates that the token signature matches SECRET_KEY and has not expired.

    Args:
        token (str): Raw JWT token string extracted from request header.

    Returns:
        Dict[str, Any]: Decoded claims dictionary if valid.

    Raises:
        jwt.PyJWTError: If signature is invalid or token has expired.
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        logging.info("Executing verify_access_token: token verified successfully")
        return payload
    except jwt.PyJWTError as err:
        logging.warning(f"Executing verify_access_token rejection: {err}")
        raise err
