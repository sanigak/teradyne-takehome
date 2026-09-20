from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Enrichment(StrictModel):
    domain: str
    priority: str | None
    decisions: list[str]
    action_items: list[str]


class Citation(StrictModel):
    chunk_id: str
    quote: str = Field(min_length=1, pattern=r"\S")


class Claim(StrictModel):
    text: str = Field(min_length=1, pattern=r"\S")
    citations: list[Citation] = Field(min_length=1)


class SourceReference(StrictModel):
    chunk_id: str
    quote_id: str


class DraftClaim(StrictModel):
    text: str = Field(min_length=1, pattern=r"\S")
    citations: list[SourceReference] = Field(min_length=1)


class DraftAnswer(StrictModel):
    status: Literal["answered", "partial", "needs_routing"]
    claims: list[DraftClaim]
    missing_information: str
    conflicting_evidence: bool
    relevant_chunk_ids: list[str]


class ClaimCheck(StrictModel):
    claim_index: int
    supported: bool


class ComponentCoverage(StrictModel):
    requested_component: str = Field(min_length=1, description="One information component explicitly requested by the question; do not add adjacent background or unrequested contacts.")
    provided_value: str | None = Field(description="The substantive requested value or explanation actually provided by the sources. Use null when it is unknown, absent, pending, or not approved; a sentence saying the value is missing is not a value. For an explicit yes/no question, an established negative is a valid answer.")
    evidence_state: Literal["present", "missing", "conflicting"]
    supporting_chunk_ids: list[str]

    @model_validator(mode="after")
    def consistent_coverage(self):
        if self.evidence_state == "missing" and self.provided_value is not None:
            raise ValueError("Missing components must have provided_value=null.")
        if self.evidence_state != "missing" and (not self.provided_value or not self.provided_value.strip()):
            raise ValueError("Present/conflicting components must state the supplied value or alternatives.")
        if self.evidence_state != "missing" and not self.supporting_chunk_ids:
            raise ValueError("Present/conflicting components require source references.")
        return self


class SupportCheck(StrictModel):
    checks: list[ClaimCheck]


class CoverageAssessment(StrictModel):
    coverage: list[ComponentCoverage] = Field(min_length=1)
    relevant_chunk_ids: list[str]


class Evidence(StrictModel):
    chunk_id: str
    document_id: str
    filename: str
    title: str
    author: str | None
    attendees: list[str]
    date: str | None
    domain: str
    priority: str | None
    locator: str
    text: str


class Routing(StrictModel):
    recipient: str
    reason: str
    draft_question: str
    evidence_ids: list[str]


class QueryResult(StrictModel):
    query_id: str
    question: str
    status: Literal["answered", "partial", "needs_routing"]
    claims: list[Claim]
    evidence: list[Evidence]
    routing: list[Routing]
    message: str
    created_at: str


class Question(StrictModel):
    question: str = Field(min_length=3, max_length=3000)

    @model_validator(mode="after")
    def nonblank(self):
        self.question = self.question.strip()
        if len(self.question) < 3:
            raise ValueError("Enter a question with at least three characters.")
        return self


class Feedback(StrictModel):
    query_id: str
    kind: Literal["accepted", "rejected", "corrected"]
    comment: str = Field(default="", max_length=10000)

    @model_validator(mode="after")
    def comment_required(self):
        self.comment = self.comment.strip()
        if self.kind != "accepted" and not self.comment:
            raise ValueError("Rejections and corrections require a comment.")
        return self


class ReviewUpdate(StrictModel):
    status: Literal["open", "resolved"]
    resolution_note: str = Field(default="", max_length=10000)

    @model_validator(mode="after")
    def resolution_required(self):
        if self.status == "resolved" and not self.resolution_note.strip():
            raise ValueError("A resolution note is required.")
        return self


class OutboxDraft(StrictModel):
    query_id: str
    recipient: str = Field(min_length=1, max_length=500)
    subject: str = Field(min_length=1, max_length=500)
    body: str = Field(min_length=1, max_length=10000)
    evidence_ids: list[str]

    @model_validator(mode="after")
    def nonblank_fields(self):
        for name in ("recipient", "subject", "body"):
            value = getattr(self, name).strip()
            if not value:
                raise ValueError(f"{name} must not be blank.")
            setattr(self, name, value)
        return self
