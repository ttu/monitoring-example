"""Authentication API router."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import logging

from config import VALID_TOKENS
from monitoring import auth_attempts_counter, auth_failures_counter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["authentication"])


class LoginRequest(BaseModel):
    """Login request model."""
    username: str
    password: str


class LoginResponse(BaseModel):
    """Login response model."""
    token: str
    token_type: str = "bearer"
    user_id: str


# Simple username to token mapping for demo
USER_CREDENTIALS = {
    "user123": {"password": "password123", "token": "user-token-123"},
    "admin": {"password": "admin123", "token": "admin-token-456"},
    "test": {"password": "test123", "token": "test-token-789"},
}


@router.post("/login", response_model=LoginResponse)
async def login(request: LoginRequest):
    """
    Authenticate user and return token.

    Demo credentials:
    - username: user123, password: password123
    - username: admin, password: admin123
    - username: test, password: test123
    """
    # Record authentication attempt
    auth_attempts_counter.add(1, {"type": "login", "username": request.username})

    # Check if user exists
    if request.username not in USER_CREDENTIALS:
        auth_failures_counter.add(1, {"reason": "invalid_username"})
        logger.warning("Login failed: Invalid username", extra={
            "username": request.username
        })
        raise HTTPException(status_code=401, detail="Invalid username or password")

    # Check password
    user_data = USER_CREDENTIALS[request.username]
    if request.password != user_data["password"]:
        auth_failures_counter.add(1, {"reason": "invalid_password"})
        logger.warning("Login failed: Invalid password", extra={
            "username": request.username
        })
        raise HTTPException(status_code=401, detail="Invalid username or password")

    # Successful login
    token = user_data["token"]
    user_id = f"user_{token[:10]}"

    logger.info("User logged in successfully", extra={
        "username": request.username,
        "user_id": user_id
    })

    return LoginResponse(
        token=token,
        user_id=user_id
    )
