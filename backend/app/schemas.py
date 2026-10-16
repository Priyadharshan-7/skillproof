"""SkillProof - Pydantic schemas for request/response validation."""
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


# ── Student ──────────────────────────────────────────────────────────
class StudentCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    email: str = Field(..., min_length=3, max_length=200)
    github_username: Optional[str] = None
    bio: Optional[str] = ""


class StudentOut(BaseModel):
    id: int
    name: str
    email: str
    github_username: Optional[str]
    bio: str
    avatar_url: str
    evidence_score: float
    score_breakdown: dict
    projects: list = []
    skills: list = []
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class StudentBrief(BaseModel):
    id: int
    name: str
    github_username: Optional[str]
    avatar_url: str
    evidence_score: float
    skills: list = []

    model_config = {"from_attributes": True}


# ── Project ──────────────────────────────────────────────────────────
class ProjectOut(BaseModel):
    id: int
    student_id: int
    github_repo_url: str
    name: str
    description: str
    languages: dict
    topics: list
    commit_count: int
    first_commit_date: str
    last_commit_date: str
    commit_timeline: list
    readme_length: int
    is_fork: bool
    has_original_commits: bool
    star_count: int
    file_count: int
    repo_size_kb: int
    is_public: bool
    ai_summary: str
    ai_skills: list
    evidence_score: float
    score_breakdown: dict
    anti_gaming_flags: list
    feedback: list = []

    model_config = {"from_attributes": True}


class ProjectVisibilityUpdate(BaseModel):
    is_public: bool


# ── GitHub Import ────────────────────────────────────────────────────
class GitHubImportRequest(BaseModel):
    github_username: str = Field(..., min_length=1, max_length=100)


class GitHubRepoImportRequest(BaseModel):
    repo_url: str = Field(..., min_length=1)


# ── Mentor Feedback ──────────────────────────────────────────────────
class MentorFeedbackCreate(BaseModel):
    project_id: int
    mentor_name: str = Field(..., min_length=1, max_length=200)
    mentor_email: Optional[str] = ""
    rating: int = Field(..., ge=1, le=5)
    strengths: str = ""
    improvements: str = ""
    comments: str = ""
    skills_verified: list[str] = []


class MentorFeedbackOut(BaseModel):
    id: int
    project_id: int
    mentor_name: str
    mentor_email: str
    rating: int
    strengths: str
    improvements: str
    comments: str
    skills_verified: list
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


# ── Recruiter Search ─────────────────────────────────────────────────
class RecruiterSearchRequest(BaseModel):
    skill: Optional[str] = None
    min_score: Optional[float] = 0
    sort_by: Optional[str] = "evidence_score"  # evidence_score, name


# ── Score Breakdown ──────────────────────────────────────────────────
class ScoreBreakdown(BaseModel):
    total: float
    commit_consistency: float
    project_complexity: float
    readme_quality: float
    recent_activity: float
    explanation: list[str]
    warnings: list[str]
