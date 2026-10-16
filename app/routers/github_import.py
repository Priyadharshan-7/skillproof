"""SkillProof - GitHub Import API routes with Real-Time Progress Streaming."""
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Student, Project, Skill
from app.schemas import GitHubImportRequest, GitHubRepoImportRequest
from app.services.github_service import import_full_repo, fetch_user_repos, fetch_rate_limit
from app.services.scoring import compute_project_score, compute_student_score
from app.services.ai_summary import generate_ai_summary
from app.services.websocket_manager import manager
import re
import json
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/import", tags=["github-import"])


def parse_github_repo_url(url: str) -> tuple[str, str] | None:
    """Robustly parse GitHub repo URL in various formats, stripping .git and slashes."""
    if not url:
        return None
    cleaned = url.strip()
    if cleaned.endswith(".git"):
        cleaned = cleaned[:-4]
    cleaned = cleaned.rstrip("/")
    
    # Matches https://github.com/owner/repo or github.com/owner/repo
    match = re.search(r'(?:https?://)?(?:www\.)?github\.com/([^/\s]+)/([^/\s]+)', cleaned, re.IGNORECASE)
    if match:
        owner, repo = match.group(1), match.group(2)
        if repo.endswith(".git"):
            repo = repo[:-4]
        return owner, repo
        
    # Matches owner/repo
    match_short = re.match(r'^([^/\s]+)/([^/\s]+)$', cleaned)
    if match_short:
        owner, repo = match_short.group(1), match_short.group(2)
        if repo.endswith(".git"):
            repo = repo[:-4]
        return owner, repo
        
    return None


def parse_github_username(raw: str) -> str:
    """Extract username even if a full profile URL was entered."""
    if not raw:
        return ""
    cleaned = raw.strip().lstrip("@").rstrip("/")
    match = re.search(r'(?:https?://)?(?:www\.)?github\.com/([^/\s]+)', cleaned, re.IGNORECASE)
    if match:
        return match.group(1)
    if "/" in cleaned:
        return cleaned.split("/")[0]
    return cleaned


@router.get("/github/rate-limit")
async def get_github_rate_limit():
    """Get real-time GitHub API rate limit status."""
    return await fetch_rate_limit()


@router.post("/live-scan")
async def live_scan_repo(data: GitHubRepoImportRequest):
    """Scan and evaluate any public GitHub repository in real time.
    
    Provides instant analysis without requiring student profile association.
    """
    parsed = parse_github_repo_url(data.repo_url)
    if not parsed:
        raise HTTPException(
            status_code=400,
            detail="Invalid GitHub repo URL. Expected format: https://github.com/owner/repo",
        )

    owner, repo_name = parsed
    repo_data = await import_full_repo(owner, repo_name)
    if not repo_data:
        raise HTTPException(
            status_code=404,
            detail=f"Could not fetch '{owner}/{repo_name}'. Check that it exists and is public.",
        )

    score_result = compute_project_score(repo_data)
    ai_summary, ai_skills = await generate_ai_summary(repo_data)

    # Broadcast live activity event
    await manager.broadcast({
        "type": "activity_event",
        "data": {
            "title": "Real-Time Repo Scan",
            "detail": f"Audited {owner}/{repo_name} — Score: {score_result['total']}/100",
            "badge": "Audit",
        },
    })

    return {
        "repo_name": repo_name,
        "owner": owner,
        "url": repo_data["github_repo_url"],
        "repo_data": repo_data,
        "score_result": score_result,
        "ai_summary": ai_summary,
        "ai_skills": ai_skills,
    }


