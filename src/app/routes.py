# routes.py

from fastapi import Depends, HTTPException, Request, APIRouter
from starlette.responses import RedirectResponse, JSONResponse
from jose import JWTError, jwt
from loguru import logger

from app.user_auth import get_current_user


router = APIRouter()


@router.get("/login")
async def login(
    request: Request,
):
    redirect_uri = request.url_for("auth")
    oauth = request.app.state.oauth
    return await oauth.dex.authorize_redirect(request, redirect_uri)


@router.route("/auth", methods=["GET", "POST"])
async def auth(request: Request):
    oauth = request.app.state.oauth
    token = await oauth.dex.authorize_access_token(request)
    id_token = token.get("id_token")
    if not id_token:
        raise HTTPException(status_code=400, detail="ID token missing from response")

    jwks_data = oauth.dex.server_metadata.get("jwks")

    try:
        decoded_token = jwt.decode(
            id_token,
            jwks_data,
            algorithms=oauth.dex.server_metadata.get(
                "id_token_signing_alg_values_supported"
            ),
            access_token=token.get("access_token"),
            options={"verify_signature": True, "verify_aud": False},
        )
    except JWTError:
        raise HTTPException(status_code=401, detail="Token signature is invalid")

    groups = decoded_token.get("groups", [])
    user = token.get("userinfo") or decoded_token
    user_name = user.get("name") or user.get("preferred_username") or user.get("email")

    request.session["user"] = {
        "name": user_name,
        "email": user.get("email"),
        "groups": groups,
        "id_token": id_token,
    }
    logger.info(f"User `{user_name}` successfully authenticated.")
    next_url = request.session.pop("next_url", request.url_for("about_me"))
    return RedirectResponse(next_url)


@router.get("/logout")
async def logout(request: Request, user: dict = Depends(get_current_user)):
    del request.session["user"]
    logger.info(f"Logged out {user.get('name')}.")
    return JSONResponse({"message": "Successfully logged out."})


@router.get("/about/me")
async def about_me(user: dict = Depends(get_current_user)):
    logger.info(f"Showing information for `{user.get('name')}`")
    return JSONResponse({"user": user})
