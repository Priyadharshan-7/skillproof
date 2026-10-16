"""
Evidence scoring engine for SkillProof.

Produces a score 0-100 with four weighted components:
  - Commit consistency (30%): spread of commits over time
  - Project complexity (25%): languages, file count, size
  - README quality   (20%): length, sections, formatting
  - Recent activity  (25%): recency of last commit

Each component returns 0-100 and a human-readable explanation.
Anti-gaming checks flag suspicious patterns.
"""

from __future__ import annotations
import re
from datetime import datetime, timedelta
from typing import Any


# ── Weights ──────────────────────────────────────────────────────────────────

WEIGHTS = {
    "commit_consistency": 0.30,
    "project_complexity": 0.25,
    "readme_quality": 0.20,
    "recent_activity": 0.25,
}


# ── Component Scorers ───────────────────────────────────────────────────────

def score_commit_consistency(commit_history: list[dict], commit_count: int) -> tuple[float, str]:
    """
    Rewards commits spread across multiple months.
    A single-day dump scores low; steady work over months scores high.
    """
    if commit_count == 0:
        return 0.0, "No commits found."

    active_months = len([m for m in commit_history if m.get("count", 0) > 0])

    if active_months == 0:
        return 5.0, "Commit dates unavailable; minimal score assigned."

    # Score based on how many distinct months have activity
    if active_months >= 12:
        raw = 100
    elif active_months >= 6:
        raw = 70 + (active_months - 6) * 5  # 70-100
    elif active_months >= 3:
        raw = 40 + (active_months - 3) * 10  # 40-70
    else:
        raw = active_months * 15  # 0-30

    # Bonus for steady commit volume (not just 1 commit/month)
    avg_per_month = commit_count / max(active_months, 1)
    if avg_per_month >= 10:
        raw = min(100, raw + 10)
    elif avg_per_month >= 5:
        raw = min(100, raw + 5)

    explanation = (
        f"{commit_count} commits across {active_months} month(s), "
        f"avg {avg_per_month:.1f}/month."
    )
    return min(100.0, float(raw)), explanation


def score_project_complexity(
    languages: dict, file_count: int, repo_size_kb: int
) -> tuple[float, str]:
    """
    Rewards multi-language projects with substantial file counts and size.
    """
    raw = 0.0
    details = []

    # Language diversity (up to 30 pts)
    lang_count = len(languages)
    lang_score = min(30, lang_count * 10)
    raw += lang_score
    details.append(f"{lang_count} language(s)")

    # File count (up to 35 pts)
    if file_count >= 50:
        file_score = 35
    elif file_count >= 20:
        file_score = 20 + (file_count - 20) * 0.5
    elif file_count >= 5:
        file_score = 5 + (file_count - 5) * 1.0
    else:
        file_score = file_count * 1.0
    raw += file_score
    details.append(f"{file_count} files")

    # Repo size (up to 35 pts)
    if repo_size_kb >= 5000:
        size_score = 35
    elif repo_size_kb >= 1000:
        size_score = 20 + (repo_size_kb - 1000) / 250
    elif repo_size_kb >= 100:
        size_score = 5 + (repo_size_kb - 100) / 60
    else:
        size_score = repo_size_kb / 20
    raw += min(35, size_score)
    details.append(f"{repo_size_kb} KB")

    explanation = f"Complexity: {', '.join(details)}."
    return min(100.0, float(raw)), explanation


def score_readme_quality(readme_content: str) -> tuple[float, str]:
    """
    Rewards READMEs with sections, code blocks, length, and images/links.
    """
    if not readme_content or not readme_content.strip():
        return 0.0, "No README found."

    raw = 0.0
    details = []
    text = readme_content.strip()

    # Length (up to 30 pts)
    word_count = len(text.split())
    if word_count >= 500:
        raw += 30
    elif word_count >= 200:
        raw += 20
    elif word_count >= 50:
        raw += 10
    else:
        raw += 5
    details.append(f"{word_count} words")

    # Headings / sections (up to 25 pts)
    headings = len(re.findall(r"^#{1,3}\s", text, re.MULTILINE))
    heading_score = min(25, headings * 5)
    raw += heading_score
    details.append(f"{headings} section(s)")

    # Code blocks (up to 20 pts)
    code_blocks = len(re.findall(r"```", text))
    if code_blocks >= 4:
        raw += 20
    elif code_blocks >= 2:
        raw += 10
    elif code_blocks >= 1:
        raw += 5
    if code_blocks:
        details.append(f"{code_blocks // 2} code block(s)")

    # Links / images (up to 15 pts)
    links = len(re.findall(r"\[.*?\]\(.*?\)", text))
    if links >= 5:
        raw += 15
    elif links >= 2:
        raw += 10
    elif links >= 1:
        raw += 5
    if links:
        details.append(f"{links} link(s)")

    # Has install / usage instructions (up to 10 pts)
    has_install = bool(re.search(r"(install|setup|getting started|usage|how to run)", text, re.IGNORECASE))
    if has_install:
        raw += 10
        details.append("has setup instructions")

    explanation = f"README: {', '.join(details)}."
    return min(100.0, float(raw)), explanation


