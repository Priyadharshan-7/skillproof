"""Tests for SkillProof FastAPI API Endpoints."""
import pytest
from app.models import Student, Project, Skill, MentorFeedback


def test_health_check(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "SkillProof"


def test_frontend_and_static_files(client):
    # Test index.html served at root
    res_root = client.get("/")
    assert res_root.status_code == 200
    assert "SkillProof" in res_root.text

    # Test static assets
    res_css = client.get("/static/styles.css")
    assert res_css.status_code == 200
    assert "--bg-primary" in res_css.text

    res_js = client.get("/static/app.js")
    assert res_js.status_code == 200
    assert "showView" in res_js.text


def test_create_and_get_student(client, db_session):
    # Create student
    payload = {
        "name": "Alice Tester",
        "email": "alice@example.com",
        "github_username": "alicetester",
        "bio": "Full stack engineer",
    }
    response = client.post("/api/students/", json=payload)
    assert response.status_code == 200
    student_data = response.json()
    assert student_data["name"] == "Alice Tester"
    assert student_data["email"] == "alice@example.com"
    student_id = student_data["id"]

    # Duplicate email should fail
    dup_res = client.post("/api/students/", json=payload)
    assert dup_res.status_code == 400

    # Get student
    get_res = client.get(f"/api/students/{student_id}")
    assert get_res.status_code == 200
    assert get_res.json()["id"] == student_id

    # List students
    list_res = client.get("/api/students/")
    assert list_res.status_code == 200
    assert len(list_res.json()) >= 1


def test_project_visibility_toggle(client, db_session):
    # Setup student and project
    student = Student(name="Bob Smith", email="bob@example.com", github_username="bobsmith")
    db_session.add(student)
    db_session.commit()
    db_session.refresh(student)

    project = Project(
        student_id=student.id,
        github_repo_url="https://github.com/bobsmith/demo",
        name="demo",
        description="Demo project",
        languages={"Python": 1000},
        commit_count=10,
        is_public=True,
    )
    db_session.add(project)
    db_session.commit()
    db_session.refresh(project)

    # Toggle to private
    res = client.put(
        f"/api/students/{student.id}/projects/{project.id}/visibility",
        json={"is_public": False},
    )
    assert res.status_code == 200
    assert "private" in res.json()["message"]

    # Student public profile should now hide the private project
    prof_res = client.get(f"/api/students/{student.id}")
    assert len(prof_res.json()["projects"]) == 0

    # With include_private=True, it appears
    all_proj_res = client.get(f"/api/students/{student.id}/projects?include_private=true")
    assert len(all_proj_res.json()) == 1


def test_mentor_feedback_and_skill_verification(client, db_session):
    student = Student(name="Carol White", email="carol@example.com")
    db_session.add(student)
    db_session.commit()
    db_session.refresh(student)

    project = Project(
        student_id=student.id,
        github_repo_url="https://github.com/carol/app",
        name="app",
        description="A web app",
        languages={"TypeScript": 20000},
        commit_count=35,
    )
    skill = Skill(
        student_id=student.id,
        name="TypeScript",
        source="ai-suggested",
    )
    db_session.add(project)
    db_session.add(skill)
    db_session.commit()
    db_session.refresh(project)
    db_session.refresh(skill)

    # Submit feedback verifying TypeScript
    fb_payload = {
        "project_id": project.id,
        "mentor_name": "Prof. Turing",
        "mentor_email": "turing@university.edu",
        "rating": 5,
        "strengths": "Clean modular architecture",
        "improvements": "Add more end-to-end tests",
        "comments": "Great work overall",
        "skills_verified": ["TypeScript"],
    }
    fb_res = client.post("/api/feedback/", json=fb_payload)
    assert fb_res.status_code == 200
    fb_data = fb_res.json()
    assert fb_data["rating"] == 5

    # Check that skill is now verified
    db_session.refresh(skill)
    assert skill.source == "verified"
    assert skill.verified_by == "Prof. Turing"
    assert skill.verified_at is not None


def test_recruiter_search(client, db_session):
    student = Student(name="Dave Developer", email="dave@example.com", evidence_score=88.5)
    db_session.add(student)
    db_session.commit()
    db_session.refresh(student)

    skill = Skill(student_id=student.id, name="Docker", level="intermediate", source="verified")
    db_session.add(skill)
    db_session.commit()

    # Search by skill Docker
    res = client.get("/api/recruiter/search?skill=Docker")
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 1
    assert data["students"][0]["name"] == "Dave Developer"

    # Search with min_score threshold
    res_high = client.get("/api/recruiter/search?min_score=95")
    assert res_high.json()["total"] == 0

    # Skills catalog
    skills_res = client.get("/api/recruiter/skills")
    assert skills_res.status_code == 200
    skill_names = [s["name"] for s in skills_res.json()["skills"]]
    assert "Docker" in skill_names


def test_url_and_username_parsing():
    from app.routers.github_import import parse_github_repo_url, parse_github_username

    # Test repo URL parsing
    assert parse_github_repo_url("https://github.com/Priyadharshan-7/skillproof.git") == ("Priyadharshan-7", "skillproof")
    assert parse_github_repo_url("https://github.com/Priyadharshan-7/skillproof/") == ("Priyadharshan-7", "skillproof")
    assert parse_github_repo_url("github.com/Priyadharshan-7/skillproof") == ("Priyadharshan-7", "skillproof")
    assert parse_github_repo_url("Priyadharshan-7/skillproof") == ("Priyadharshan-7", "skillproof")
    assert parse_github_repo_url("invalid-url") is None

    # Test username parsing
    assert parse_github_username("Priyadharshan-7") == "Priyadharshan-7"
    assert parse_github_username("@Priyadharshan-7") == "Priyadharshan-7"
    assert parse_github_username("https://github.com/Priyadharshan-7") == "Priyadharshan-7"
    assert parse_github_username("https://github.com/Priyadharshan-7/skillproof") == "Priyadharshan-7"
