"""SkillProof - SQLAlchemy Models."""
from sqlalchemy import (
    Column, Integer, String, Float, Text, Boolean, DateTime, ForeignKey, JSON
)
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from app.database import Base


class Student(Base):
    __tablename__ = "students"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    email = Column(String(200), unique=True, nullable=False)
    github_username = Column(String(100), unique=True, nullable=True)
    bio = Column(Text, default="")
    avatar_url = Column(String(500), default="")
    evidence_score = Column(Float, default=0.0)
    score_breakdown = Column(JSON, default=dict)  # detailed score explanation
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))

    projects = relationship("Project", back_populates="student", cascade="all, delete-orphan")
    skills = relationship("Skill", back_populates="student", cascade="all, delete-orphan")


class Project(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False)
    github_repo_url = Column(String(500), nullable=False)
    name = Column(String(200), nullable=False)
    description = Column(Text, default="")
    languages = Column(JSON, default=dict)  # {"Python": 45000, "JS": 12000}
    topics = Column(JSON, default=list)
    commit_count = Column(Integer, default=0)
    first_commit_date = Column(String(50), default="")
    last_commit_date = Column(String(50), default="")
    commit_timeline = Column(JSON, default=list)  # [{month: "2024-01", count: 12}, ...]
    readme_content = Column(Text, default="")
    readme_length = Column(Integer, default=0)
    is_fork = Column(Boolean, default=False)
    has_original_commits = Column(Boolean, default=True)
    star_count = Column(Integer, default=0)
    file_count = Column(Integer, default=0)
    repo_size_kb = Column(Integer, default=0)
    is_public = Column(Boolean, default=True)  # privacy control
    ai_summary = Column(Text, default="")  # AI-generated summary
    ai_skills = Column(JSON, default=list)  # AI-suggested skills
    evidence_score = Column(Float, default=0.0)
    score_breakdown = Column(JSON, default=dict)
    anti_gaming_flags = Column(JSON, default=list)  # list of warning flags
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    student = relationship("Student", back_populates="projects")
    feedback = relationship("MentorFeedback", back_populates="project", cascade="all, delete-orphan")


class Skill(Base):
    __tablename__ = "skills"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False)
    name = Column(String(100), nullable=False)
    level = Column(String(50), default="beginner")  # beginner, intermediate, advanced
    source = Column(String(50), default="ai-suggested")  # ai-suggested, verified
    verified_by = Column(String(200), default="")  # mentor name who verified
    verified_at = Column(DateTime, nullable=True)
    evidence_project_ids = Column(JSON, default=list)  # project IDs backing this skill
    monthly_activity = Column(JSON, default=list)  # [{month: "2024-01", commits: 5}, ...]
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    student = relationship("Student", back_populates="skills")


class MentorFeedback(Base):
    __tablename__ = "mentor_feedback"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    mentor_name = Column(String(200), nullable=False)
    mentor_email = Column(String(200), default="")
    rating = Column(Integer, nullable=False)  # 1-5
    strengths = Column(Text, default="")
    improvements = Column(Text, default="")
    comments = Column(Text, default="")
    skills_verified = Column(JSON, default=list)  # skill names approved by mentor
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    project = relationship("Project", back_populates="feedback")
