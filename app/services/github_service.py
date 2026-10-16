"""SkillProof - GitHub REST API service.

Fetches public repo data: repos, languages, commits, README.
Uses GITHUB_TOKEN from env if available (raises rate limit from 60→5000/hr).
"""
import httpx
import os
import logging
from typing import Optional
from collections import defaultdict
from datetime import datetime

logger = logging.getLogger(__name__)

GITHUB_API = "https://api.github.com"
TIMEOUT = 15.0


def _headers() -> dict:
    """Build request headers, including auth token if available."""
    h = {"Accept": "application/vnd.github.v3+json", "User-Agent": "SkillProof/1.0"}
    token = os.getenv("GITHUB_TOKEN", "")
    if token:
        h["Authorization"] = f"token {token}"
    return h


class GitHubRateLimitException(Exception):
    """Raised when GitHub API quota/rate limit is reached."""
    def __init__(self, reset_time: str = "", message: str = ""):
        self.reset_time = reset_time
        super().__init__(message or f"GitHub API rate limit exceeded. Resets at {reset_time}.")


async def _get(url: str, params: dict | None = None) -> dict | list | None:
    """Make a GET request to GitHub API with error handling."""
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        try:
            resp = await client.get(url, headers=_headers(), params=params)
            if resp.status_code == 403:
                reset_ts = resp.headers.get("X-RateLimit-Reset", 0)
                reset_dt = ""
                if reset_ts:
                    try:
                        reset_dt = datetime.fromtimestamp(int(reset_ts)).strftime("%H:%M:%S UTC")
                    except Exception:
                        pass
                logger.warning(f"GitHub rate limited. Resets at: {reset_dt}")
                raise GitHubRateLimitException(reset_time=reset_dt)
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            return resp.json()
        except GitHubRateLimitException:
            raise
        except httpx.HTTPStatusError as e:
            logger.error(f"GitHub API error: {e}")
            return None
        except httpx.RequestError as e:
            logger.error(f"GitHub request error: {e}")
            return None


async def fetch_rate_limit() -> dict:
    """Fetch current GitHub API rate limit status."""
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        try:
            resp = await client.get(f"{GITHUB_API}/rate_limit", headers=_headers())
            if resp.status_code == 200:
                data = resp.json()
                core = data.get("resources", {}).get("core", {})
                reset_ts = core.get("reset", 0)
                reset_dt = datetime.fromtimestamp(reset_ts).strftime("%H:%M:%S UTC") if reset_ts else "Unknown"
                return {
                    "limit": core.get("limit", 60),
                    "remaining": core.get("remaining", 60),
                    "reset_timestamp": reset_ts,
                    "reset_formatted": reset_dt,
                    "authenticated": bool(os.getenv("GITHUB_TOKEN")),
                    "status": "ok",
                }
            return {
                "limit": 60,
                "remaining": 0,
                "reset_timestamp": 0,
                "reset_formatted": "Exceeded",
                "authenticated": bool(os.getenv("GITHUB_TOKEN")),
                "status": "rate_limited",
            }
        except Exception as e:
            logger.warning(f"Failed to query GitHub rate limit: {e}")
            return {
                "limit": 60,
                "remaining": 60,
                "reset_timestamp": 0,
                "reset_formatted": "Unknown",
                "authenticated": bool(os.getenv("GITHUB_TOKEN")),
                "status": "unavailable",
            }


async def fetch_user_repos(username: str) -> Optional[list[dict]]:
    """Fetch all public repositories for a GitHub user."""
    repos = []
    page = 1
    while True:
        data = await _get(
            f"{GITHUB_API}/users/{username}/repos",
            params={"per_page": 100, "page": page, "sort": "updated", "type": "owner"},
        )
        if data is None and page == 1:
            return None
        if not data or not isinstance(data, list):
            break
        repos.extend(data)
        if len(data) < 100:
            break
        page += 1
    return repos


def _clean_repo_name(repo: str) -> str:
    """Sanitize repository name, stripping .git suffix and slashes."""
    r = (repo or "").strip().rstrip("/")
    if r.endswith(".git"):
        r = r[:-4]
    return r


async def fetch_repo_details(owner: str, repo: str) -> Optional[dict]:
    """Fetch detailed info for a single repository."""
    repo = _clean_repo_name(repo)
    return await _get(f"{GITHUB_API}/repos/{owner}/{repo}")


async def fetch_repo_languages(owner: str, repo: str) -> dict:
    """Fetch language breakdown for a repo."""
    repo = _clean_repo_name(repo)
    data = await _get(f"{GITHUB_API}/repos/{owner}/{repo}/languages")
    return data if isinstance(data, dict) else {}


