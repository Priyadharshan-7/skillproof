"""SkillProof - AI Summary Service.

Generates plain-language summaries and skill mappings for repos.
Uses OpenAI if OPENAI_API_KEY is set, otherwise falls back to a
rule-based mock summary. All AI outputs are marked 'AI-suggested'.
"""
import os
import logging

logger = logging.getLogger(__name__)

# Common language-to-skill mappings
LANGUAGE_SKILL_MAP = {
    "Python": ["Python", "Backend Development"],
    "JavaScript": ["JavaScript", "Web Development"],
    "TypeScript": ["TypeScript", "Web Development"],
    "Java": ["Java", "Backend Development"],
    "C++": ["C++", "Systems Programming"],
    "C": ["C", "Systems Programming"],
    "C#": ["C#", ".NET Development"],
    "Go": ["Go", "Backend Development"],
    "Rust": ["Rust", "Systems Programming"],
    "Ruby": ["Ruby", "Web Development"],
    "PHP": ["PHP", "Web Development"],
    "Swift": ["Swift", "iOS Development"],
    "Kotlin": ["Kotlin", "Android Development"],
    "Dart": ["Dart", "Flutter Development"],
    "HTML": ["HTML", "Frontend Development"],
    "CSS": ["CSS", "Frontend Development"],
    "Shell": ["Shell Scripting", "DevOps"],
    "Dockerfile": ["Docker", "DevOps"],
    "HCL": ["Terraform", "Infrastructure as Code"],
    "Jupyter Notebook": ["Data Science", "Python"],
    "R": ["R", "Data Analysis"],
    "SQL": ["SQL", "Database Management"],
    "Scala": ["Scala", "Big Data"],
}

TOPIC_SKILL_MAP = {
    "machine-learning": "Machine Learning",
    "deep-learning": "Deep Learning",
    "data-science": "Data Science",
    "web": "Web Development",
    "api": "API Development",
    "react": "React",
    "vue": "Vue.js",
    "angular": "Angular",
    "django": "Django",
    "flask": "Flask",
    "fastapi": "FastAPI",
    "docker": "Docker",
    "kubernetes": "Kubernetes",
    "devops": "DevOps",
    "ci-cd": "CI/CD",
    "testing": "Testing",
    "database": "Database Management",
    "security": "Security",
    "blockchain": "Blockchain",
    "mobile": "Mobile Development",
    "ios": "iOS Development",
    "android": "Android Development",
    "game": "Game Development",
    "cli": "CLI Development",
}


def generate_mock_summary(project_data: dict) -> str:
    """Generate a rule-based summary when no LLM is available."""
    name = project_data.get("name", "Unknown")
    desc = project_data.get("description", "")
    languages = project_data.get("languages", {})
    commit_count = project_data.get("commit_count", 0)
    topics = project_data.get("topics", [])

    lang_list = list(languages.keys())[:5]
    lang_str = ", ".join(lang_list) if lang_list else "no detected languages"

    summary_parts = [f"**{name}**"]
    if desc:
        summary_parts.append(f"is {desc.lower().rstrip('.')}.")
    else:
        summary_parts.append("is a software project.")

    summary_parts.append(f"Built primarily with {lang_str}.")
    summary_parts.append(f"The repository has {commit_count} commits,")

    if commit_count > 50:
        summary_parts.append("showing sustained development effort.")
    elif commit_count > 10:
        summary_parts.append("indicating moderate development activity.")
    else:
        summary_parts.append("suggesting early-stage or experimental work.")

    if topics:
        summary_parts.append(f"Tagged with: {', '.join(topics[:5])}.")

    return " ".join(summary_parts)


def extract_skills_from_project(project_data: dict) -> list[str]:
    """Extract skills from languages, topics, and README content."""
    skills = set()
    languages = project_data.get("languages", {})
    topics = project_data.get("topics", [])
    readme = project_data.get("readme_content", "").lower()

    # From languages
    for lang in languages:
        if lang in LANGUAGE_SKILL_MAP:
            for s in LANGUAGE_SKILL_MAP[lang]:
                skills.add(s)

    # From topics
    for topic in topics:
        topic_lower = topic.lower()
        if topic_lower in TOPIC_SKILL_MAP:
            skills.add(TOPIC_SKILL_MAP[topic_lower])

    # README keyword detection
    readme_keywords = {
        "rest api": "API Development",
        "graphql": "GraphQL",
        "unit test": "Testing",
        "pytest": "Testing",
        "jest": "Testing",
        "ci/cd": "CI/CD",
        "github actions": "CI/CD",
        "deploy": "Deployment",
        "aws": "AWS",
        "gcp": "Google Cloud",
        "azure": "Azure",
        "machine learning": "Machine Learning",
        "neural network": "Deep Learning",
        "tensorflow": "Deep Learning",
        "pytorch": "Deep Learning",
        "pandas": "Data Analysis",
        "numpy": "Data Analysis",
        "react": "React",
        "next.js": "Next.js",
        "vue": "Vue.js",
        "angular": "Angular",
        "docker": "Docker",
        "kubernetes": "Kubernetes",
        "postgres": "PostgreSQL",
        "mongodb": "MongoDB",
        "redis": "Redis",
        "authentication": "Authentication",
        "oauth": "Authentication",
    }
    for keyword, skill in readme_keywords.items():
        if keyword in readme:
            skills.add(skill)

    return sorted(list(skills))


async def generate_ai_summary(project_data: dict) -> tuple[str, list[str]]:
    """Generate an AI summary and skill mapping.
    
    Returns (summary_text, skill_list).
    If OPENAI_API_KEY is set, uses the API. Otherwise falls back to mock.
    """
    api_key = os.getenv("OPENAI_API_KEY", "")

    # Extract skills (always rule-based for consistency)
    skills = extract_skills_from_project(project_data)

    if api_key:
        try:
            import httpx
            summary = await _call_openai(api_key, project_data)
            return summary, skills
        except Exception as e:
            logger.warning(f"OpenAI call failed, using mock: {e}")

    # Fallback to mock summary
    summary = generate_mock_summary(project_data)
    return summary, skills


async def _call_openai(api_key: str, project_data: dict) -> str:
    """Call OpenAI to generate a project summary."""
    import httpx
    
    name = project_data.get("name", "Unknown")
    desc = project_data.get("description", "")
    languages = list(project_data.get("languages", {}).keys())
    commit_count = project_data.get("commit_count", 0)
    readme_snippet = (project_data.get("readme_content", "") or "")[:2000]

    prompt = f"""Summarize this GitHub project in 2-3 sentences for a recruiter.
Project: {name}
Description: {desc}
Languages: {', '.join(languages)}
Commits: {commit_count}
README excerpt: {readme_snippet}

Be specific about what the project does and what skills it demonstrates. Be concise."""

    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "model": "gpt-3.5-turbo",
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 200,
                "temperature": 0.5,
            },
        )
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"].strip()