def score_recent_activity(last_commit_date: datetime | None) -> tuple[float, str]:
    """
    Rewards projects with recent commits.
    Full score for activity in last 30 days, decays over 2 years.
    """
    if last_commit_date is None:
        return 0.0, "No commit dates available."

    now = datetime.utcnow()
    days_ago = (now - last_commit_date).days

    if days_ago < 0:
        days_ago = 0

    if days_ago <= 30:
        raw = 100.0
    elif days_ago <= 90:
        raw = 80.0
    elif days_ago <= 180:
        raw = 60.0
    elif days_ago <= 365:
        raw = 40.0
    elif days_ago <= 730:
        raw = 20.0
    else:
        raw = 5.0

    explanation = f"Last commit {days_ago} day(s) ago."
    return raw, explanation


# ── Anti-Gaming Checks ──────────────────────────────────────────────────────

def check_anti_gaming(
    is_fork: bool,
    has_original_commits: bool,
    commit_history: list[dict],
    commit_count: int,
) -> list[str]:
    """
    Returns a list of warning flags for suspicious patterns.
    """
    flags = []

    # Fork with no original commits
    if is_fork and not has_original_commits:
        flags.append(
            "⚠️ Forked repo with no original commits — may not reflect own work."
        )

    # Single-day commit dump (>80% of commits on one day)
    if commit_count >= 10 and commit_history:
        max_month = max((m.get("count", 0) for m in commit_history), default=0)
        if max_month >= commit_count * 0.8:
            flags.append(
                "⚠️ Most commits concentrated in a single period — possible commit dump."
            )

    # Very low commit count for large repo
    # (suspicious: big repo, almost no commits — likely a bulk import)
    if commit_count <= 2 and len(commit_history) <= 1:
        flags.append(
            "⚠️ Very few commits — project may be a bulk upload rather than iterative work."
        )

    return flags


# ── Main Scorer ─────────────────────────────────────────────────────────────

def compute_evidence_score(project_data: dict[str, Any]) -> dict[str, Any]:
    """
    Compute the full evidence score for a project.

    Args:
        project_data: dict with keys matching Project model fields.

    Returns:
        {
            "total": float,
            "commit_consistency": float,
            "project_complexity": float,
            "readme_quality": float,
            "recent_activity": float,
            "explanation": [str, ...],
            "flags": [str, ...]
        }
    """
    results = {}
    explanations = []

    # 1. Commit consistency
    cc_score, cc_expl = score_commit_consistency(
        project_data.get("commit_history", []),
        project_data.get("commit_count", 0),
    )
    results["commit_consistency"] = round(cc_score, 1)
    explanations.append(f"Commit Consistency ({WEIGHTS['commit_consistency']:.0%}): {cc_expl}")

    # 2. Project complexity
    pc_score, pc_expl = score_project_complexity(
        project_data.get("languages", {}),
        project_data.get("file_count", 0),
        project_data.get("repo_size_kb", 0),
    )
    results["project_complexity"] = round(pc_score, 1)
    explanations.append(f"Project Complexity ({WEIGHTS['project_complexity']:.0%}): {pc_expl}")

    # 3. README quality
    rq_score, rq_expl = score_readme_quality(
        project_data.get("readme_content", ""),
    )
    results["readme_quality"] = round(rq_score, 1)
    explanations.append(f"README Quality ({WEIGHTS['readme_quality']:.0%}): {rq_expl}")

    # 4. Recent activity
    ra_score, ra_expl = score_recent_activity(
        project_data.get("last_commit_date"),
    )
    results["recent_activity"] = round(ra_score, 1)
    explanations.append(f"Recent Activity ({WEIGHTS['recent_activity']:.0%}): {ra_expl}")

    # Weighted total
    total = sum(results[k] * WEIGHTS[k] for k in WEIGHTS)
    results["total"] = round(total, 1)
    results["explanation"] = explanations

    # Anti-gaming
    flags = check_anti_gaming(
        project_data.get("is_fork", False),
        project_data.get("has_original_commits", True),
        project_data.get("commit_history", []),
        project_data.get("commit_count", 0),
    )
    results["flags"] = flags

    # Penalize flagged projects
    if flags:
        penalty = len(flags) * 10
        results["total"] = max(0, round(results["total"] - penalty, 1))
        explanations.append(f"⚠️ Score reduced by {penalty} pts due to {len(flags)} flag(s).")

    return results
