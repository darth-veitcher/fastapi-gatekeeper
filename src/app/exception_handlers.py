# exception_handlers.py

from fastapi import HTTPException, Request
from starlette.responses import JSONResponse, RedirectResponse
from authlib.integrations.base_client.errors import MismatchingStateError
from loguru import logger


async def csrf_exception_handler(request: Request, exc: MismatchingStateError):
    logger.debug("CSRF error detected. Wiping session...")
    url = request.session["next_url"] or str(request.url)
    request.session.clear()
    return RedirectResponse(url=url)


async def custom_exception_handler(request: Request, exc: HTTPException):
    if exc.status_code == 401:
        logger.debug(
            "Custom exception unathenticated 401 handler called. Redirecting to login..."
        )
        request.session["next_url"] = str(request.url)
        return RedirectResponse(url=request.url_for("login"))
    if exc.status_code == 403:
        logger.debug("Custom exception unauthorised 403 handler called.")
        return JSONResponse({"message": "Unauthorised. You shouldn't be here."})
    if exc.status_code == 500:
        logger.debug("Custom 500 error called.")
        return JSONResponse({"message": exc})
    # Handle other exceptions the default way or add custom handlers
    return await request.app.exception_handler(request, exc)
