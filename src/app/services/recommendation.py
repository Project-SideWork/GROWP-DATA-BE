from __future__ import annotations

import re
from datetime import UTC, datetime

from app.schemas.recommendation import (
    Applicant,
    ApplicantDataset,
    ApplicantRecommendation,
    RankingSaveItem,
    RankingSaveRequest,
    RecommendationResult,
    RecruitmentPosition,
    ScoreDetail,
    TargetType,
)

TARGET_WEIGHTS: dict[TargetType, dict[str, float]] = {
    TargetType.PROJECT: {
        "requiredSkillMatch": 0.40,
        "preferredSkillMatch": 0.10,
        "roleMatch": 0.25,
        "experienceMatch": 0.15,
        "availabilityMatch": 0.10,
    },
    TargetType.STUDY: {
        "interviewScore": 0.55,
        "availabilityMatch": 0.25,
        "experienceMatch": 0.15,
        "motivationScore": 0.05,
    },
    TargetType.CLUB: {
        "interviewScore": 0.45,
        "motivationScore": 0.35,
        "availabilityMatch": 0.10,
        "experienceMatch": 0.10,
    },
}
CONFIDENCE_THRESHOLDS = {
    TargetType.PROJECT: 0.55,
    TargetType.STUDY: 0.50,
    TargetType.CLUB: 0.50,
}


def _normalize(value: str) -> str:
    return re.sub(r"[^0-9a-z가-힣+#.]", "", value.casefold())


def _ratio(required: list[str], actual: set[str]) -> tuple[float, list[str], list[str]]:
    normalized = {_normalize(value): value for value in required if _normalize(value)}
    if not normalized:
        return 0, [], []
    matched = [original for key, original in normalized.items() if key in actual]
    missing = [original for key, original in normalized.items() if key not in actual]
    return len(matched) / len(normalized) * 100, matched, missing


def _position(dataset: ApplicantDataset, applicant: Applicant) -> RecruitmentPosition | None:
    if applicant.applied_position_id is not None:
        for position in dataset.target.positions:
            if position.position_id == applicant.applied_position_id:
                return position
    if applicant.applied_role:
        role = _normalize(applicant.applied_role)
        for position in dataset.target.positions:
            if _normalize(position.role) == role:
                return position
    return dataset.target.positions[0] if len(dataset.target.positions) == 1 else None


def _recommendation(score: float) -> str:
    if score >= 85:
        return "HIGHLY_RECOMMENDED"
    if score >= 70:
        return "RECOMMENDED"
    if score >= 55:
        return "REVIEW"
    return "LOW_FIT"


def _text_score(value: str) -> float:
    """Score substantive free text without interpreting sensitive attributes."""
    length = len(value.strip())
    if length == 0:
        return 0.0
    return min(100.0, length / 80 * 100)


