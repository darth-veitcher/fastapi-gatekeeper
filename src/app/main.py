import asyncio
from random import choice
from uuid import uuid4

from authlib.integrations.starlette_client import OAuth
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse
from httpx import AsyncClient
from jose import JWTError, jwt
from app.logger import init_logging
from loguru import logger
from starlette.background import BackgroundTask
from starlette.config import Config
from starlette.middleware.sessions import SessionMiddleware
from starlette.responses import RedirectResponse

app = FastAPI(title="FastAPI Gatekeeper")
init_logging()

# Use Starlette's session middleware
# TODO: replace secret_key with environment variable
app.add_middleware(SessionMiddleware, secret_key="some-secret-key", max_age=3600)


@app.exception_handler(HTTPException)
async def custom_exception_handler(request: Request, exc: HTTPException):
    if exc.status_code == 401:
        logger.debug(
            "Custom exception unathenticated 401 handler called. Redirecting to login..."
        )
        # Store the originally requested URL
        request.session["next_url"] = str(request.url)
        return RedirectResponse(url=request.url_for("login"))
    # Handle other exceptions the default way or add custom handlers
    return await app.exception_handler(request, exc)


config = Config(".env")  # assuming you have a .env file for configurations

oauth = OAuth()
oauth.register(
    name="dex",
    client_id=config("DEX_CLIENT_ID"),
    client_secret=config("DEX_CLIENT_SECRET"),
    authorize_url=config("DEX_AUTHORIZE_URL"),
    authorize_params=None,
    access_token_url=config("DEX_ACCESS_TOKEN_URL"),
    refresh_token_url=None,
    server_metadata_url=config("DEX_SERVER_METADATA_URL"),
    redirect_uri=config("DEX_REDIRECT_URI"),
    client_kwargs={"scope": "openid profile email groups"},
)


def get_current_user(request: Request):
    user = request.session.get("user")
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user


@app.route("/login")
async def login(request: Request):
    redirect_uri = request.url_for("auth")
    return await oauth.dex.authorize_redirect(request, redirect_uri)


@app.route("/auth")
async def auth(request: Request):
    token = await oauth.dex.authorize_access_token(request)

    id_token = token.get("id_token")
    if not id_token:
        raise HTTPException(status_code=400, detail="ID token missing from response")

    jwks_data = oauth.dex.server_metadata.get("jwks")

    # Decode ID token and verify its signature
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

    # Extract user groups
    groups = decoded_token.get("groups", [])

    user = token.get("userinfo") or decoded_token
    # Use 'preferred_username' or 'email' if 'name' doesn't exist
    user_name = user.get("name") or user.get("preferred_username") or user.get("email")

    # Store the user data and the id_token in the session
    request.session["user"] = {
        "name": user_name,
        "groups": groups,
        "id_token": id_token,
    }
    logger.info(f"User `{user_name}` successfully authenticated.")
    logger.debug(request.session.get("user"))

    # Redirect to the original requested URL or default to "/"
    next_url = request.session.pop("next_url", request.url_for("about_me"))
    return RedirectResponse(next_url)


@app.get("/logout")
async def logout(request: Request, user: dict = Depends(get_current_user)):
    # Use the user object obtained from the get_current_user dependency.
    del request.session["user"]
    logger.info(f"Logged out {user.get('name')}.")

    return RedirectResponse("/")


@app.get("/about/me")
async def about_me(user: dict = Depends(get_current_user)):
    logger.info(f"Showing information for `{user.get('name')}`")
    return {"user": user}


@app.get("/private-route")
async def private_route(user: dict = Depends(get_current_user)):
    return {"message": f"Hello, {user.get('name', 'unknown user')}!"}


@app.get("/proxy-endpoint/{resource}")
async def proxy_endpoint(
    resource: str, request: Request, user: dict = Depends(get_current_user)
):
    try:
        client = AsyncClient()
        upstream = choice(
            ["whoami", "httpbin/anything"]
        )  # randomly choose one of the upstreams
        req = client.build_request(
            request.method,
            f"http://{upstream}/{resource}",
            headers=request.headers,
        )
        resp = await client.send(req, stream=True)

        async def content_generator():
            async for chunk in resp.aiter_bytes():
                yield chunk

        def close_response():
            asyncio.run(resp.aclose())

        return StreamingResponse(
            content_generator(),
            headers=dict(resp.headers),
            background=BackgroundTask(close_response),
        )
    except Exception as e:
        logger.error("ERROR: Unable to proxy resource.")
        logger.error(e)
        raise HTTPException(
            status_code=500, detail="An error occurred when proxying the request."
        )
