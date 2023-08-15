# config.py

from dotenv import load_dotenv
import os
from pathlib import Path
from loguru import logger


def load_env_file(env: str | None = None):
    """Load environment configuration based on the given environment."""
    # Determine the environment
    environment = env or os.getenv("GATEKEEPER_ENV")

    if environment:
        if Path(environment).exists() and Path(environment).is_file():
            load_dotenv(environment)
        else:
            from app import APP_ROOT

            env_file = os.path.join(APP_ROOT, f".env.{environment}")
            if Path(env_file).is_file():
                load_dotenv(env_file)
            else:
                logger.error("Unable to determine environment source.")
