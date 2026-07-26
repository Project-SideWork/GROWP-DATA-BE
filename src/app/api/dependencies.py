from typing import Annotated, cast

import httpx
from fastapi import Depends, Request

from app.clients.backend import BackendClient
from app.core.config import Settings, get_settings


def get_http_client(request: Request) -> httpx.AsyncClient:
    return cast(httpx.AsyncClient, request.app.state.http_client)


def get_backend_client(
    http_client: Annotated[httpx.AsyncClient, Depends(get_http_client)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> BackendClient:
    return BackendClient(http_client=http_client, settings=settings)
