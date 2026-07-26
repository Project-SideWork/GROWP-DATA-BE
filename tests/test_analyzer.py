from uuid import uuid4

from app.schemas.analysis import AnalysisRequest
from app.services.analyzer import analyze


def test_analyze_summarizes_numeric_columns() -> None:
    payload = AnalysisRequest(
        job_id=uuid4(),
        records=[
            {"score": 10, "group": "A"},
            {"score": 20, "group": "B"},
        ],
    )

    result = analyze(payload)

    assert result.row_count == 2
    assert result.numeric_columns["score"].count == 2
    assert result.numeric_columns["score"].mean == 15
    assert result.numeric_columns["score"].minimum == 10
    assert result.numeric_columns["score"].maximum == 20

