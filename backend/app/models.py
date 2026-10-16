"""Pydantic models shared by the engine, the API and the narrative validator."""
from __future__ import annotations

from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, Field

Quality = Literal["usable", "partial", "cloudy", "none", "n/a"]
Confidence = Literal["high", "medium", "low"]
Severity = Literal["high", "medium", "low"]
Outcome = Literal["auto_dismissed", "area_alert", "field_case", "unexplained", "watch", "resolved"]
Stance = Literal["for", "against", "neutral"]


class Evidence(BaseModel):
    id: str
    tool: str
    title: str
    finding: str
    data: dict[str, Any] = Field(default_factory=dict)
    as_of: date
    quality: Quality
    source: str
    visual: dict[str, Any] | None = None
    stance: Stance = "neutral"


class Line(BaseModel):
    text: str
    evidence_ids: list[str] = Field(default_factory=list)


class HypothesisResult(BaseModel):
    id: str
    name: str
    stage: Literal[1, 2, 3]
    score: float
    confidence: Confidence
    status: Literal["leading", "possible", "ruled_out", "fired"]
    for_lines: list[Line] = Field(default_factory=list)
    against_lines: list[Line] = Field(default_factory=list)
    unknown_lines: list[Line] = Field(default_factory=list)
    brief: str = ""  # one line used when the card is collapsed


class StageOutcome(BaseModel):
    kind: Literal["auto_dismissed", "area_alert", "watch"]
    hypothesis_id: str
    title: str
    reason: str
    evidence_ids: list[str]
    confirm_with: str | None = None


class CheckOutcome(BaseModel):
    key: str
    label: str
    then: str
    supports: list[str]
    against: list[str]


class CandidateCheck(BaseModel):
    check_id: str
    short: str
    label: str
    cost_min: int
    split: float
    score: float
    chosen: bool = False
    note: str = ""


class NextCheck(BaseModel):
    check_id: str
    label: str
    cost_min: int
    outcomes: list[CheckOutcome]
    hypotheses: list[str]  # the two being separated (one when a single cause is still live)
    candidates: list[CandidateCheck]
    reason: str | None = None  # why the recommendation changed after an officer finding


class CaseFileLine(BaseModel):
    text: str
    evidence_ids: list[str] = Field(default_factory=list)


class HypothesisExplainer(BaseModel):
    id: str
    why: list[CaseFileLine]


class CaseFile(BaseModel):
    summary: CaseFileLine
    hypotheses: list[HypothesisExplainer]
    next_check_explainer: CaseFileLine | None = None
    limits: str


class Headline(BaseModel):
    delta: float
    zone: str
    zone_label: str
    date: date
    quality: Quality
    baseline_label: str


Movement = Literal["more_likely", "less_likely", "ruled_out", "newly_considered", "unchanged"]


class CauseMove(BaseModel):
    """How one cause moved because of the latest officer finding."""
    id: str
    name: str
    before_score: float
    after_score: float
    before_status: str
    after_status: str
    before_rank: int
    after_rank: int
    movement: Movement
    reason: str
    evidence_ids: list[str] = Field(default_factory=list)


class InvestigationUpdate(BaseModel):
    """The latest finding and what it changed. The case stays open: nothing here confirms a cause."""
    check_id: str
    check_label: str
    outcome_key: str
    outcome_label: str
    note: str
    recorded_at: str
    evidence_id: str
    findings: int  # how many findings the case has had so far
    moves: list[CauseMove]


class FieldInfo(BaseModel):
    id: str
    name: str
    klass: str
    class_label: str
    area_ha: float
    analysis_pixels: int
    mode: str = "zoned"


class CaseResult(BaseModel):
    case_id: str
    field: FieldInfo
    alert_date: date
    as_of: date
    banner: str = ""
    outcome: Outcome
    severity: Severity | None = None
    headline: Headline | None = None
    evidence: list[Evidence]
    hypotheses: list[HypothesisResult]
    stage_outcome: StageOutcome | None = None
    next_check: NextCheck | None = None
    visit_checklist: list[str] = Field(default_factory=list)
    narrative: CaseFile | None = None
    narrative_source: Literal["gemini", "template"] | None = None
    update: InvestigationUpdate | None = None
    check_context: dict[str, Any] = Field(default_factory=dict)  # what decides which checks apply, kept for replays
    limits: str = ""


class FindingRequest(BaseModel):
    check_id: str
    outcome: str
    note: str = Field(default="", max_length=600)
