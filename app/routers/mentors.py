"""SkillProof - Mentor Feedback API routes."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime, timezone
from app.database import get_db
from app.models import MentorFeedback, Project, Skill
from app.schemas import MentorFeedbackCreate, MentorFeedbackOut

router = APIRouter(prefix="/api/feedback", tags=["mentor-feedback"])


from app.services.websocket_manager import manager


@router.post("/", response_model=MentorFeedbackOut)
async def create_feedback(data: MentorFeedbackCreate, db: Session = Depends(get_db)):
    """Submit mentor feedback for a project."""
    project = db.query(Project).filter(Project.id == data.project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    feedback = MentorFeedback(
        project_id=data.project_id,
        mentor_name=data.mentor_name,
        mentor_email=data.mentor_email or "",
        rating=data.rating,
        strengths=data.strengths,
        improvements=data.improvements,
        comments=data.comments,
        skills_verified=data.skills_verified,
    )
    db.add(feedback)

    # Verify skills if mentor approved them
    if data.skills_verified:
        for skill_name in data.skills_verified:
            skill = db.query(Skill).filter(
                Skill.student_id == project.student_id,
                Skill.name == skill_name,
            ).first()
            if skill:
                skill.source = "verified"
                skill.verified_by = data.mentor_name
                skill.verified_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(feedback)

    # Broadcast real-time mentor event
    student_name = project.student.name if project.student else ""
    await manager.broadcast({
        "type": "mentor_feedback_added",
        "data": {
            "feedback_id": feedback.id,
            "project_id": project.id,
            "project_name": project.name,
            "student_id": project.student_id,
            "student_name": student_name,
            "mentor_name": feedback.mentor_name,
            "rating": feedback.rating,
            "skills_verified": feedback.skills_verified or [],
        },
    })
    skills_text = f" and verified {', '.join(feedback.skills_verified)}" if feedback.skills_verified else ""
    await manager.broadcast({
        "type": "activity_event",
        "data": {
            "title": "Mentor Feedback",
            "detail": f"{feedback.mentor_name} reviewed '{project.name}' ({feedback.rating}★){skills_text}",
            "badge": "Mentor",
            "student_id": project.student_id,
        },
    })

    return feedback


@router.get("/project/{project_id}", response_model=list[MentorFeedbackOut])
def get_project_feedback(project_id: int, db: Session = Depends(get_db)):
    """Get all feedback for a project."""
    feedback = db.query(MentorFeedback).filter(
        MentorFeedback.project_id == project_id
    ).all()
    return feedback


@router.get("/{feedback_id}", response_model=MentorFeedbackOut)
def get_feedback(feedback_id: int, db: Session = Depends(get_db)):
    """Get a single feedback entry."""
    feedback = db.query(MentorFeedback).filter(MentorFeedback.id == feedback_id).first()
    if not feedback:
        raise HTTPException(status_code=404, detail="Feedback not found")
    return feedback