@router.get("/github/{student_id}/stream")
async def stream_github_import(
    student_id: int,
    username: str = Query(..., description="GitHub username"),
    db: Session = Depends(get_db),
):
    """Stream repository import progress in real time via Server-Sent Events (SSE)."""
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    uname = parse_github_username(username)
    if not re.match(r'^[a-zA-Z0-9\-]+$', uname):
        raise HTTPException(status_code=400, detail="Invalid GitHub username format")

    async def event_generator():
        yield f"data: {json.dumps({'type': 'init', 'message': f'Connecting to GitHub for @{uname}...', 'percent': 5})}\n\n"

        repos = await fetch_user_repos(uname)
        if repos is None:
            yield f"data: {json.dumps({'type': 'error', 'message': 'GitHub API error or rate limit reached. Consider adding a GITHUB_TOKEN.', 'percent': 0})}\n\n"
            return
        if not repos:
            yield f"data: {json.dumps({'type': 'error', 'message': f'No public repositories found for @{uname}', 'percent': 0})}\n\n"
            return

        # Update avatar
        if repos and repos[0].get("owner", {}).get("avatar_url"):
            student.avatar_url = repos[0]["owner"]["avatar_url"]
            student.github_username = uname
            db.commit()

        total_repos = min(len(repos), 10)
        yield f"data: {json.dumps({'type': 'discovered', 'count': len(repos), 'to_process': total_repos, 'message': f'Found {len(repos)} repositories. Processing {total_repos}...', 'percent': 15})}\n\n"

        imported_count = 0
        for i, repo in enumerate(repos[:total_repos]):
            repo_name = repo.get("name", "")
            owner = repo.get("owner", {}).get("login", uname)
            progress_pct = 15 + int(((i + 1) / total_repos) * 75)

            yield f"data: {json.dumps({'type': 'progress', 'index': i + 1, 'total': total_repos, 'repo': repo_name, 'message': f'Analyzing {repo_name} ({i+1}/{total_repos})...', 'percent': progress_pct})}\n\n"

            # Skip if already imported
            existing = db.query(Project).filter(
                Project.student_id == student_id,
                Project.github_repo_url == repo.get("html_url", ""),
            ).first()
            if existing:
                yield f"data: {json.dumps({'type': 'repo_skipped', 'repo': repo_name, 'reason': 'Already imported', 'percent': progress_pct})}\n\n"
                continue

            repo_data = await import_full_repo(owner, repo_name)
            if not repo_data:
                yield f"data: {json.dumps({'type': 'repo_skipped', 'repo': repo_name, 'reason': 'Failed to fetch', 'percent': progress_pct})}\n\n"
                continue

            score_result = compute_project_score(repo_data)
            ai_summary, ai_skills = await generate_ai_summary(repo_data)

            project = Project(
                student_id=student_id,
                github_repo_url=repo_data["github_repo_url"],
                name=repo_data["name"],
                description=repo_data["description"],
                languages=repo_data["languages"],
                topics=repo_data["topics"],
                commit_count=repo_data["commit_count"],
                first_commit_date=repo_data["first_commit_date"],
                last_commit_date=repo_data["last_commit_date"],
                commit_timeline=repo_data["commit_timeline"],
                readme_content=repo_data.get("readme_content", ""),
                readme_length=repo_data["readme_length"],
                is_fork=repo_data["is_fork"],
                has_original_commits=repo_data["has_original_commits"],
                star_count=repo_data["star_count"],
                file_count=repo_data["file_count"],
                repo_size_kb=repo_data["repo_size_kb"],
                ai_summary=ai_summary,
                ai_skills=ai_skills,
                evidence_score=score_result["total"],
                score_breakdown=score_result,
                anti_gaming_flags=repo_data["anti_gaming_flags"],
            )
            db.add(project)
            db.flush()

            for skill_name in ai_skills:
                existing_skill = db.query(Skill).filter(
                    Skill.student_id == student_id,
                    Skill.name == skill_name,
                ).first()
                if existing_skill:
                    pids = existing_skill.evidence_project_ids or []
                    if project.id not in pids:
                        pids.append(project.id)
                        existing_skill.evidence_project_ids = pids
                else:
                    skill = Skill(
                        student_id=student_id,
                        name=skill_name,
                        source="ai-suggested",
                        evidence_project_ids=[project.id],
                        monthly_activity=repo_data.get("commit_timeline", []),
                    )
                    db.add(skill)

            imported_count += 1
            yield f"data: {json.dumps({'type': 'repo_imported', 'repo': repo_name, 'score': score_result['total'], 'skills': ai_skills, 'flags': repo_data['anti_gaming_flags'], 'percent': progress_pct})}\n\n"

        # Update student aggregate score
        all_project_scores = [
            p.score_breakdown or {"total": p.evidence_score}
            for p in db.query(Project).filter(Project.student_id == student_id).all()
        ]
        student_score = compute_student_score(all_project_scores)
        student.evidence_score = student_score["total"]
        student.score_breakdown = student_score
        db.commit()

        # Broadcast live updates to all clients
        await manager.broadcast({
            "type": "student_updated",
            "data": {
                "id": student.id,
                "name": student.name,
                "evidence_score": student.evidence_score,
                "score_breakdown": student.score_breakdown,
            },
        })
        await manager.broadcast({
            "type": "activity_event",
            "data": {
                "title": "Live Import Complete",
                "detail": f"{student.name} imported {imported_count} projects — Evidence Score: {student.evidence_score}/100",
                "badge": "Import",
            },
        })

        yield f"data: {json.dumps({'type': 'complete', 'imported_count': imported_count, 'student_score': student_score['total'], 'percent': 100})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/github/{student_id}")
