import os
import sys
from pathlib import Path

from authlib.integrations.base_client.errors import MismatchingStateError
from authlib.integrations.starlette_client import OAuth
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from jose import JWTError, jwt
from loguru import logger
from pydantic import ValidationError
from starlette.middleware.sessions import SessionMiddleware
from starlette.responses import RedirectResponse

from app.logger import init_logging
from app.proxy import transparent_proxy
from app.settings import Settings

app: FastAPI


def create_app(env: str | None = None):
    global app
    app = FastAPI(title="FastAPI Gatekeeper")
    init_logging()
    logger.debug("Logging initialised")

    # Determine the environment
    environment = env or os.getenv("GATEKEEPER_ENV")

    # Determine if it's a suffix or a path and
    # Load the .env file based on the environment
    if environment:
        logger.debug(f"Requested environment {environment}")
        if Path(environment).exists() and Path(environment).is_file():
            logger.debug(f"Found file at {environment}")
            load_dotenv(environment)
        else:
            from app import APP_ROOT

            env_file = os.path.join(APP_ROOT, f".env.{environment}")
            if Path(env_file).is_file():
                logger.debug(f"Found file at {env_file}")
                load_dotenv(env_file)
            else:
                logger.error("Unable to determine environment source.")

    # Instantiate settings and attach to the app
    try:
        app.state.settings = Settings()
    except ValidationError as e:
        logger.exception("Unable to load settings. Please configure the environment.")
        logger.error(e)
        sys.exit(1)
    except Exception as e:
        logger.exception(e)
        sys.exit(1)

    # Router
    from app.routes import add_routes, load_config

    config = load_config("routes.sample.yaml")
    app = add_routes(app, config)

    # Use Starlette's session middleware
    # TODO: replace secret_key with environment variable
    app.add_middleware(SessionMiddleware, secret_key="some-secret-key", max_age=3600)

    @app.exception_handler(MismatchingStateError)
    async def csrf_expection_handler(request: Request, exc: MismatchingStateError):
        logger.debug("CSRF error detected. Wiping session...")
        url = request.session["next_url"] or str(request.url)
        request.session.clear()
        return RedirectResponse(url=url)

    @app.exception_handler(HTTPException)
    async def custom_exception_handler(request: Request, exc: HTTPException):
        if exc.status_code == 401:
            logger.debug(
                "Custom exception unathenticated 401 handler called. Redirecting to login..."
            )
            logger.debug(vars(request))
            # Store the originally requested URL
            request.session["next_url"] = str(request.url)
            return RedirectResponse(url=request.url_for("login"))
        if exc.status_code == 403:
            logger.debug("Custom exception unauthorised 403 handler called.")
            return JSONResponse({"message": "Unauthorised. You shouldn't be here."})
        if exc.status_code == 500:
            logger.debug("Custom 500 error called.")
            return JSONResponse({"message": exc})
        # Handle other exceptions the default way or add custom handlers
        return await app.exception_handler(request, exc)

    oauth = OAuth()
    oauth.register(
        name="dex",
        client_id=app.state.settings.OAUTH2_CLIENT_ID,
        client_secret=app.state.settings.OAUTH2_CLIENT_SECRET,
        authorize_url=app.state.settings.OAUTH2_AUTHORIZE_URL,
        authorize_params=None,
        access_token_url=app.state.settings.OAUTH2_ACCESS_TOKEN_URL,
        refresh_token_url=None,
        server_metadata_url=app.state.settings.OAUTH2_SERVER_METADATA_URL,
        redirect_uri=app.state.settings.OAUTH2_REDIRECT_URI,
        client_kwargs={"scope": app.state.settings.OAUTH2_SCOPES},
    )

    def get_current_user(request: Request):
        user = request.session.get("user")
        if not user:
            raise HTTPException(status_code=401, detail="Not authenticated")
        return user

    def get_current_user_group(group: str):
        def _get_user_group(user: dict = Depends(get_current_user)):
            # Check if the desired group is in the user's groups
            if group not in user.get("groups", []):
                raise HTTPException(status_code=403, detail="Not in the required group")
            return user

        return _get_user_group

    @app.route("/login")
    async def login(request: Request):
        redirect_uri = request.url_for("auth")
        return await oauth.dex.authorize_redirect(request, redirect_uri)

    @app.route("/auth")
    async def auth(request: Request):
        token = await oauth.dex.authorize_access_token(request)

        id_token = token.get("id_token")
        if not id_token:
            raise HTTPException(
                status_code=400, detail="ID token missing from response"
            )

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
        user_name = (
            user.get("name") or user.get("preferred_username") or user.get("email")
        )

        # Store the user data and the id_token in the session
        request.session["user"] = {
            "name": user_name,
            "email": user.get("email"),
            "groups": groups,
            "id_token": id_token,
        }
        logger.info(f"User `{user_name}` successfully authenticated.")
        logger.debug(f"Token userinfo: {user}")
        logger.debug(f"Session: {request.session.get('user')}")

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

    @app.get("/proxy-endpoint/{path:path}")
    async def proxy_endpoint(
        path: Path, request: Request, user: dict = Depends(get_current_user)
    ):
        return await transparent_proxy("http://httpbin.org/anything", request)

    @app.get("/admins-only")
    async def admin_endpoint(
        user: dict = Depends(get_current_user_group("admin_staff")),
    ):
        return {"message": "Welcome, admin!"}

    return app
