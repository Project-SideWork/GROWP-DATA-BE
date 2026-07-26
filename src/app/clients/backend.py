import httpx
from tenacity import AsyncRetrying, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.core.config import Settings
from app.schemas.analysis import AnalysisResult


class DeliveryError(RuntimeError):
    """Raised when an analysis result cannot be delivered."""


class BackendClient:
    def __init__(self, http_client: httpx.AsyncClient, settings: Settings) -> None:
        self._http_client = http_client
        self._settings = settings

    async def deliver(self, result: AnalysisResult) -> None:
        headers = {}
        if self._settings.backend_api_key:
            headers["Authorization"] = f"Bearer {self._settings.backend_api_key}"

        try:
            retrying = AsyncRetrying(
                retry=retry_if_exception_type(httpx.HTTPError),
                wait=wait_exponential(multiplier=0.25, min=0.25, max=2),
                stop=stop_after_attempt(self._settings.delivery_max_attempts),
                reraise=True,
            )
            async for attempt in retrying:
                with attempt:
                    await self._deliver_once(result, headers)
        except httpx.HTTPError as exc:
            raise DeliveryError from exc

    async def _deliver_once(
        self,
        result: AnalysisResult,
        headers: dict[str, str],
    ) -> None:
        response = await self._http_client.post(
            self._settings.backend_result_path,
            json=result.model_dump(mode="json"),
            headers=headers,
        )
        response.raise_for_status()