async def import_github_repos(student_id: int, data: GitHubImportRequest, db: Session = Depends(get_db)):
    """Import all public repos for a GitHub username (synchronous fallback)."""
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    username = parse_github_username(data.github_username)
    if not re.match(r'^[a-zA-Z0-9\-]+$', username):
        raise HTTPException(status_code=400, detail="Invalid GitHub username format")

    # Fetch repo list
    repos = await fetch_user_repos(username)
    if repos is None:
        raise HTTPException(status_code=502, detail="GitHub API error (rate limit or network issue)")
    if not repos:
        raise HTTPException(status_code=404, detail=f"No public repos found for '{username}'")

    # Update student GitHub info
    student.github_username = username
    if repos and repos[0].get("owner", {}).get("avatar_url"):
        student.avatar_url = repos[0]["owner"]["avatar_url"]

    imported = []
    project_scores = []

    for repo in repos[:15]:
        repo_name = repo.get("name", "")
        owner = repo.get("owner", {}).get("login", username)

        # Skip if already imported
        existing = db.query(Project).filter(
            Project.student_id == student_id,
            Project.github_repo_url == repo.get("html_url", ""),
        ).first()
        if existing:
            continue

        repo_data = await import_full_repo(owner, repo_name)
        if not repo_data:
            continue

        score_result = compute_project_score(repo_data)
        ai_summary, ai_skills = await generate_ai_summary(repo_data)

        project = Project(
            student_id=student_id,
            github_repo_url=repo_data["github_repo_url"],
            name=repo_data["name"],
            description=repo_data["description"],
            languages=repo_data["languages"],
            topics=repo_data["topics"],
            commit_count=repo_data["commit_count"],
            first_commit_date=repo_data["first_commit_date"],
            last_commit_date=repo_data["last_commit_date"],
            commit_timeline=repo_data["commit_timeline"],
            readme_content=repo_data.get("readme_content", ""),
            readme_length=repo_data["readme_length"],
            is_fork=repo_data["is_fork"],
            has_original_commits=repo_data["has_original_commits"],
            star_count=repo_data["star_count"],
            file_count=repo_data["file_count"],
            repo_size_kb=repo_data["repo_size_kb"],
            ai_summary=ai_summary,
            ai_skills=ai_skills,
            evidence_score=score_result["total"],
            score_breakdown=score_result,
            anti_gaming_flags=repo_data["anti_gaming_flags"],
        )
        db.add(project)
        db.flush()

        imported.append({"name": repo_name, "score": score_result["total"]})
        project_scores.append(score_result)

        for skill_name in ai_skills:
            existing_skill = db.query(Skill).filter(
                Skill.student_id == student_id,
                Skill.name == skill_name,
            ).first()
            if existing_skill:
                pids = existing_skill.evidence_project_ids or []
                if project.id not in pids:
                    pids.append(project.id)
                    existing_skill.evidence_project_ids = pids
            else:
                skill = Skill(
                    student_id=student_id,
                    name=skill_name,
                    source="ai-suggested",
                    evidence_project_ids=[project.id],
                    monthly_activity=repo_data.get("commit_timeline", []),
                )
                db.add(skill)

    all_project_scores = [
        p.score_breakdown or {"total": p.evidence_score}
        for p in db.query(Project).filter(Project.student_id == student_id).all()
    ]
    student_score = compute_student_score(all_project_scores)
    student.evidence_score = student_score["total"]
    student.score_breakdown = student_score
    db.commit()

    # Broadcast live updates
    await manager.broadcast({
        "type": "student_updated",
        "data": {
            "id": student.id,
            "name": student.name,
            "evidence_score": student.evidence_score,
            "score_breakdown": student.score_breakdown,
        },
    })
    await manager.broadcast({
        "type": "activity_event",
        "data": {
            "title": "GitHub Import",
            "detail": f"{student.name} imported {len(imported)} repos — Score: {student.evidence_score}/100",
            "badge": "Import",
        },
    })

    return {
        "message": f"Imported {len(imported)} repos for {username}",
        "imported": imported,
        "student_score": student_score["total"],
    }


