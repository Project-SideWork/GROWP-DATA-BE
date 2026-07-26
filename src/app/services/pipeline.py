import anyio

from app.clients.backend import BackendClient
from app.schemas.analysis import AnalysisRequest, AnalysisResult
from app.services.analyzer import analyze


class AnalysisPipeline:
    def __init__(self, backend_client: BackendClient) -> None:
        self._backend_client = backend_client

    async def run(self, payload: AnalysisRequest) -> AnalysisResult:
        # pandas is synchronous/CPU-bound, so keep it off the event loop.
        result = await anyio.to_thread.run_sync(analyze, payload)
        await self._backend_client.deliver(result)
        return result

