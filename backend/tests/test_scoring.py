"""Tests for SkillProof Evidence Scoring Engine."""
import pytest
from app.services.scoring import (
    score_commit_consistency,
    score_project_complexity,
    score_readme_quality,
    score_recent_activity,
    score_community_signal,
    compute_project_score,
    compute_student_score,
)


def test_empty_commit_consistency():
    score, expl = score_commit_consistency([], 0)
    assert score == 0.0
    assert "No commits" in expl


def test_consistent_commit_timeline():
    timeline = [
        {"month": "2025-01", "count": 10},
        {"month": "2025-02", "count": 12},
        {"month": "2025-03", "count": 15},
        {"month": "2025-04", "count": 8},
        {"month": "2025-05", "count": 20},
    ]
    score, expl = score_commit_consistency(timeline, 65)
    assert score > 20.0
    assert "active months" in expl


def test_project_complexity_multi_language():
    languages = {"Python": 60000, "JavaScript": 20000, "HTML": 5000}
    score, expl = score_project_complexity(languages, file_count=45, repo_size_kb=1500)
    assert score >= 15.0
    assert "language" in expl


def test_readme_quality():
    readme_good = """# My Project
## Features
- Fast API integration
- Secure authentication

## Installation
```bash
pip install -r requirements.txt
```

## Usage
Run the app using uvicorn.

## Contributing
Submit PRs!

## License
MIT
"""
    # Note: signature is score_readme_quality(readme_length: int, readme_content: str = "")
    score, expl = score_readme_quality(len(readme_good), readme_good)
    assert score >= 12.0
    assert "quality markers found" in expl


def test_anti_gaming_burst_penalty():
    timeline = [{"month": "2026-01", "count": 80}]
    repo_data = {
        "name": "cheat-repo",
        "commit_timeline": timeline,
        "commit_count": 80,
        "languages": {"Python": 10000},
        "file_count": 5,
        "repo_size_kb": 200,
        "readme_length": 50,
        "readme_content": "# Cheat",
        "last_commit_date": "2026-01-05T00:00:00Z",
        "star_count": 0,
        "is_fork": False,
        "has_original_commits": True,
        "anti_gaming_flags": ["Single day commit dump detected"],
    }
    result = compute_project_score(repo_data)
    assert any("Single day" in w for w in result["warnings"])
    assert result["penalty"] >= 15.0


def test_anti_gaming_bare_fork():
    repo_data = {
        "name": "forked-repo",
        "commit_timeline": [{"month": "2025-01", "count": 10}],
        "commit_count": 10,
        "languages": {"Python": 10000},
        "file_count": 5,
        "repo_size_kb": 200,
        "readme_length": 100,
        "readme_content": "# Forked",
        "last_commit_date": "2025-01-05T00:00:00Z",
        "star_count": 0,
        "is_fork": True,
        "has_original_commits": False,
        "anti_gaming_flags": ["Fork with no original commits"],
    }
    result = compute_project_score(repo_data)
    assert any("no original commits" in w.lower() for w in result["warnings"])
    assert result["penalty"] >= 30.0


def test_compute_student_score():
    projects = [
        {"total": 80.0, "commit_consistency": 25.0, "project_complexity": 20.0,
         "readme_quality": 18.0, "recent_activity": 12.0, "warnings": []},
        {"total": 60.0, "commit_consistency": 18.0, "project_complexity": 15.0,
         "readme_quality": 15.0, "recent_activity": 10.0, "warnings": []},
    ]
    student_score = compute_student_score(projects)
    assert student_score["total"] > 60.0
    assert student_score["project_count"] == 2
    assert student_score["best_project_score"] == 80.0