@router.post("/repo/{student_id}")
async def import_single_repo(student_id: int, data: GitHubRepoImportRequest, db: Session = Depends(get_db)):
    """Import a single repo by URL."""
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    parsed = parse_github_repo_url(data.repo_url)
    if not parsed:
        raise HTTPException(status_code=400, detail="Invalid GitHub repo URL. Expected: https://github.com/owner/repo")

    owner, repo_name = parsed

    existing = db.query(Project).filter(
        Project.student_id == student_id,
        Project.github_repo_url.contains(f"{owner}/{repo_name}"),
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="This repo is already imported")

    repo_data = await import_full_repo(owner, repo_name)
    if not repo_data:
        raise HTTPException(status_code=404, detail=f"Could not fetch repo '{owner}/{repo_name}'. Check that it exists and is public.")

    score_result = compute_project_score(repo_data)
    ai_summary, ai_skills = await generate_ai_summary(repo_data)

    project = Project(
        student_id=student_id,
        github_repo_url=repo_data["github_repo_url"],
        name=repo_data["name"],
        description=repo_data["description"],
        languages=repo_data["languages"],
        topics=repo_data["topics"],
        commit_count=repo_data["commit_count"],
        first_commit_date=repo_data["first_commit_date"],
        last_commit_date=repo_data["last_commit_date"],
        commit_timeline=repo_data["commit_timeline"],
        readme_content=repo_data.get("readme_content", ""),
        readme_length=repo_data["readme_length"],
        is_fork=repo_data["is_fork"],
        has_original_commits=repo_data["has_original_commits"],
        star_count=repo_data["star_count"],
        file_count=repo_data["file_count"],
        repo_size_kb=repo_data["repo_size_kb"],
        ai_summary=ai_summary,
        ai_skills=ai_skills,
        evidence_score=score_result["total"],
        score_breakdown=score_result,
        anti_gaming_flags=repo_data["anti_gaming_flags"],
    )
    db.add(project)
    db.flush()

    for skill_name in ai_skills:
        existing_skill = db.query(Skill).filter(
            Skill.student_id == student_id, Skill.name == skill_name
        ).first()
        if not existing_skill:
            db.add(Skill(
                student_id=student_id, name=skill_name,
                source="ai-suggested", evidence_project_ids=[project.id],
                monthly_activity=repo_data.get("commit_timeline", []),
            ))

    all_scores = [
        p.score_breakdown or {"total": p.evidence_score}
        for p in db.query(Project).filter(Project.student_id == student_id).all()
    ]
    student_score = compute_student_score(all_scores)
    student.evidence_score = student_score["total"]
    student.score_breakdown = student_score
    db.commit()

    # Broadcast live update
    await manager.broadcast({
        "type": "student_updated",
        "data": {
            "id": student.id,
            "name": student.name,
            "evidence_score": student.evidence_score,
            "score_breakdown": student.score_breakdown,
        },
    })
    await manager.broadcast({
        "type": "activity_event",
        "data": {
            "title": "Project Imported",
            "detail": f"{student.name} imported {repo_name} — Evidence Score: {student.evidence_score}/100",
            "badge": "Import",
        },
    })

    return {
        "message": f"Imported {repo_name}",
        "project_score": score_result["total"],
        "student_score": student_score["total"],
    }
