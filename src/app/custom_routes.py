from typing import Any, Callable, List, Optional

import yaml
from fastapi import Depends, FastAPI, HTTPException, Request
from pydantic import BaseModel, validator

from app.proxy import transparent_proxy
from app.routes import get_current_user

from pathlib import Path
from loguru import logger
import sys
import os


# ===
# Pydantic Models
# ===
class URIRule(BaseModel):
    """Rules associated with specific URIs for access control."""

    methods: Optional[List[str]]  # If omitted, all methods are allowed.
    roles: Optional[List[str]] = []  # Roles that are allowed to access this path.
    users: Optional[
        List[str]
    ] = []  # Specific users allowed to access. Priority over roles.

    @validator("methods", pre=True, always=True)
    def default_methods(cls, v):
        """Set default HTTP methods if not specified."""
        return v or ["GET", "POST", "PUT", "DELETE", "PATCH"]


class Upstream(BaseModel):
    """Information about an upstream service to proxy to."""

    url: str  # The address of the remote service.
    slug: Optional[str] = None  # Optional identifier for the service.
    uris: dict[str, URIRule]  # Mapping of path to rules.

    @validator("slug", pre=True, always=True)
    def default_slug(cls, v, values, **kwargs):
        if "url" in values and v is None:
            # Generate slug from URL if not provided.
            return values["url"].replace("://", "_").replace(".", "_").replace("/", "_")
        return v


class ProxyConfig(BaseModel):
    """Configuration for proxy routing with access control."""

    upstreams: List[Upstream]


# ===
# Security
# TODO: refactor into dedicated module
# ===
def require_user_in_roles(required_roles: List[str], raise_exception: bool = True):
    def _inner(user: dict = Depends(get_current_user)) -> bool:
        user_roles = user.get("groups", [])
        if len(required_roles) > 0:
            is_match = any(role in required_roles for role in user_roles)
        else:
            logger.debug("No roles required. Defaulting to accept.")
            is_match = True
        logger.debug(
            f"ROLE: {user.get('email')}{'' if is_match else ' not'} matched in route rules. Has {user_roles} {'and' if is_match else 'but'} needs any of {required_roles}."
        )
        if not is_match and raise_exception:
            raise HTTPException(status_code=403, detail="Not in the required roles")
        return is_match

    return _inner


def require_specific_user(users: List[str], raise_exception: bool = True):
    def _inner(user: dict = Depends(get_current_user)) -> bool:
        is_match = user.get("email") in users if len(users) > 0 else True
        logger.debug(
            f"USER: {user.get('email')}{'' if is_match else ' not'} matched in route rules."
        )
        if not is_match and raise_exception:
            raise HTTPException(status_code=403, detail="User not allowed")
        return is_match

    return _inner


def user_or_role_check(
    roles: Optional[List[str]] = None, users: Optional[List[str]] = None
):
    def _check(user: dict = Depends(get_current_user)):
        logger.info(f"Checking {user} against {users} and {roles}")
        # Check roles and users without raising an exception immediately
        role_matched = (
            require_user_in_roles(roles, raise_exception=False)(user) if roles else True
        )
        user_matched = (
            require_specific_user(users, raise_exception=False)(user) if users else True
        )

        # If neither roles nor users match, raise an exception
        if not (role_matched or user_matched):
            logger.info(f"User {user.get('email')} not authorised for route.")
            raise HTTPException(status_code=403, detail="Unauthorized")

        logger.info(f"User {user.get('email')} authorised for route.")
        return True

    return _check


# ===
# Routes Logic
# ===
def load_config(config: str) -> ProxyConfig:
    if Path(config).exists() and Path(config).is_file():
        logger.debug(f"Found routes config at {config}")
    else:
        from app import APP_ROOT

        config_file = os.path.join(APP_ROOT, config)
        if Path(config_file).is_file():
            logger.debug(f"Found routes config at {config_file}")
            config = config_file
        else:
            logger.error("Unable to determine routes config source.")
            sys.exit(1)
    with open(config, "r") as file:
        config_data = yaml.safe_load(file)
        return ProxyConfig(**config_data)


def proxy_route_factory(
    uri_rule: URIRule, upstream_url: str, replacements: List[tuple] | None
) -> Callable:
    async def route(
        request: Request,
        _=Depends(user_or_role_check(roles=uri_rule.roles, users=uri_rule.users)),
    ):
        logger.debug(f"uri_rule: {uri_rule}")
        logger.debug(f"upstream_url: {upstream_url}")
        # Replace the wildcard in the uri with the captured path segment
        return await transparent_proxy(upstream_url, request, replacements=replacements)

    return route


def add_routes(app: FastAPI, config: ProxyConfig):
    for upstream in config.upstreams:
        for uri, uri_rule in upstream.uris.items():
            path = f"/{upstream.slug}{uri}"
            path = path.replace(
                "/*", "/{path:path}"
            )  # replace wildcard with FastAPI path parameter

            logger.info(f"Adding protected route: {path} {uri}, {uri_rule}")

            # The endpoint URL doesn't need the slug adjustment since we're handling that in the proxy_route_factory
            app.add_api_route(
                path=path,
                endpoint=proxy_route_factory(
                    uri_rule, upstream.url, replacements=[(f"/{upstream.slug}", "")]
                ),  # Pass the original uri here
                methods=uri_rule.methods,
                tags=[upstream.slug or upstream.url],
                response_model=Any,
            )

    logger.debug(app.routes)
    return app
