"""SkillProof - Recruiter API routes."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Student, Skill

router = APIRouter(prefix="/api/recruiter", tags=["recruiter"])


@router.get("/search")
def search_students(
    skill: str = Query(default=None, description="Filter by skill name"),
    min_score: float = Query(default=0, description="Minimum evidence score"),
    sort_by: str = Query(default="evidence_score", description="Sort field"),
    db: Session = Depends(get_db),
):
    """Search and filter students by skill and score. Recruiter view."""
    query = db.query(Student)

    if skill:
        # Find students who have this skill
        skill_lower = skill.lower()
        student_ids = (
            db.query(Skill.student_id)
            .filter(Skill.name.ilike(f"%{skill_lower}%"))
            .distinct()
            .all()
        )
        ids = [s[0] for s in student_ids]
        if not ids:
            return {"students": [], "total": 0, "filter": {"skill": skill, "min_score": min_score}}
        query = query.filter(Student.id.in_(ids))

    if min_score > 0:
        query = query.filter(Student.evidence_score >= min_score)

    if sort_by == "name":
        query = query.order_by(Student.name)
    else:
        query = query.order_by(Student.evidence_score.desc())

    students = query.all()

    results = []
    for s in students:
        # Only include public projects
        public_projects = [p for p in s.projects if p.is_public]
        skills_data = [
            {
                "name": sk.name,
                "level": sk.level,
                "source": sk.source,
                "verified_by": sk.verified_by,
                "evidence_projects": len(sk.evidence_project_ids) if sk.evidence_project_ids else 0,
            }
            for sk in s.skills
        ]
        results.append({
            "id": s.id,
            "name": s.name,
            "github_username": s.github_username,
            "avatar_url": s.avatar_url,
            "evidence_score": s.evidence_score,
            "project_count": len(public_projects),
            "skills": skills_data,
            "score_breakdown": s.score_breakdown or {},
        })

    return {
        "students": results,
        "total": len(results),
        "filter": {"skill": skill, "min_score": min_score},
    }


@router.get("/skills")
def list_all_skills(db: Session = Depends(get_db)):
    """List all unique skills across all students, with counts."""
    skills = db.query(Skill.name, Skill.source).all()
    skill_counts = {}
    for name, source in skills:
        if name not in skill_counts:
            skill_counts[name] = {"total": 0, "verified": 0}
        skill_counts[name]["total"] += 1
        if source == "verified":
            skill_counts[name]["verified"] += 1

    result = [
        {"name": name, "total_students": data["total"], "verified_count": data["verified"]}
        for name, data in sorted(skill_counts.items(), key=lambda x: x[1]["total"], reverse=True)
    ]
    return {"skills": result}
