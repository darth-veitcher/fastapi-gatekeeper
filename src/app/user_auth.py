# user_auth.py
import asyncio
from fastapi import HTTPException, Depends, Request
from loguru import logger


def get_current_user(request: Request):
    """Retrieve the current user from the session."""
    user = request.session.get("user")
    if not user:
        # check if we've got a bearer token in the headers
        payload = asyncio.run(request.app.state.oauth2_scheme(request))
        if payload:
            logger.info(f"OAuth2PasswordBearer: {payload}")
            # authenticate them with the bearer, use `/auth` directly
            from app.routes import _auth_with_bearer_token

            user = asyncio.run(_auth_with_bearer_token(request, payload))
        else:
            raise HTTPException(status_code=401, detail="Not authenticated")
    return user


def get_current_user_group(group: str):
    """Retrieve the current user and check if they belong to the specified group."""

    def _get_user_group(user: dict = Depends(get_current_user)):
        # Check if the desired group is in the user's groups
        if group not in user.get("groups", []):
            raise HTTPException(status_code=403, detail="Not in the required group")
        return user

    return _get_user_group
