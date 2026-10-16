"""SkillProof - Evidence Scoring Engine.

Computes an evidence score (0-100) per project and per student.
All weights and logic are transparent and testable.

Score Components (per project):
  - Commit Consistency (30pts): rewards sustained activity over many months
  - Project Complexity (25pts): languages, file count, repo size
  - README Quality (20pts): length, presence of sections
  - Recent Activity (15pts): commits in the last 6 months
  - Community Signal (10pts): stars, not a bare fork

Anti-gaming penalties are applied after scoring.
"""
from datetime import datetime, timezone
from typing import Optional


def score_commit_consistency(commit_timeline: list[dict], commit_count: int) -> tuple[float, str]:
    """Score based on how consistently the student commits over time.
    
    Max 30 points.
    Rewards: many months with commits, no huge gaps.
    """
    if not commit_timeline or commit_count == 0:
        return 0.0, "No commits found"

    active_months = len(commit_timeline)
    if active_months == 0:
        return 0.0, "No commit activity months"

    # Span of months (first to last)
    try:
        months_sorted = sorted(t["month"] for t in commit_timeline)
        first = datetime.strptime(months_sorted[0], "%Y-%m")
        last = datetime.strptime(months_sorted[-1], "%Y-%m")
        span_months = max(1, (last.year - first.year) * 12 + (last.month - first.month) + 1)
    except (ValueError, IndexError):
        span_months = active_months

    # Consistency ratio: what fraction of the span has commits
    consistency = active_months / span_months if span_months > 0 else 0

    # Base score from commit count (diminishing returns)
    if commit_count >= 100:
        count_score = 15
    elif commit_count >= 50:
        count_score = 12
    elif commit_count >= 20:
        count_score = 9
    elif commit_count >= 10:
        count_score = 6
    elif commit_count >= 5:
        count_score = 4
    else:
        count_score = 2

    # Consistency bonus
    consistency_score = consistency * 15  # up to 15 pts

    total = min(30, count_score + consistency_score)
    explanation = (
        f"Commit consistency: {active_months} active months across {span_months}-month span "
        f"({consistency:.0%} consistency), {commit_count} total commits → {total:.1f}/30"
    )
    return round(total, 1), explanation


def score_project_complexity(languages: dict, file_count: int, repo_size_kb: int) -> tuple[float, str]:
    """Score based on project complexity indicators.
    
    Max 25 points.
    """
    lang_count = len(languages)
    total_bytes = sum(languages.values()) if languages else 0

    # Language diversity (up to 8 pts)
    if lang_count >= 5:
        lang_score = 8
    elif lang_count >= 3:
        lang_score = 6
    elif lang_count >= 2:
        lang_score = 4
    elif lang_count >= 1:
        lang_score = 2
    else:
        lang_score = 0

    # File count (up to 9 pts)
    if file_count >= 50:
        file_score = 9
    elif file_count >= 20:
        file_score = 7
    elif file_count >= 10:
        file_score = 5
    elif file_count >= 5:
        file_score = 3
    else:
        file_score = 1

    # Repo size (up to 8 pts)
    if repo_size_kb >= 5000:
        size_score = 8
    elif repo_size_kb >= 1000:
        size_score = 6
    elif repo_size_kb >= 200:
        size_score = 4
    elif repo_size_kb >= 50:
        size_score = 2
    else:
        size_score = 1

    total = min(25, lang_score + file_score + size_score)
    explanation = (
        f"Complexity: {lang_count} language(s), {file_count} files, "
        f"{repo_size_kb}KB → {total:.1f}/25"
    )
    return round(total, 1), explanation


def score_readme_quality(readme_length: int, readme_content: str = "") -> tuple[float, str]:
    """Score based on README presence and quality.
    
    Max 20 points.
    """
    if readme_length == 0:
        return 0.0, "No README found → 0/20"

    # Length score (up to 10 pts)
    if readme_length >= 3000:
        length_score = 10
    elif readme_length >= 1500:
        length_score = 8
    elif readme_length >= 500:
        length_score = 5
    elif readme_length >= 100:
        length_score = 3
    else:
        length_score = 1

    # Content quality markers (up to 10 pts)
    quality_score = 0
    content_lower = readme_content.lower() if readme_content else ""
    markers = {
        "install": 2,    # installation instructions
        "usage": 2,      # usage guide
        "## ": 2,        # has sections/structure
        "```": 2,        # has code blocks
        "license": 1,    # mentions license
        "contribut": 1,  # contribution guide
    }
    for marker, pts in markers.items():
        if marker in content_lower:
            quality_score += pts

    quality_score = min(10, quality_score)
    total = min(20, length_score + quality_score)
    explanation = (
        f"README: {readme_length} chars, quality markers found → {total:.1f}/20"
    )
    return round(total, 1), explanation


