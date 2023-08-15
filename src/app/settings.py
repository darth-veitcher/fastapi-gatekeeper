# settings.py
import secrets
from pathlib import Path

from pydantic import ConfigDict
from pydantic_settings import BaseSettings

from app import APP_ROOT


class Settings(BaseSettings):
    APP_ROOT: Path = APP_ROOT

    SESSION_SECRET: str = secrets.token_urlsafe(64)

    OAUTH2_CLIENT_ID: str
    OAUTH2_CLIENT_SECRET: str
    OAUTH2_AUTHORIZE_URL: str
    OAUTH2_ACCESS_TOKEN_URL: str
    OAUTH2_REDIRECT_URI: str
    OAUTH2_SERVER_METADATA_URL: str
    OAUTH2_SCOPES: str = "openid profile email groups"

    # Pydantic meta
    # https://docs.pydantic.dev/dev-v2/usage/model_config/
    model_config = ConfigDict(
        env_prefix="GATEKEEPER_", case_sensitive=False
    )  # type: ignore