def _analyze_applicant(
    dataset: ApplicantDataset, applicant: Applicant
) -> ApplicantRecommendation:
    weights = TARGET_WEIGHTS[dataset.target.target_type]
    confidence_threshold = CONFIDENCE_THRESHOLDS[dataset.target.target_type]
    position = _position(dataset, applicant)
    details: dict[str, ScoreDetail] = {}
    strengths: list[str] = []
    concerns: list[str] = []

    skill_values = applicant.skills.copy()
    for experience in applicant.experiences:
        skill_values.extend(experience.skills)
    for portfolio in applicant.portfolios:
        skill_values.extend(portfolio.skills)
    actual_skills = {_normalize(value) for value in skill_values if _normalize(value)}

    if "requiredSkillMatch" in weights and position and position.required_skills:
        score, matched, missing = _ratio(position.required_skills, actual_skills)
        details["requiredSkillMatch"] = ScoreDetail(
            score=score,
            weight=weights["requiredSkillMatch"],
            evidence=[
                f"일치: {', '.join(matched) or '없음'}",
                f"누락: {', '.join(missing) or '없음'}",
            ],
        )
        if matched:
            strengths.append(f"필수 기술 일치: {', '.join(matched)}")
        if missing:
            concerns.append(f"확인되지 않은 필수 기술: {', '.join(missing)}")

    if "preferredSkillMatch" in weights and position and position.preferred_skills:
        score, matched, _ = _ratio(position.preferred_skills, actual_skills)
        details["preferredSkillMatch"] = ScoreDetail(
            score=score,
            weight=weights["preferredSkillMatch"],
            evidence=[f"일치: {', '.join(matched) or '없음'}"],
        )

    if "roleMatch" in weights and position and applicant.applied_role:
        score = 100.0 if _normalize(position.role) == _normalize(applicant.applied_role) else 0.0
        details["roleMatch"] = ScoreDetail(
            score=score,
            weight=weights["roleMatch"],
            evidence=[f"지원 역할={applicant.applied_role}, 모집 역할={position.role}"],
        )

    if "experienceMatch" in weights and applicant.experiences:
        months = sum(item.duration_months or 0 for item in applicant.experiences)
        score = min(100.0, 40 + len(applicant.experiences) * 15 + min(months, 36) / 36 * 30)
        details["experienceMatch"] = ScoreDetail(
            score=score,
            weight=weights["experienceMatch"],
            evidence=[f"관련 경험 {len(applicant.experiences)}건, 명시된 기간 {months}개월"],
        )

    availability_evidence: list[str] = []
    availability_checks: list[float] = []
    target = dataset.target
    if target.expected_weekly_hours is not None and applicant.available_weekly_hours is not None:
        expected = target.expected_weekly_hours
        available = applicant.available_weekly_hours
        availability_checks.append(100.0 if expected == 0 else min(100, available / expected * 100))
        availability_evidence.append(f"주당 가능 {available}시간 / 요구 {expected}시간")
    if target.activity_method and applicant.preferred_activity_method:
        method_matches = _normalize(target.activity_method) == _normalize(
            applicant.preferred_activity_method
        )
        availability_checks.append(100.0 if method_matches else 0.0)
        availability_evidence.append("활동 방식 일치" if method_matches else "활동 방식 불일치")
    if target.activity_region and applicant.activity_region:
        region_matches = _normalize(target.activity_region) == _normalize(applicant.activity_region)
        availability_checks.append(100.0 if region_matches else 0.0)
        availability_evidence.append("활동 지역 일치" if region_matches else "활동 지역 불일치")
    if "availabilityMatch" in weights and availability_checks:
        details["availabilityMatch"] = ScoreDetail(
            score=sum(availability_checks) / len(availability_checks),
            weight=weights["availabilityMatch"],
            evidence=availability_evidence,
        )

    if "motivationScore" in weights and applicant.motivation and applicant.motivation.strip():
        details["motivationScore"] = ScoreDetail(
            score=_text_score(applicant.motivation),
            weight=weights["motivationScore"],
            evidence=[f"지원 동기 {len(applicant.motivation.strip())}자"],
        )

    evaluated_answers = [a for a in applicant.answers if a.evaluation_score is not None]
    if "interviewScore" in weights and evaluated_answers:
        confidences = [a.evaluation_confidence or 0.5 for a in evaluated_answers]
        weighted_sum = sum(
            (a.evaluation_score or 0) * confidence
            for a, confidence in zip(evaluated_answers, confidences, strict=True)
        )
        interview_score = weighted_sum / sum(confidences)
        details["interviewScore"] = ScoreDetail(
            score=interview_score,
            weight=weights["interviewScore"],
            evidence=[f"AI 평가가 완료된 답변 {len(evaluated_answers)}/{len(applicant.answers)}건"],
        )
    elif "interviewScore" in weights and applicant.answers:
        answered = [answer for answer in applicant.answers if len(answer.answer.strip()) >= 30]
        details["interviewScore"] = ScoreDetail(
            score=len(answered) / len(applicant.answers) * 100,
            weight=weights["interviewScore"],
            evidence=[
                "AI 평가 점수 없음",
                f"30자 이상 답변 {len(answered)}/{len(applicant.answers)}건",
            ],
        )
        concerns.append("인터뷰 내용에 대한 AI 또는 사람의 정성 평가가 필요함")

    total_weight = sum(detail.weight for detail in details.values())
    final_score = (
        sum(detail.score * detail.weight for detail in details.values()) / total_weight
        if total_weight
        else 0.0
    )
    confidence = min(1.0, total_weight / sum(weights.values()))

    if confidence < confidence_threshold:
        recommendation = "INSUFFICIENT_DATA"
    else:
        recommendation = _recommendation(final_score)

    return ApplicantRecommendation(
        application_id=applicant.application_id,
        user_id=applicant.user_id,
        profile_id=applicant.profile_id,
        nickname=applicant.nickname,
        final_score=round(final_score, 2),
        recommendation=recommendation,
        confidence=round(confidence, 2),
        score_details=details,
        strengths=strengths,
        concerns=concerns,
        requires_human_review=confidence < confidence_threshold or bool(concerns),
    )


def analyze_applicants(dataset: ApplicantDataset) -> RecommendationResult:
    recommendations = [_analyze_applicant(dataset, applicant) for applicant in dataset.applicants]
    recommendations.sort(key=lambda item: item.final_score, reverse=True)
    return RecommendationResult(
        target_id=dataset.target.target_id,
        target_type=dataset.target.target_type,
        recommendations=recommendations,
        analyzed_at=datetime.now(UTC),
    )


def build_ranking_save_request(
    result: RecommendationResult,
    calculation_id: str,
) -> RankingSaveRequest | None:
    rankings: list[RankingSaveItem] = []
    saveable = [item for item in result.recommendations if item.application_id is not None]
    for rank, recommendation in enumerate(saveable, start=1):
        application_id = recommendation.application_id
        assert application_id is not None
        if recommendation.review_summary:
            reason_summary = recommendation.review_summary
        else:
            reason_parts = [f"판정: {recommendation.recommendation}"]
            if recommendation.strengths:
                reason_parts.append(f"강점: {', '.join(recommendation.strengths)}")
            if recommendation.concerns:
                reason_parts.append(f"검토사항: {', '.join(recommendation.concerns)}")
            reason_parts.append(f"신뢰도: {recommendation.confidence:.2f}")
            reason_summary = " | ".join(reason_parts)
        rankings.append(
            RankingSaveItem(
                application_id=application_id,
                applicant_user_id=recommendation.user_id,
                score=recommendation.final_score,
                rank_position=rank,
                reason_summary=reason_summary[:5000],
            )
        )

    if not rankings:
        return None
    return RankingSaveRequest(
        target_type=result.target_type,
        target_id=result.target_id,
        model_version=result.analysis_version,
        calculation_id=calculation_id,
        calculated_at=result.analyzed_at,
        rankings=rankings,
    )
