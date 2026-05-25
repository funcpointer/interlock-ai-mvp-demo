from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

SCHEMA_VERSION = "interlock_mvp.v1"

ReviewMode = Literal["version", "cross_doc"]
FindingType = Literal[
    "value_mismatch",
    "missing_item",
    "reference_conflict",
    "coverage_warning",
    "needs_engineer_review",
]
Severity = Literal["review_required", "possible_issue", "informational"]
Confidence = Literal["high", "medium", "low"]
IdentityStrength = Literal["strong", "medium", "weak"]
TriageSeverity = Literal["high", "medium", "low", "info"]
AlignmentStatus = Literal[
    "matched",
    "probable_match",
    "ambiguous",
    "unmatched_a",
    "unmatched_b",
    "conflict",
    "equivalent",
    "needs_review",
]


class ReviewRequest(BaseModel):
    doc_a_path: Path
    doc_b_path: Path
    mode: ReviewMode
    out_dir: Path
    authority_config_path: Path | None = None
    domain_glossary_path: Path | None = None
    env_file_path: Path | None = None
    doc_a_type: str | None = None
    doc_b_type: str | None = None
    dry_run: bool = False
    no_cloud: bool = False
    no_kuzu: bool = False
    max_vlm_pages: int = 10
    max_cost_usd: float = 5.0


class ReviewResult(BaseModel):
    run_id: str
    out_dir: Path
    findings_count: int
    review_required_count: int
    coverage_warning_count: int
    report_path: Path
    findings_path: Path
    metrics_path: Path
    warnings: list[str] = Field(default_factory=list)


class DocumentRecord(BaseModel):
    doc_id: str
    label: str
    path: str
    sha256: str
    page_count: int
    doc_type: str
    mode_role: str


class PageRecord(BaseModel):
    page_id: str
    doc_id: str
    page_num: int
    width: float
    height: float
    text_char_count: int
    extraction_status: str
    page_image_path: str


class AnnotationRecord(BaseModel):
    annotation_id: str
    doc_id: str
    page: int
    bbox: list[float]
    annotation_type: str
    annotation_comment: str
    highlighted_text: str
    raw: dict[str, Any] = Field(default_factory=dict)


class RegionRecord(BaseModel):
    region_id: str
    doc_id: str
    page: int
    bbox: list[float]
    text: str
    kind: str
    crop_path: str
    annotation_ids: list[str] = Field(default_factory=list)


class EvidenceItem(BaseModel):
    evidence_id: str
    doc_id: str
    page: int
    bbox: list[float]
    region_id: str
    kind: Literal[
        "equipment_id",
        "parameter_value",
        "reference",
        "annotation",
        "coverage_warning",
    ]
    subject: str
    parameter: str
    value: str
    unit: str
    raw_text: str
    normalized_text: str
    normalized_value: str
    confidence: Confidence
    source_method: str
    crop_path: str
    context_id: str = ""
    context_confidence: Confidence = "low"


class EvidenceCitation(BaseModel):
    evidence_id: str
    doc_id: str
    page: int
    bbox: list[float]
    quote: str
    crop_path: str
    value: str = ""
    unit: str = ""


class Finding(BaseModel):
    finding_id: str
    mode: ReviewMode
    finding_type: FindingType
    severity: Severity
    confidence: Confidence
    subject: str
    parameter: str
    summary: str
    authoritative_side: str
    authority_basis: str
    authority_confidence: float
    evidence_a: EvidenceCitation | None = None
    evidence_b: EvidenceCitation | None = None
    plausibility_notes: list[str] = Field(default_factory=list)
    verifier_notes: str
    alignment_id: str | None = None
    comparison_id: str | None = None
    absence_id: str | None = None
    context_support_id: str | None = None
    context_support_supports: bool | None = None
    context_support_confidence: Confidence | None = None
    context_support_summary: str = ""
    context_support_signal_types: list[str] = Field(default_factory=list)
    context_support_context_ids: list[str] = Field(default_factory=list)
    context_support_search_ids: list[str] = Field(default_factory=list)
    model_review_status: str = "not_run"
    model_review_model: str = ""
    model_review_supports: bool | None = None
    model_review_summary: str = ""
    model_review_cautions: list[str] = Field(default_factory=list)


class ContextNode(BaseModel):
    context_id: str
    doc_id: str
    canonical_label: str
    raw_labels: list[str] = Field(default_factory=list)
    kind: str
    page_span: list[int]
    region_ids: list[str] = Field(default_factory=list)
    confidence: Confidence


class SubjectNode(BaseModel):
    subject_id: str
    doc_id: str
    canonical_label: str
    raw_labels: list[str] = Field(default_factory=list)
    kind: str
    context_ids: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    confidence: Confidence


class ClaimNode(BaseModel):
    claim_id: str
    doc_id: str
    context_id: str
    subject_id: str
    parameter: str
    value: str
    unit: str
    raw_text: str
    evidence_ids: list[str] = Field(default_factory=list)
    confidence: Confidence


