from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dependencies import get_backend_client
from app.clients.backend import BackendClient, DeliveryError
from app.schemas.analysis import AnalysisRequest, PipelineResponse
from app.services.pipeline import AnalysisPipeline

router = APIRouter()


@router.post("", response_model=PipelineResponse, status_code=status.HTTP_200_OK)
async def analyze_and_deliver(
    payload: AnalysisRequest,
    backend_client: Annotated[BackendClient, Depends(get_backend_client)],
) -> PipelineResponse:
    pipeline = AnalysisPipeline(backend_client)
    try:
        result = await pipeline.run(payload)
    except DeliveryError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Analysis succeeded, but result delivery failed",
        ) from exc
    return PipelineResponse(status="delivered", result=result)

