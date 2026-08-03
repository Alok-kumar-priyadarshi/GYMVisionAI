# file_name: auth.py

"""Authentication endpoints.

Implements ``contracts/auth/01_GOOGLE_LOGIN.md`` through
``contracts/auth/04_REFRESH_TOKEN.md``.

Routers stay thin: they parse the request, call a service and shape the
response, per ``docs/04_backend/28_BACKEND_ARCHITECTURE.md`` section 8.
"""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, status

from app.application.services.auth_service import AuthService
from app.core.dependencies import CurrentUser, get_auth_service
from app.domain.entities.user import User
from app.schemas.dto import (
    AccessTokenResponse,
    GoogleLoginRequest,
    LoginResponse,
    RefreshTokenRequest,
    UserResponse,
)
from app.schemas.response import success

router = APIRouter()

AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]


def to_user_response(user: User) -> UserResponse:
    """Shape a user for the API."""
    return UserResponse(
        id=str(user.id),
        name=user.full_name,
        email=user.email,
        picture=user.profile_picture,
        created_at=user.created_at,
        updated_at=user.updated_at,
    )


@router.post(
    "/google",
    status_code=status.HTTP_200_OK,
    summary="Sign in with Google",
    description="Verifies a Google ID token and returns application tokens.",
)
async def google_login(
    payload: GoogleLoginRequest, service: AuthServiceDep
) -> dict[str, Any]:
    """Exchange a Google ID token for an access and refresh token."""
    result = await service.login_with_google(payload.id_token)

    return success(
        "Login successful.",
        LoginResponse(
            access_token=result.tokens.access_token,
            refresh_token=result.tokens.refresh_token,
            expires_in=result.tokens.expires_in,
            user=to_user_response(result.user),
        ).model_dump(by_alias=True),
    )


@router.post(
    "/refresh",
    status_code=status.HTTP_200_OK,
    summary="Refresh an access token",
    description="Exchanges a valid refresh token for a new access token.",
)
async def refresh_token(
    payload: RefreshTokenRequest, service: AuthServiceDep
) -> dict[str, Any]:
    """Issue a new access token."""
    access_token, expires_in = await service.refresh_access_token(payload.refresh_token)

    return success(
        "Access token refreshed successfully.",
        AccessTokenResponse(
            access_token=access_token, expires_in=expires_in
        ).model_dump(by_alias=True),
    )


@router.get(
    "/me",
    status_code=status.HTTP_200_OK,
    summary="Get the authenticated user",
)
async def current_user(user: CurrentUser) -> dict[str, Any]:
    """Return the signed-in user."""
    return success(
        "Authenticated user retrieved successfully.",
        to_user_response(user).model_dump(by_alias=True),
    )


@router.post(
    "/logout",
    status_code=status.HTTP_200_OK,
    summary="Sign out",
    description=(
        "Acknowledges sign-out. Tokens are stateless and time-limited, so the "
        "client discards them; the backend keeps no session to destroy."
    ),
)
async def logout(user: CurrentUser) -> dict[str, Any]:
    """Complete a sign-out.

    Version 1 issues stateless JWTs with no revocation list, so this endpoint
    confirms the request and the client discards its tokens. A token blocklist
    would be required to invalidate a token before it expires.
    """
    return success("Logout successful.", None)