class DiffEdge(BaseModel):
    diff_id: str
    diff_type: FindingType
    a_node_id: str | None = None
    b_node_id: str | None = None
    alignment_status: AlignmentStatus
    subject: str
    parameter: str
    rationale: str
    evidence_ids: list[str] = Field(default_factory=list)
    plausibility_notes: list[str] = Field(default_factory=list)
    identity_strength: IdentityStrength = "weak"
    deterministic_discrepancy: bool = False


class DocumentGraph(BaseModel):
    doc_id: str
    contexts: list[ContextNode] = Field(default_factory=list)
    subjects: list[SubjectNode] = Field(default_factory=list)
    claims: list[ClaimNode] = Field(default_factory=list)


class DiffGraph(BaseModel):
    edges: list[DiffEdge] = Field(default_factory=list)


class AlignmentDecision(BaseModel):
    alignment_id: str
    diff_id: str
    a_claim_id: str
    b_claim_id: str
    subject_method: str
    parameter_method: str
    context_method: str
    confidence: Confidence
    accepted: bool
    rationale: str
    rejected_b_claim_ids: list[str] = Field(default_factory=list)


class ComparisonDecision(BaseModel):
    comparison_id: str
    diff_id: str
    alignment_id: str | None = None
    comparison_type: FindingType | Literal["equivalent"]
    unit_method: str
    plausibility_notes: list[str] = Field(default_factory=list)
    deterministic: bool
    verifier_status: str
    rationale: str


class AbsenceSearch(BaseModel):
    absence_id: str
    diff_id: str
    a_subject_id: str | None = None
    a_claim_id: str | None = None
    searched_doc_id: str
    searched_context_ids: list[str] = Field(default_factory=list)
    searched_parameters: list[str] = Field(default_factory=list)
    query_terms: list[str] = Field(default_factory=list)
    candidate_ids_considered: list[str] = Field(default_factory=list)
    rejected_candidate_ids: list[str] = Field(default_factory=list)
    coverage_status: str
    confidence: Confidence
    rationale: str


class ContextSupport(BaseModel):
    support_id: str
    diff_id: str
    supports: bool
    confidence: Confidence
    signal_types: list[str] = Field(default_factory=list)
    context_ids: list[str] = Field(default_factory=list)
    search_ids: list[str] = Field(default_factory=list)
    summary: str
    downgrade_reasons: list[str] = Field(default_factory=list)


class ReasoningGraph(BaseModel):
    alignments: list[AlignmentDecision] = Field(default_factory=list)
    comparisons: list[ComparisonDecision] = Field(default_factory=list)
    absence_searches: list[AbsenceSearch] = Field(default_factory=list)
    context_supports: list[ContextSupport] = Field(default_factory=list)


class ContextRoom(BaseModel):
    room_id: str
    doc_id: str
    context_id: str
    canonical_label: str
    kind: str
    page_span: list[int] = Field(default_factory=list)
    region_ids: list[str] = Field(default_factory=list)
    subject_ids: list[str] = Field(default_factory=list)
    claim_ids: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    finding_ids: list[str] = Field(default_factory=list)
    neighboring_room_ids: list[str] = Field(default_factory=list)
    memory_path: str
    summary: str
    salience_score: int


class ContextTrail(BaseModel):
    trail_id: str
    name: str
    room_ids: list[str] = Field(default_factory=list)
    finding_ids: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    rationale: str


class ContextMemory(BaseModel):
    rooms: list[ContextRoom] = Field(default_factory=list)
    trails: list[ContextTrail] = Field(default_factory=list)


class DecisionSignal(BaseModel):
    signal_id: str
    source: str
    signal_type: str
    supports: bool
    summary: str
    confidence: Confidence
    evidence_ids: list[str] = Field(default_factory=list)
    reasoning_id: str | None = None


class DecisionTrace(BaseModel):
    finding_id: str
    decision: Severity
    finding_type: FindingType
    confidence: Confidence
    why: list[str] = Field(default_factory=list)
    supporting_signals: list[DecisionSignal] = Field(default_factory=list)
    contradicting_signals: list[DecisionSignal] = Field(default_factory=list)
    downgrade_reasons: list[str] = Field(default_factory=list)
    rejected_alternatives: list[str] = Field(default_factory=list)


class TriageIssue(BaseModel):
    issue_id: str
    severity: TriageSeverity
    category: str
    title: str
    summary: str
    evidence: list[str] = Field(default_factory=list)
    metrics: dict[str, Any] = Field(default_factory=dict)
    suggested_next_step: str


class RunTriage(BaseModel):
    run_dir: str
    findings: int
    review_required_findings: int
    coverage_warning_findings: int
    issue_count: int
    issues: list[TriageIssue] = Field(default_factory=list)
    next_actions: list[str] = Field(default_factory=list)


class AuthorityDecision(BaseModel):
    authoritative_side: str
    basis: str
    confidence: float
    doc_a_type: str
    doc_b_type: str
    doc_a_type_confidence: float
    doc_b_type_confidence: float
    warnings: list[str] = Field(default_factory=list)


class ArtifactFile(BaseModel):
    schema_version: str = SCHEMA_VERSION
    records: list[Any] = Field(default_factory=list)
    meta: dict[str, Any] = Field(default_factory=dict)
