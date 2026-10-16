"""SkillProof - Student API routes."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Student, Project, Skill
from app.schemas import StudentCreate, StudentOut, StudentBrief, ProjectOut, ProjectVisibilityUpdate
from app.services.scoring import compute_project_score, compute_student_score

router = APIRouter(prefix="/api/students", tags=["students"])


@router.get("/", response_model=list[StudentBrief])
def list_students(db: Session = Depends(get_db)):
    """List all students with brief info."""
    students = db.query(Student).all()
    result = []
    for s in students:
        skills_data = [
            {"id": sk.id, "name": sk.name, "level": sk.level, "source": sk.source,
             "verified_by": sk.verified_by}
            for sk in s.skills
        ]
        result.append(StudentBrief(
            id=s.id, name=s.name, github_username=s.github_username,
            avatar_url=s.avatar_url, evidence_score=s.evidence_score,
            skills=skills_data,
        ))
    return result


@router.get("/{student_id}", response_model=StudentOut)
def get_student(student_id: int, db: Session = Depends(get_db)):
    """Get full student profile with projects and skills."""
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    projects = [
        _project_to_dict(p) for p in student.projects if p.is_public
    ]
    skills = [
        {"id": sk.id, "name": sk.name, "level": sk.level, "source": sk.source,
         "verified_by": sk.verified_by, "verified_at": str(sk.verified_at) if sk.verified_at else None,
         "evidence_project_ids": sk.evidence_project_ids, "monthly_activity": sk.monthly_activity}
        for sk in student.skills
    ]
    return StudentOut(
        id=student.id, name=student.name, email=student.email,
        github_username=student.github_username, bio=student.bio,
        avatar_url=student.avatar_url, evidence_score=student.evidence_score,
        score_breakdown=student.score_breakdown or {},
        projects=projects, skills=skills, created_at=student.created_at,
    )


from app.services.websocket_manager import manager


@router.post("/", response_model=StudentOut)
async def create_student(data: StudentCreate, db: Session = Depends(get_db)):
    """Create a new student profile."""
    existing = db.query(Student).filter(Student.email == data.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    student = Student(
        name=data.name, email=data.email,
        github_username=data.github_username, bio=data.bio or "",
    )
    db.add(student)
    db.commit()
    db.refresh(student)

    # Broadcast new student event
    await manager.broadcast({
        "type": "student_created",
        "data": {
            "id": student.id,
            "name": student.name,
            "github_username": student.github_username,
            "evidence_score": student.evidence_score,
            "skills": [],
        },
    })
    await manager.broadcast({
        "type": "activity_event",
        "data": {
            "title": "New Profile",
            "detail": f"{student.name} registered on SkillProof",
            "badge": "Student",
            "student_id": student.id,
        },
    })

    return get_student(student.id, db)


@router.put("/{student_id}/projects/{project_id}/visibility")
async def update_project_visibility(
    student_id: int, project_id: int,
    data: ProjectVisibilityUpdate,
    db: Session = Depends(get_db),
):
    """Toggle project visibility (privacy control)."""
    project = db.query(Project).filter(
        Project.id == project_id, Project.student_id == student_id
    ).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    project.is_public = data.is_public
    db.commit()

    # Broadcast visibility toggle event
    await manager.broadcast({
        "type": "project_visibility_changed",
        "data": {
            "student_id": student_id,
            "project_id": project_id,
            "is_public": data.is_public,
        },
    })

    return {"message": f"Project visibility set to {'public' if data.is_public else 'private'}"}


@router.get("/{student_id}/projects", response_model=list[ProjectOut])
def get_student_projects(student_id: int, include_private: bool = False, db: Session = Depends(get_db)):
    """Get all projects for a student."""
    query = db.query(Project).filter(Project.student_id == student_id)
    if not include_private:
        query = query.filter(Project.is_public == True)
    projects = query.all()
    return [_project_to_dict(p) for p in projects]


def _project_to_dict(p: Project) -> dict:
    """Convert a Project model to a dict for the response."""
    feedback_list = [
        {"id": f.id, "mentor_name": f.mentor_name, "rating": f.rating,
         "strengths": f.strengths, "improvements": f.improvements,
         "comments": f.comments, "skills_verified": f.skills_verified,
         "created_at": str(f.created_at) if f.created_at else None}
        for f in p.feedback
    ]
    return {
        "id": p.id, "student_id": p.student_id,
        "github_repo_url": p.github_repo_url, "name": p.name,
        "description": p.description, "languages": p.languages or {},
        "topics": p.topics or [], "commit_count": p.commit_count,
        "first_commit_date": p.first_commit_date or "",
        "last_commit_date": p.last_commit_date or "",
        "commit_timeline": p.commit_timeline or [],
        "readme_length": p.readme_length,
        "is_fork": p.is_fork,
        "has_original_commits": p.has_original_commits,
        "star_count": p.star_count, "file_count": p.file_count,
        "repo_size_kb": p.repo_size_kb, "is_public": p.is_public,
        "ai_summary": p.ai_summary, "ai_skills": p.ai_skills or [],
        "evidence_score": p.evidence_score,
        "score_breakdown": p.score_breakdown or {},
        "anti_gaming_flags": p.anti_gaming_flags or [],
        "feedback": feedback_list,
    }
