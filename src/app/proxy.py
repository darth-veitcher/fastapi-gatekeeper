from fastapi import HTTPException, Request
from fastapi.responses import StreamingResponse
from httpx import URL, AsyncClient
from loguru import logger
from starlette.background import BackgroundTask
from typing import List


async def transparent_proxy(
    upstream: str, request: Request, replacements: List[tuple] | None
):
    client = AsyncClient(base_url=upstream)
    final_url = request.url.path
    if replacements:
        for r in replacements:
            final_url = final_url.replace(r[0], r[1])
    url = URL(
        path=final_url,
        query=request.url.query.encode("utf-8") if request.url.query else None,
    )
    logger.debug(f"Proxying for: {url}")
    tp_req = client.build_request(
        request.method,
        url=url,
        headers=request.headers.raw,
        content=request.stream(),
    )
    logger.debug(f"{tp_req.url}")
    # logger.debug(f"{vars(tp_req)}")  # Enable for tracing...

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