async def fetch_repo_commits(owner: str, repo: str, max_pages: int = 1) -> list[dict]:
    """Fetch recent commits for a repo (up to max_pages * 100)."""
    repo = _clean_repo_name(repo)
    commits = []
    for page in range(1, max_pages + 1):
        data = await _get(
            f"{GITHUB_API}/repos/{owner}/{repo}/commits",
            params={"per_page": 100, "page": page},
        )
        if not data or not isinstance(data, list):
            break
        commits.extend(data)
        if len(data) < 100:
            break
    return commits


async def fetch_readme(owner: str, repo: str) -> str:
    """Fetch the README content (decoded)."""
    import base64
    repo = _clean_repo_name(repo)
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        try:
            resp = await client.get(
                f"{GITHUB_API}/repos/{owner}/{repo}/readme",
                headers=_headers(),
            )
            if resp.status_code != 200:
                return ""
            data = resp.json()
            content = data.get("content", "")
            encoding = data.get("encoding", "base64")
            if encoding == "base64" and content:
                return base64.b64decode(content).decode("utf-8", errors="replace")
            return content
        except Exception:
            return ""


async def fetch_repo_contents(owner: str, repo: str, path: str = "") -> list[dict]:
    """Fetch repo file tree (top-level) to estimate file count."""
    repo = _clean_repo_name(repo)
    data = await _get(f"{GITHUB_API}/repos/{owner}/{repo}/contents/{path}")
    return data if isinstance(data, list) else []


def build_commit_timeline(commits: list[dict]) -> list[dict]:
    """Group commits by month to build a timeline."""
    monthly = defaultdict(int)
    for c in commits:
        commit_data = c.get("commit", {})
        author = commit_data.get("author", {}) or {}
        date_str = author.get("date", "")
        if date_str:
            try:
                dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                key = dt.strftime("%Y-%m")
                monthly[key] += 1
            except ValueError:
                continue
    # Sort by month
    sorted_months = sorted(monthly.items())
    return [{"month": m, "count": c} for m, c in sorted_months]


def detect_anti_gaming(repo_data: dict, commits: list[dict], is_fork: bool) -> list[str]:
    """Detect potential gaming patterns. Returns a list of warning flags."""
    flags = []

    # Flag 1: Fork with no original commits
    if is_fork:
        # Check if commits are from the repo owner
        owner = repo_data.get("owner", {}).get("login", "")
        owner_commits = sum(
            1 for c in commits
            if c.get("author", {}) and c["author"].get("login", "") == owner
        )
        if owner_commits == 0:
            flags.append("Fork with no original commits — likely not the student's own work")
        elif owner_commits < 3:
            flags.append(f"Fork with only {owner_commits} original commit(s) — minimal contribution")

    # Flag 2: Single-day commit dump
    if commits:
        dates = set()
        for c in commits:
            commit_data = c.get("commit", {})
            author = commit_data.get("author", {}) or {}
            date_str = author.get("date", "")
            if date_str:
                try:
                    dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                    dates.add(dt.strftime("%Y-%m-%d"))
                except ValueError:
                    continue
        if len(commits) > 10 and len(dates) <= 1:
            flags.append(f"All {len(commits)} commits on a single day — possible commit dump")
        elif len(commits) > 20 and len(dates) <= 2:
            flags.append(f"{len(commits)} commits across only {len(dates)} days — suspiciously concentrated")

    return flags


async def import_full_repo(owner: str, repo_name: str) -> dict:
    """Import all data for a single repo. Returns a dict ready to create a Project."""
    repo_data = await fetch_repo_details(owner, repo_name)
    if not repo_data:
        return None

    languages = await fetch_repo_languages(owner, repo_name)
    commits = await fetch_repo_commits(owner, repo_name)
    readme = await fetch_readme(owner, repo_name)
    contents = await fetch_repo_contents(owner, repo_name)

    timeline = build_commit_timeline(commits)
    is_fork = repo_data.get("fork", False)
    flags = detect_anti_gaming(repo_data, commits, is_fork)

    # Commit dates
    first_date = ""
    last_date = ""
    if commits:
        dates = []
        for c in commits:
            cd = c.get("commit", {}).get("author", {}) or {}
            d = cd.get("date", "")
            if d:
                dates.append(d)
        if dates:
            first_date = min(dates)
            last_date = max(dates)

    return {
        "github_repo_url": repo_data.get("html_url", ""),
        "name": repo_data.get("name", repo_name),
        "description": repo_data.get("description", "") or "",
        "languages": languages,
        "topics": repo_data.get("topics", []),
        "commit_count": len(commits),
        "first_commit_date": first_date,
        "last_commit_date": last_date,
        "commit_timeline": timeline,
        "readme_content": readme,
        "readme_length": len(readme),
        "is_fork": is_fork,
        "has_original_commits": not is_fork or any(
            c.get("author", {}) and c["author"].get("login", "") == owner
            for c in commits
        ),
        "star_count": repo_data.get("stargazers_count", 0),
        "file_count": len(contents),
        "repo_size_kb": repo_data.get("size", 0),
        "anti_gaming_flags": flags,
    }
