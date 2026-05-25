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
    env_file_path: Path | None = None
    doc_a_type: str | None = None
    doc_b_type: str | None = None
    dry_run: bool = False
    no_cloud: bool = False
    no_kuzu: bool = False
    max_candidates: int = 50
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


class CandidateFinding(BaseModel):
    candidate_id: str
    candidate_key: str
    finding_type: FindingType
    subject: str
    parameter: str
    evidence_a_id: str | None = None
    evidence_b_id: str | None = None
    generation_method: str
    deterministic_reason: str
    status: str = "pending"
    identity_strength: IdentityStrength = "weak"
    deterministic_discrepancy: bool = False
    plausibility_notes: list[str] = Field(default_factory=list)


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
