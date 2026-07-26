import pandas as pd

from app.schemas.analysis import AnalysisRequest, AnalysisResult, NumericSummary


def analyze(payload: AnalysisRequest) -> AnalysisResult:
    frame = pd.DataFrame(payload.records)
    summaries: dict[str, NumericSummary] = {}

    for column in frame.select_dtypes(include="number").columns:
        series = pd.to_numeric(frame[column], errors="coerce").dropna()
        if series.empty:
            continue
        summaries[str(column)] = NumericSummary(
            count=int(series.count()),
            mean=float(series.mean()),
            minimum=float(series.min()),
            maximum=float(series.max()),
        )

    return AnalysisResult(
        job_id=payload.job_id,
        row_count=len(frame),
        numeric_columns=summaries,
    )
