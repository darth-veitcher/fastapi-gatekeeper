import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from authlib.integrations.base_client.errors import MismatchingStateError
from starlette.middleware.sessions import SessionMiddleware
from loguru import logger

from app.logger import init_logging
from app.settings import Settings
from pydantic import ValidationError

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
        app.state.settings = Settings()  # type: ignore
    except ValidationError as e:
        logger.exception("Unable to load settings. Please configure the environment.")
        logger.error(e)
        sys.exit(1)
    except Exception as e:
        logger.exception(e)
        sys.exit(1)

    # Use Starlette's session middleware
    # TODO: replace secret_key with environment variable
    app.add_middleware(
        SessionMiddleware, secret_key=app.state.settings.SESSION_SECRET, max_age=3600
    )

    return configure_app(app)


def configure_app(app: FastAPI):
    from app.routes import router as core_router
    from app.custom_routes import add_routes, load_config
    from app.exception_handlers import csrf_exception_handler, custom_exception_handler
    from app.oauth import init_oauth

    # Router
    app.include_router(core_router)
    config = load_config("routes.sample.yaml")
    app = add_routes(app, config)
    # Adding exception handlers
    app.exception_handler(MismatchingStateError)(csrf_exception_handler)
    app.exception_handler(HTTPException)(custom_exception_handler)
    # Initialize OAuth for the application
    app = init_oauth(app)

    return app


# If the app is being run directly (not imported)
if __name__ == "__main__":
    app = create_app()
