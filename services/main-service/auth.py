"""Authentication utilities."""
from typing import Optional
from fastapi import Header, HTTPException
import logging

from config import VALID_TOKENS
from monitoring import auth_failures_counter, auth_attempts_counter

logger = logging.getLogger(__name__)


def verify_token(authorization: Optional[str] = Header(None)) -> str:
    """
    Verify authentication token.

    Args:
        authorization: Authorization header value

    Returns:
        Valid token

    Raises:
        HTTPException: If token is invalid or missing
    """
    # Record authentication attempt
    auth_attempts_counter.add(1, {"type": "bearer_token"})

    if authorization is None:
        auth_failures_counter.add(1, {"reason": "missing_header"})
        logger.warning("Authentication failed: Missing authorization header")
        raise HTTPException(status_code=401, detail="Missing authorization header")

    # Extract token (Bearer <token>)
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        auth_failures_counter.add(1, {"reason": "invalid_format"})
        logger.warning("Authentication failed: Invalid authorization header format", extra={
            "auth_header": authorization[:20] + "..." if len(authorization) > 20 else authorization
        })
        raise HTTPException(status_code=401, detail="Invalid authorization header format")

    token = parts[1]
    if token not in VALID_TOKENS:
        auth_failures_counter.add(1, {"reason": "invalid_token"})
        logger.warning("Authentication failed: Invalid token", extra={
            "token_prefix": token[:8] + "..." if len(token) > 8 else token
        })
        raise HTTPException(status_code=401, detail="Invalid token")

    # Successful authentication
    logger.debug("Authentication successful", extra={
        "user_id": get_user_id_from_token(token)
    })
    return token


def get_user_id_from_token(token: str) -> str:
    """
    Extract user ID from token.

    Args:
        token: Authentication token

    Returns:
        User ID
    """
    return f"user_{token[:10]}"
