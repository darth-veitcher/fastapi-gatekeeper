# user_auth.py

from fastapi import HTTPException, Depends, Request


def get_current_user(request: Request):
    """Retrieve the current user from the session."""
    user = request.session.get("user")
    if not user:
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
