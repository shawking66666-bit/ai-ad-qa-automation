from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator


AssetType = Literal["video", "image", "script"]
EvaluationStatus = Literal["completed", "partial", "human_review_required"]
DimensionStatus = Literal["evaluated", "partial", "not_applicable"]
Priority = Literal["P0", "P1", "P2"]
EvidenceSource = Literal["video_frame", "image", "text_span", "user_input"]


class DimensionScore(BaseModel):
    dimension: str = Field(min_length=1)
    label: str = Field(min_length=1)
    score: float = Field(ge=0, le=10)
    max_score: float = Field(default=10, gt=0)
    status: DimensionStatus
    reason: str = Field(min_length=1)


class EvidenceItem(BaseModel):
    id: str = Field(min_length=1)
    source_type: EvidenceSource
    location: str = Field(min_length=1)
    dimension: str = Field(min_length=1)
    finding: str = Field(min_length=1)
    confidence: float = Field(ge=0, le=1)


class IssueItem(BaseModel):
    priority: Priority
    dimension: str = Field(min_length=1)
    problem: str = Field(min_length=1)
    impact: str = Field(min_length=1)
    evidence_refs: list[str] = Field(default_factory=list)
    suggestion: str = Field(min_length=1)


class SuggestionItem(BaseModel):
    priority: Priority
    action: str = Field(min_length=1)
    expected_effect: str = Field(min_length=1)
    evidence_refs: list[str] = Field(default_factory=list)


class RunSummary(BaseModel):
    steps: int = Field(default=0, ge=0)
    completed_actions: list[str] = Field(default_factory=list)
    supplementary_frames_used: bool = False
    retry_count: int = Field(default=0, ge=0)
    stop_reason: str = "not_recorded"


class EvaluationRequest(BaseModel):
    asset_type: AssetType
    profile: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    dimensions: list[DimensionScore]
    evidence: list[EvidenceItem] = Field(default_factory=list)
    issues: list[IssueItem] = Field(default_factory=list)
    strengths: list[str] = Field(default_factory=list)
    suggestions: list[SuggestionItem] = Field(default_factory=list)
    missing_information: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0, le=1)
    conflicting_core_evidence: bool = False
    human_review_required: bool = False
    human_review_reason: str | None = None
    run_summary: RunSummary = Field(default_factory=RunSummary)
    technical_details: dict = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_evidence_references(self) -> "EvaluationRequest":
        known_ids = {item.id for item in self.evidence}
        referenced_ids = {
            reference
            for item in [*self.issues, *self.suggestions]
            for reference in item.evidence_refs
        }
        unknown_ids = sorted(referenced_ids - known_ids)
        if unknown_ids:
            raise ValueError(f"unknown evidence references: {unknown_ids}")
        return self


class EvaluationResult(BaseModel):
    asset_type: AssetType
    profile: str
    status: EvaluationStatus
    overall_score: int = Field(ge=0, le=100)
    summary: str
    dimensions: list[DimensionScore]
    evidence: list[EvidenceItem]
    issues: list[IssueItem]
    strengths: list[str]
    suggestions: list[SuggestionItem]
    missing_information: list[str]
    confidence: float = Field(ge=0, le=1)
    human_review_required: bool
    human_review_reason: str | None
    run_summary: RunSummary


def calculate_overall_score(dimensions: list[DimensionScore]) -> int:
    applicable = [item for item in dimensions if item.status != "not_applicable"]
    if not applicable:
        return 0
    percentages = [item.score / item.max_score * 100 for item in applicable]
    return int(round(sum(percentages) / len(percentages)))


def normalize_evaluation(request: EvaluationRequest) -> EvaluationResult:
    requires_review = (
        request.human_review_required
        or request.conflicting_core_evidence
        or request.confidence < 0.5
    )
    if requires_review:
        status: EvaluationStatus = "human_review_required"
    elif request.missing_information or any(
        item.status == "partial" for item in request.dimensions
    ):
        status = "partial"
    else:
        status = "completed"

    review_reason = request.human_review_reason
    if request.conflicting_core_evidence and not review_reason:
        review_reason = "核心证据存在冲突"
    elif request.confidence < 0.5 and not review_reason:
        review_reason = "整体评估置信度过低"

    return EvaluationResult(
        asset_type=request.asset_type,
        profile=request.profile,
        status=status,
        overall_score=calculate_overall_score(request.dimensions),
        summary=request.summary,
        dimensions=request.dimensions,
        evidence=request.evidence,
        issues=request.issues,
        strengths=request.strengths,
        suggestions=request.suggestions,
        missing_information=request.missing_information,
        confidence=request.confidence,
        human_review_required=requires_review,
        human_review_reason=review_reason,
        run_summary=request.run_summary,
    )
