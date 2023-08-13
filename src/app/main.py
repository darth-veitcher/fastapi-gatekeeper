from fastapi import FastAPI, Depends, HTTPException, Request
from authlib.integrations.starlette_client import OAuth
from starlette.middleware.sessions import SessionMiddleware
from starlette.config import Config
from starlette.responses import RedirectResponse

app = FastAPI()

# Use Starlette's session middleware
app.add_middleware(SessionMiddleware, secret_key="some-secret-key", max_age=3600)


@app.exception_handler(HTTPException)
async def custom_exception_handler(request: Request, exc: HTTPException):
    if exc.status_code == 401:
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
    client_kwargs={"scope": "openid profile email"},
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
    # user = await oauth.dex.parse_id_token(request, token)
    user = token.get("userinfo")
    # Use 'preferred_username' or 'email' if 'name' doesn't exist
    user_name = user.get("name") or user.get("preferred_username") or user.get("email")
    request.session["user"] = {"name": user_name}
    return RedirectResponse(request.url_for("private_route"))


@app.get("/private-route")
async def private_route(user: dict = Depends(get_current_user)):
    print(user)
    return {"message": f"Hello, {user.get('name', 'unknown user')}!"}
