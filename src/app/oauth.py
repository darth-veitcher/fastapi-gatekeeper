# oauth.py

from authlib.integrations.starlette_client import OAuth


def init_oauth(app):
    """Initialize and register OAuth client with the provided app."""
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
    return oauth
