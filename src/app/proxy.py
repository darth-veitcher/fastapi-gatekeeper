import asyncio

from fastapi import HTTPException, Request
from fastapi.responses import StreamingResponse
from httpx import URL, AsyncClient
from loguru import logger
from starlette.background import BackgroundTask


async def transparent_proxy(upstream: str, request: Request):
    client = AsyncClient(base_url=upstream)
    url = URL(
        path=request.url.path,
        query=request.url.query.encode("utf-8") if request.url.query else None,
    )
    logger.debug(f"Proxying for: {url}")
    tp_req = client.build_request(
        request.method, url=url, headers=request.headers.raw, content=request.stream()
    )
    logger.debug(f"{tp_req.url}")

    try:
        tp_resp = await client.send(tp_req, stream=True)

        return StreamingResponse(
            tp_resp.aiter_raw(),
            status_code=tp_resp.status_code,
            headers=tp_resp.headers,
            background=BackgroundTask(tp_resp.aclose),
        )
    except Exception as e:
        logger.exception(e)
        return HTTPException(500, detail="Unable to process request.")