def score_recent_activity(last_commit_date: str) -> tuple[float, str]:
    """Score based on how recent the last commit is.
    
    Max 15 points.
    """
    if not last_commit_date:
        return 0.0, "No commit date available → 0/15"

    try:
        last_dt = datetime.fromisoformat(last_commit_date.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        days_ago = (now - last_dt).days
    except ValueError:
        return 0.0, "Invalid commit date → 0/15"

    if days_ago <= 30:
        score = 15
    elif days_ago <= 90:
        score = 12
    elif days_ago <= 180:
        score = 9
    elif days_ago <= 365:
        score = 6
    elif days_ago <= 730:
        score = 3
    else:
        score = 1

    explanation = f"Last commit {days_ago} days ago → {score:.1f}/15"
    return round(score, 1), explanation


def score_community_signal(star_count: int, is_fork: bool, has_original_commits: bool) -> tuple[float, str]:
    """Score based on community signals.
    
    Max 10 points.
    """
    # Stars (up to 6 pts)
    if star_count >= 50:
        star_score = 6
    elif star_count >= 10:
        star_score = 4
    elif star_count >= 3:
        star_score = 2
    elif star_count >= 1:
        star_score = 1
    else:
        star_score = 0

    # Originality (up to 4 pts)
    if not is_fork:
        orig_score = 4
    elif has_original_commits:
        orig_score = 2
    else:
        orig_score = 0

    total = min(10, star_score + orig_score)
    fork_str = "fork" if is_fork else "original"
    explanation = f"Community: {star_count} stars, {fork_str} → {total:.1f}/10"
    return round(total, 1), explanation


def compute_project_score(project_data: dict) -> dict:
    """Compute the full evidence score for a project.
    
    Returns a dict with total score (0-100), breakdown, and explanations.
    """
    s1, e1 = score_commit_consistency(
        project_data.get("commit_timeline", []),
        project_data.get("commit_count", 0),
    )
    s2, e2 = score_project_complexity(
        project_data.get("languages", {}),
        project_data.get("file_count", 0),
        project_data.get("repo_size_kb", 0),
    )
    s3, e3 = score_readme_quality(
        project_data.get("readme_length", 0),
        project_data.get("readme_content", ""),
    )
    s4, e4 = score_recent_activity(project_data.get("last_commit_date", ""))
    s5, e5 = score_community_signal(
        project_data.get("star_count", 0),
        project_data.get("is_fork", False),
        project_data.get("has_original_commits", True),
    )

    raw_total = s1 + s2 + s3 + s4 + s5

    # Anti-gaming penalties
    warnings = project_data.get("anti_gaming_flags", [])
    penalty = 0
    if warnings:
        for w in warnings:
            if "no original commits" in w.lower():
                penalty += 30
            elif "single day" in w.lower() or "commit dump" in w.lower():
                penalty += 15
            elif "minimal contribution" in w.lower():
                penalty += 10
            elif "concentrated" in w.lower():
                penalty += 10

    total = max(0, raw_total - penalty)

    return {
        "total": round(total, 1),
        "commit_consistency": s1,
        "project_complexity": s2,
        "readme_quality": s3,
        "recent_activity": s4,
        "community_signal": s5,
        "penalty": round(penalty, 1),
        "explanation": [e1, e2, e3, e4, e5],
        "warnings": warnings,
    }


def compute_student_score(project_scores: list[dict]) -> dict:
    """Aggregate project scores into a student-level evidence score.
    
    Uses a weighted average, giving more weight to the best projects.
    """
    if not project_scores:
        return {
            "total": 0,
            "project_count": 0,
            "best_project_score": 0,
            "average_score": 0,
            "explanation": ["No projects to score"],
            "warnings": [],
        }

    scores = [p["total"] for p in project_scores]
    scores.sort(reverse=True)

    # Weighted: best project counts more
    if len(scores) == 1:
        total = scores[0]
    elif len(scores) == 2:
        total = scores[0] * 0.6 + scores[1] * 0.4
    else:
        # Top 3 contribute most
        top = scores[:3]
        rest = scores[3:]
        weighted = sum(top) / len(top) * 0.7
        rest_avg = sum(rest) / len(rest) * 0.3 if rest else 0
        total = weighted + rest_avg

    # Bonus for having multiple quality projects (up to +10)
    quality_projects = sum(1 for s in scores if s >= 50)
    multi_bonus = min(10, quality_projects * 3)
    total = min(100, total + multi_bonus)

    all_warnings = []
    for p in project_scores:
        all_warnings.extend(p.get("warnings", []))

    return {
        "total": round(total, 1),
        "project_count": len(scores),
        "best_project_score": scores[0],
        "average_score": round(sum(scores) / len(scores), 1),
        "explanation": [
            f"Scored across {len(scores)} project(s)",
            f"Best project: {scores[0]}/100",
            f"Multi-project bonus: +{multi_bonus}",
        ],
        "warnings": list(set(all_warnings)),
    }
