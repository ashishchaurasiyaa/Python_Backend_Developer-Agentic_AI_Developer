"""Milestone 1 — ReviewState + Pydantic issue models."""
from typing import TypedDict, Literal
from pydantic import BaseModel, Field


class SecurityIssue(BaseModel):
    severity: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
    file: str
    line: int
    description: str
    suggestion: str
    owasp_category: str | None = None


class PerformanceIssue(BaseModel):
    type: Literal["n+1", "missing_index", "sync_in_async", "blocking_io", "inefficient_loop"]
    file: str
    line: int
    impact: str
    suggestion: str


class StyleIssue(BaseModel):
    rule: str
    file: str
    line: int
    message: str
    autofix: str | None = None


class SecurityReviewResult(BaseModel):
    issues: list[SecurityIssue] = Field(default_factory=list)
    summary: str
    cost_usd: float = 0.0


class PerformanceReviewResult(BaseModel):
    issues: list[PerformanceIssue] = Field(default_factory=list)
    summary: str
    cost_usd: float = 0.0


class StyleReviewResult(BaseModel):
    issues: list[StyleIssue] = Field(default_factory=list)
    summary: str
    cost_usd: float = 0.0


class ReviewState(TypedDict):
    pr_id: int
    repo: str
    diff: str
    files_changed: list[str]
    security_issues: list[SecurityIssue]
    performance_issues: list[PerformanceIssue]
    style_issues: list[StyleIssue]
    decision: Literal["approve", "request_changes", "human_review"]
    review_comment: str
    cost_usd: float
