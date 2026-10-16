"""SkillProof - Seed Script.

Creates 5 fake demo student profiles with realistic project data
so the demo works fully offline without GitHub API calls.

Usage: python -m app.seed
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import engine, SessionLocal, Base
from app.models import Student, Project, Skill, MentorFeedback
from app.services.scoring import compute_project_score, compute_student_score
from datetime import datetime, timezone, timedelta
import random


def generate_timeline(start_year: int, start_month: int, months: int, intensity: str = "medium") -> list[dict]:
    """Generate a realistic commit timeline."""
    timeline = []
    for i in range(months):
        m = start_month + i
        y = start_year + (m - 1) // 12
        month = ((m - 1) % 12) + 1
        if intensity == "high":
            count = random.randint(8, 30)
        elif intensity == "medium":
            count = random.randint(3, 15)
        else:
            count = random.randint(1, 5)
        # Some months might have 0 commits for realism
        if random.random() < 0.15:
            count = 0
        if count > 0:
            timeline.append({"month": f"{y}-{month:02d}", "count": count})
    return timeline


SEED_DATA = [
    {
        "student": {
            "name": "Aria Chen",
            "email": "aria.chen@demo.edu",
            "github_username": "ariachen",
            "bio": "CS senior passionate about machine learning and full-stack development. Building AI tools that actually help people.",
            "avatar_url": "",
        },
        "projects": [
            {
                "name": "smartnotes-ai",
                "github_repo_url": "https://github.com/ariachen/smartnotes-ai",
                "description": "An AI-powered note-taking app that auto-generates summaries and flashcards using NLP.",
                "languages": {"Python": 45000, "JavaScript": 32000, "HTML": 8000, "CSS": 5000},
                "topics": ["machine-learning", "web", "api", "flask"],
                "commit_count": 187,
                "first_commit_date": "2025-02-10T10:00:00Z",
                "last_commit_date": "2026-09-28T15:30:00Z",
                "readme_content": "# SmartNotes AI\n\nAn intelligent note-taking application.\n\n## Features\n- Auto-summarization of notes\n- Flashcard generation\n- Semantic search across notes\n\n## Installation\n```bash\npip install -r requirements.txt\npython app.py\n```\n\n## Usage\nUpload your notes and get AI-generated summaries.\n\n## Tech Stack\n- Flask backend with REST API\n- React frontend\n- TensorFlow for NLP models\n- PostgreSQL database\n\n## Contributing\nPRs welcome! See CONTRIBUTING.md.\n\n## License\nMIT",
                "readme_length": 520,
                "is_fork": False,
                "star_count": 23,
                "file_count": 42,
                "repo_size_kb": 3400,
                "timeline_config": {"start_year": 2025, "start_month": 2, "months": 20, "intensity": "high"},
            },
            {
                "name": "budget-tracker",
                "github_repo_url": "https://github.com/ariachen/budget-tracker",
                "description": "A personal finance tracker with data visualization and spending predictions.",
                "languages": {"Python": 28000, "JavaScript": 18000, "SQL": 3000},
                "topics": ["data-science", "web", "react"],
                "commit_count": 94,
                "first_commit_date": "2025-06-01T09:00:00Z",
                "last_commit_date": "2026-08-15T11:00:00Z",
                "readme_content": "# Budget Tracker\n\nTrack spending and predict future expenses.\n\n## Installation\n```\npip install -r requirements.txt\n```\n\n## Usage\nRun the app and connect your accounts.\n\n## License\nMIT",
                "readme_length": 240,
                "is_fork": False,
                "star_count": 8,
                "file_count": 25,
                "repo_size_kb": 1200,
                "timeline_config": {"start_year": 2025, "start_month": 6, "months": 15, "intensity": "medium"},
            },
            {
                "name": "ml-image-classifier",
                "github_repo_url": "https://github.com/ariachen/ml-image-classifier",
                "description": "Deep learning image classifier with transfer learning, built for a course project.",
                "languages": {"Python": 35000, "Jupyter Notebook": 20000},
                "topics": ["deep-learning", "machine-learning", "tensorflow"],
                "commit_count": 45,
                "first_commit_date": "2025-09-01T08:00:00Z",
                "last_commit_date": "2026-01-20T16:00:00Z",
                "readme_content": "# ML Image Classifier\n\nImage classification using transfer learning with TensorFlow.\n\n## Setup\n```bash\npip install tensorflow numpy pandas\njupyter notebook\n```\n\n## Results\n95.2% accuracy on test set.\n\n## Architecture\n- ResNet50 base model\n- Custom dense layers\n- Data augmentation pipeline",
                "readme_length": 350,
                "is_fork": False,
                "star_count": 12,
                "file_count": 18,
                "repo_size_kb": 8500,
                "timeline_config": {"start_year": 2025, "start_month": 9, "months": 5, "intensity": "medium"},
            },
        ],
    },
    {
        "student": {
            "name": "Marcus Johnson",
            "email": "marcus.j@demo.edu",
            "github_username": "marcusdev",
            "bio": "Full-stack developer focusing on React and Node.js. Love building tools that make developers more productive.",
            "avatar_url": "",
        },
        "projects": [
            {
                "name": "devflow",
                "github_repo_url": "https://github.com/marcusdev/devflow",
                "description": "Developer productivity dashboard with GitHub integration and project management.",
                "languages": {"TypeScript": 52000, "JavaScript": 15000, "CSS": 8000, "HTML": 3000},
                "topics": ["react", "web", "api", "docker"],
                "commit_count": 234,
                "first_commit_date": "2024-11-01T10:00:00Z",
                "last_commit_date": "2026-09-30T14:00:00Z",
                "readme_content": "# DevFlow\n\nA developer productivity dashboard.\n\n## Features\n- GitHub activity tracking\n- Kanban board\n- Time tracking\n- CI/CD pipeline status\n\n## Installation\n```bash\nnpm install\nnpm run dev\n```\n\n## Tech Stack\n- React + TypeScript frontend\n- Node.js + Express backend\n- MongoDB database\n- Docker deployment\n- GitHub Actions CI/CD\n\n## Contributing\nSee CONTRIBUTING.md for guidelines.\n\n## License\nApache 2.0",
                "readme_length": 580,
                "is_fork": False,
                "star_count": 45,
                "file_count": 65,
                "repo_size_kb": 4200,
                "timeline_config": {"start_year": 2024, "start_month": 11, "months": 23, "intensity": "high"},
            },
            {
                "name": "react-component-lib",
                "github_repo_url": "https://github.com/marcusdev/react-component-lib",
                "description": "Accessible React component library with Storybook documentation.",
                "languages": {"TypeScript": 38000, "CSS": 12000, "JavaScript": 5000},
                "topics": ["react", "testing", "web"],
                "commit_count": 156,
                "first_commit_date": "2025-03-01T08:00:00Z",
                "last_commit_date": "2026-09-15T10:00:00Z",
                "readme_content": "# React Component Library\n\n## Installation\n```bash\nnpm install @marcusdev/components\n```\n\n## Usage\n```tsx\nimport { Button } from '@marcusdev/components'\n```\n\n## Components\n- Button, Input, Modal, Toast\n- All WCAG 2.1 AA compliant\n- Unit tests with Jest\n\n## License\nMIT",
                "readme_length": 400,
                "is_fork": False,
                "star_count": 31,
                "file_count": 48,
                "repo_size_kb": 2800,
                "timeline_config": {"start_year": 2025, "start_month": 3, "months": 19, "intensity": "high"},
            },
        ],
    },
    {
        "student": {
            "name": "Priya Sharma",
            "email": "priya.s@demo.edu",
            "github_username": "priyabuilds",
            "bio": "Backend engineer interested in distributed systems, databases and cloud infrastructure.",
            "avatar_url": "",
        },
        "projects": [
            {
                "name": "distributed-cache",
                "github_repo_url": "https://github.com/priyabuilds/distributed-cache",
                "description": "A distributed in-memory cache with consistent hashing and replication.",
                "languages": {"Go": 42000, "Python": 8000, "Shell": 2000, "Dockerfile": 1500},
                "topics": ["docker", "kubernetes", "database"],
                "commit_count": 112,
                "first_commit_date": "2025-05-01T09:00:00Z",
                "last_commit_date": "2026-09-20T17:00:00Z",
                "readme_content": "# Distributed Cache\n\nA distributed in-memory cache system.\n\n## Features\n- Consistent hashing for key distribution\n- Configurable replication factor\n- TTL support\n- REST API interface\n\n## Installation\n```bash\ngo build -o dcache cmd/main.go\n./dcache --config config.yaml\n```\n\n## Architecture\nUses a ring-based consistent hashing algorithm with virtual nodes.\n\n## Testing\n```bash\ngo test ./...\n```\n\n## Deployment\nDocker and Kubernetes manifests included.\n\n## License\nMIT",
                "readme_length": 620,
                "is_fork": False,
                "star_count": 19,
                "file_count": 35,
                "repo_size_kb": 1800,
                "timeline_config": {"start_year": 2025, "start_month": 5, "months": 17, "intensity": "high"},
            },
            {
                "name": "log-analyzer",
                "github_repo_url": "https://github.com/priyabuilds/log-analyzer",
                "description": "CLI tool for parsing and analyzing application logs with pattern detection.",
                "languages": {"Python": 22000, "Shell": 3000},
                "topics": ["cli", "devops"],
                "commit_count": 67,
                "first_commit_date": "2025-08-01T10:00:00Z",
                "last_commit_date": "2026-07-10T12:00:00Z",
                "readme_content": "# Log Analyzer\n\nA CLI tool for log analysis.\n\n## Usage\n```bash\npip install log-analyzer\nloganalyze --input app.log --pattern error\n```\n\n## Features\n- Pattern matching\n- Anomaly detection\n- Report generation\n\n## License\nMIT",
                "readme_length": 280,
                "is_fork": False,
                "star_count": 5,
                "file_count": 15,
                "repo_size_kb": 450,
                "timeline_config": {"start_year": 2025, "start_month": 8, "months": 12, "intensity": "medium"},
            },
        ],
    },
    {
        "student": {
            "name": "Jordan Lee",
            "email": "jordan.l@demo.edu",
            "github_username": "jordanl33",
            "bio": "New to programming, learning web development and exploring data science.",
            "avatar_url": "",
        },
        "projects": [
            {
                "name": "my-portfolio",
                "github_repo_url": "https://github.com/jordanl33/my-portfolio",
                "description": "Personal portfolio website built with HTML and CSS.",
                "languages": {"HTML": 8000, "CSS": 6000, "JavaScript": 2000},
                "topics": ["web"],
                "commit_count": 18,
                "first_commit_date": "2026-06-01T10:00:00Z",
                "last_commit_date": "2026-09-01T14:00:00Z",
                "readme_content": "# My Portfolio\n\nPersonal website.\n\n## How to run\nOpen index.html in browser.",
                "readme_length": 80,
                "is_fork": False,
                "star_count": 0,
                "file_count": 8,
                "repo_size_kb": 150,
                "timeline_config": {"start_year": 2026, "start_month": 6, "months": 4, "intensity": "low"},
            },
            {
                "name": "awesome-python",
                "github_repo_url": "https://github.com/jordanl33/awesome-python",
                "description": "A curated list of awesome Python frameworks, libraries and resources.",
                "languages": {"Python": 100},
                "topics": [],
                "commit_count": 1,
                "first_commit_date": "2026-08-15T10:00:00Z",
                "last_commit_date": "2026-08-15T10:00:00Z",
                "readme_content": "",
                "readme_length": 0,
                "is_fork": True,
                "has_original_commits_override": False,
                "star_count": 0,
                "file_count": 1,
                "repo_size_kb": 50,
                "timeline_config": {"start_year": 2026, "start_month": 8, "months": 1, "intensity": "low"},
                "anti_gaming_override": ["Fork with no original commits — likely not the student's own work"],
            },
        ],
    },
    {
        "student": {
            "name": "Sofia Rodriguez",
            "email": "sofia.r@demo.edu",
            "github_username": "sofiadev",
            "bio": "Mobile developer specializing in Flutter and cross-platform apps. Hackathon enthusiast.",
            "avatar_url": "",
        },
        "projects": [
            {
                "name": "healthmate",
                "github_repo_url": "https://github.com/sofiadev/healthmate",
                "description": "A cross-platform health tracking app with workout plans and nutrition logging.",
                "languages": {"Dart": 48000, "Swift": 5000, "Kotlin": 5000, "C++": 2000},
                "topics": ["mobile", "flutter", "android", "ios"],
                "commit_count": 203,
                "first_commit_date": "2025-01-15T09:00:00Z",
                "last_commit_date": "2026-09-25T16:00:00Z",
                "readme_content": "# HealthMate\n\nYour personal health companion.\n\n## Features\n- Workout tracking & custom plans\n- Nutrition logging with barcode scanner\n- Progress charts & analytics\n- Social features for accountability\n\n## Installation\n```bash\nflutter pub get\nflutter run\n```\n\n## Architecture\n- BLoC pattern for state management\n- Repository pattern for data layer\n- Unit and widget tests\n\n## Screenshots\n[See /docs/screenshots]\n\n## Contributing\nWelcome! See CONTRIBUTING.md\n\n## License\nMIT",
                "readme_length": 590,
                "is_fork": False,
                "star_count": 38,
                "file_count": 78,
                "repo_size_kb": 6200,
                "timeline_config": {"start_year": 2025, "start_month": 1, "months": 21, "intensity": "high"},
            },
            {
                "name": "flutter-weather",
                "github_repo_url": "https://github.com/sofiadev/flutter-weather",
                "description": "Beautiful weather app with animations, built during a 24-hour hackathon.",
                "languages": {"Dart": 22000, "Swift": 1000, "Kotlin": 1000},
                "topics": ["flutter", "mobile", "api"],
                "commit_count": 47,
                "first_commit_date": "2025-11-10T08:00:00Z",
                "last_commit_date": "2026-03-20T18:00:00Z",
                "readme_content": "# Flutter Weather\n\nBeautiful weather app with smooth animations.\n\n## Features\n- Current weather & 5-day forecast\n- Location-based updates\n- Custom animations\n\n## Usage\n```\nflutter run\n```\n\n## API\nUses OpenWeatherMap API.\n\n## License\nMIT",
                "readme_length": 310,
                "is_fork": False,
                "star_count": 15,
                "file_count": 22,
                "repo_size_kb": 1800,
                "timeline_config": {"start_year": 2025, "start_month": 11, "months": 5, "intensity": "medium"},
            },
        ],
    },
]

# Mentor feedback to seed
SEED_FEEDBACK = [
    {
        "student_email": "aria.chen@demo.edu",
        "project_name": "smartnotes-ai",
        "mentor_name": "Dr. Sarah Mitchell",
        "mentor_email": "s.mitchell@university.edu",
        "rating": 5,
        "strengths": "Excellent integration of NLP models with a clean web interface. Code is well-structured with proper separation of concerns. Good test coverage.",
        "improvements": "Could add more edge case handling in the summarization pipeline. Consider adding rate limiting to the API.",
        "comments": "One of the strongest student projects I've reviewed this semester. Demonstrates real-world ML engineering skills.",
        "skills_verified": ["Python", "Machine Learning", "Backend Development", "Web Development"],
    },
    {
        "student_email": "marcus.j@demo.edu",
        "project_name": "devflow",
        "mentor_name": "Prof. James Park",
        "mentor_email": "j.park@university.edu",
        "rating": 5,
        "strengths": "Professional-quality TypeScript code with excellent component architecture. Great use of Docker for deployment. CI/CD pipeline is well-configured.",
        "improvements": "Mobile responsiveness could be improved. Consider adding end-to-end tests.",
        "comments": "Exceptional project that goes well beyond course requirements. Production-ready quality.",
        "skills_verified": ["TypeScript", "React", "Web Development", "Docker", "CI/CD"],
    },
    {
        "student_email": "priya.s@demo.edu",
        "project_name": "distributed-cache",
        "mentor_name": "Dr. Alex Kumar",
        "mentor_email": "a.kumar@university.edu",
        "rating": 4,
        "strengths": "Strong understanding of distributed systems concepts. Clean Go code with good documentation. Consistent hashing implementation is correct and efficient.",
        "improvements": "Could add more comprehensive benchmarking. Consider implementing a gossip protocol for node discovery.",
        "comments": "Solid systems engineering project. Shows deep understanding of distributed computing principles.",
        "skills_verified": ["Go", "Systems Programming", "Docker", "DevOps"],
    },
    {
        "student_email": "sofia.r@demo.edu",
        "project_name": "healthmate",
        "mentor_name": "Prof. Maria Santos",
        "mentor_email": "m.santos@university.edu",
        "rating": 5,
        "strengths": "Beautiful UI with attention to accessibility. BLoC pattern is correctly implemented. Cross-platform code sharing is exemplary.",
        "improvements": "Offline sync could be more robust. Consider adding integration tests.",
        "comments": "Outstanding mobile development skills. This app could genuinely be published to the stores.",
        "skills_verified": ["Dart", "Flutter Development", "Mobile Development", "iOS Development", "Android Development"],
    },
]


def seed_database():
    """Seed the database with demo data."""
    # Create tables
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    try:
        # Check if already seeded
        existing = db.query(Student).first()
        if existing:
            print("[!] Database already has data. Clearing and re-seeding...")
            db.query(MentorFeedback).delete()
            db.query(Skill).delete()
            db.query(Project).delete()
            db.query(Student).delete()
            db.commit()

        for data in SEED_DATA:
            # Create student
            student = Student(**data["student"])
            db.add(student)
            db.flush()

            all_project_scores = []
            all_skills = []

            for proj_data in data["projects"]:
                # Generate timeline
                tc = proj_data.pop("timeline_config")
                timeline = generate_timeline(**tc)
                has_orig_override = proj_data.pop("has_original_commits_override", None)
                anti_gaming_override = proj_data.pop("anti_gaming_override", None)

                # Build project dict for scoring
                score_input = {
                    "commit_timeline": timeline,
                    "commit_count": proj_data["commit_count"],
                    "languages": proj_data["languages"],
                    "file_count": proj_data["file_count"],
                    "repo_size_kb": proj_data["repo_size_kb"],
                    "readme_length": proj_data["readme_length"],
                    "readme_content": proj_data["readme_content"],
                    "last_commit_date": proj_data["last_commit_date"],
                    "star_count": proj_data["star_count"],
                    "is_fork": proj_data["is_fork"],
                    "has_original_commits": has_orig_override if has_orig_override is not None else not proj_data["is_fork"],
                    "anti_gaming_flags": anti_gaming_override or [],
                }

                score_result = compute_project_score(score_input)
                all_project_scores.append(score_result)

                # Extract skills
                from app.services.ai_summary import extract_skills_from_project, generate_mock_summary
                proj_skills = extract_skills_from_project({
                    "languages": proj_data["languages"],
                    "topics": proj_data["topics"],
                    "readme_content": proj_data["readme_content"],
                })
                ai_summary = generate_mock_summary({
                    "name": proj_data["name"],
                    "description": proj_data["description"],
                    "languages": proj_data["languages"],
                    "commit_count": proj_data["commit_count"],
                    "topics": proj_data["topics"],
                })

                project = Project(
                    student_id=student.id,
                    github_repo_url=proj_data["github_repo_url"],
                    name=proj_data["name"],
                    description=proj_data["description"],
                    languages=proj_data["languages"],
                    topics=proj_data["topics"],
                    commit_count=proj_data["commit_count"],
                    first_commit_date=proj_data["first_commit_date"],
                    last_commit_date=proj_data["last_commit_date"],
                    commit_timeline=timeline,
                    readme_content=proj_data["readme_content"],
                    readme_length=proj_data["readme_length"],
                    is_fork=proj_data["is_fork"],
                    has_original_commits=has_orig_override if has_orig_override is not None else not proj_data["is_fork"],
                    star_count=proj_data["star_count"],
                    file_count=proj_data["file_count"],
                    repo_size_kb=proj_data["repo_size_kb"],
                    ai_summary=ai_summary,
                    ai_skills=proj_skills,
                    evidence_score=score_result["total"],
                    score_breakdown=score_result,
                    anti_gaming_flags=anti_gaming_override or [],
                )
                db.add(project)
                db.flush()

                # Track skills
                for sk in proj_skills:
                    all_skills.append((sk, project.id, timeline))

            # Create skills for student
            skill_map = {}
            for skill_name, project_id, timeline in all_skills:
                if skill_name not in skill_map:
                    skill_map[skill_name] = {"project_ids": [], "timeline": []}
                if project_id not in skill_map[skill_name]["project_ids"]:
                    skill_map[skill_name]["project_ids"].append(project_id)
                skill_map[skill_name]["timeline"].extend(timeline)

            for skill_name, info in skill_map.items():
                skill = Skill(
                    student_id=student.id,
                    name=skill_name,
                    source="ai-suggested",
                    evidence_project_ids=info["project_ids"],
                    monthly_activity=info["timeline"],
                )
                db.add(skill)

            # Compute student score
            student_score = compute_student_score(all_project_scores)
            student.evidence_score = student_score["total"]
            student.score_breakdown = student_score

            print(f"  [+] {student.name} - score: {student_score['total']}/100, "
                  f"{len(data['projects'])} projects, {len(skill_map)} skills")

        db.commit()

        # Add mentor feedback
        print("\n[*] Adding mentor feedback...")
        for fb_data in SEED_FEEDBACK:
            student = db.query(Student).filter(Student.email == fb_data["student_email"]).first()
            if not student:
                continue
            project = db.query(Project).filter(
                Project.student_id == student.id,
                Project.name == fb_data["project_name"],
            ).first()
            if not project:
                continue

            feedback = MentorFeedback(
                project_id=project.id,
                mentor_name=fb_data["mentor_name"],
                mentor_email=fb_data["mentor_email"],
                rating=fb_data["rating"],
                strengths=fb_data["strengths"],
                improvements=fb_data["improvements"],
                comments=fb_data["comments"],
                skills_verified=fb_data["skills_verified"],
            )
            db.add(feedback)

            # Verify skills
            for skill_name in fb_data["skills_verified"]:
                skill = db.query(Skill).filter(
                    Skill.student_id == student.id,
                    Skill.name == skill_name,
                ).first()
                if skill:
                    skill.source = "verified"
                    skill.verified_by = fb_data["mentor_name"]
                    skill.verified_at = datetime.now(timezone.utc)

            print(f"  [+] Feedback from {fb_data['mentor_name']} on {fb_data['project_name']}")

        db.commit()
        print(f"\n[SUCCESS] Seeded {len(SEED_DATA)} students with projects, skills, and feedback!")

    except Exception as e:
        db.rollback()
        print(f"[-] Seed failed: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed_database()
