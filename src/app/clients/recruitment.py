import asyncio
from collections.abc import Sequence
from typing import Any

import httpx
from tenacity import AsyncRetrying, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.core.config import Settings


class RecruitmentDataClient:
    """Fetch analysis input data from the backend for recruitment IDs."""

    def __init__(self, http_client: httpx.AsyncClient, settings: Settings) -> None:
        self._http_client = http_client
        self._settings = settings
        self._semaphore = asyncio.Semaphore(settings.backend_fetch_concurrency)

    async def fetch_projects(self, project_ids: Sequence[int]) -> list[Any]:
        return await self._fetch_many(project_ids, self._settings.backend_project_analysis_path)

    async def fetch_studies(self, study_ids: Sequence[int]) -> list[Any]:
        return await self._fetch_many(study_ids, self._settings.backend_study_analysis_path)

    async def _fetch_many(self, entity_ids: Sequence[int], path_template: str) -> list[Any]:
        return await asyncio.gather(
            *(self._fetch_one(entity_id, path_template) for entity_id in entity_ids)
        )

    async def _fetch_one(self, entity_id: int, path_template: str) -> Any:
        async with self._semaphore:
            retrying = AsyncRetrying(
                retry=retry_if_exception_type(httpx.HTTPError),
                wait=wait_exponential(multiplier=0.25, min=0.25, max=2),
                stop=stop_after_attempt(self._settings.delivery_max_attempts),
                reraise=True,
            )
            async for attempt in retrying:
                with attempt:
                    response = await self._http_client.get(path_template.format(id=entity_id))
                    response.raise_for_status()
                    return response.json()
        raise RuntimeError("unreachable")
