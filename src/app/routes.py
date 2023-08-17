# routes.py
import json
import base64
from fastapi import Depends, HTTPException, Request, APIRouter
from starlette.responses import RedirectResponse, JSONResponse
from jose import JWTError, jwt
from loguru import logger
from httpx import AsyncClient

from app.user_auth import get_current_user


router = APIRouter()


@router.get("/login")
async def login(
    request: Request,
):
    redirect_uri = request.url_for("auth")
    oauth = request.app.state.oauth
    return await oauth.dex.authorize_redirect(request, redirect_uri)


async def _auth_with_request_session(request: Request):
    """Authenticates a user based on the attached session."""
    pass


async def _auth_with_bearer_token(request: Request, token: str):
    """Authenticates a user based on the authorisation bearer header."""
    oauth = request.app.state.oauth

    # auth_token = await oauth.dex.authorize_access_token(request)
    # logger.info(auth_token)

    jwks_data = oauth.dex.server_metadata.get("jwks")
    if not jwks_data:
        async with AsyncClient() as client:
            meta = await client.get(
                request.app.state.settings.OAUTH2_SERVER_METADATA_URL
            )
            meta = meta.json()
            res = await client.get(meta.get("jwks_uri"))
            jwks_data = res.content

    # get the at_hash so we can validate this
    # the token comes in a segmented "." string with 3 components
    # 1. algorithm and key
    # 2. details on the issuer, subject, at_hash, groups and other claims
    # 3. ignore
    access_token: str
    try:
        token_segements = token.split(".")
        for s in token_segements[:-1]:
            logger.debug(json.loads(base64.urlsafe_b64decode(s + "==")))
        access_token = json.loads(
            base64.urlsafe_b64decode(token_segements[1] + "==")
        ).get("at_hash")
    except Exception as e:
        logger.error(e)
        pass

    try:
        logger.debug(f"Access Token: {access_token}")
        decoded_token = jwt.decode(
            token,
            jwks_data,
            algorithms=oauth.dex.server_metadata.get(
                "id_token_signing_alg_values_supported"
            ),
            access_token=access_token,
            options={
                "verify_signature": True,
                "verify_aud": False,
                "verify_at_hash": False,
            },  # FIXME: verify the hash...
        )
    except JWTError as e:
        logger.error(e)
        raise HTTPException(status_code=401, detail="Token signature is invalid")

    logger.info(f"Token decoded: {decoded_token}")
    groups = decoded_token.get("groups", [])
    user = decoded_token
    user_name = user.get("name") or user.get("preferred_username") or user.get("email")

    request.session["user"] = {
        "name": user_name,
        "email": user.get("email"),
        "groups": groups,
        "id_token": decoded_token,
    }
    logger.info(f"User `{user_name}` successfully authenticated.")
    return user


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
