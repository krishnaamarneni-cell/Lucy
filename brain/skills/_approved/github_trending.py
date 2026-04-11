"""Lucy skill: github_trending — Trending repos on GitHub by language/timeframe."""
import os
from datetime import datetime, timedelta
import requests
from dotenv import load_dotenv

load_dotenv()


def get_trending_repos(language: str = "", timeframe: str = "daily", count: int = 5) -> str:
    """Fetch trending GitHub repositories by language and timeframe.

    Args:
        language: Programming language to filter by (e.g. 'python', 'javascript'). Empty for all.
        timeframe: One of 'daily', 'weekly', 'monthly'. Defaults to 'daily'.
        count: Number of repos to return (1-25). Defaults to 5.

    Returns:
        Markdown-formatted string of trending repositories.
    """
    try:
        count = max(1, min(25, int(count)))

        days_map = {"daily": 1, "weekly": 7, "monthly": 30}
        days = days_map.get(timeframe, 1)
        since_date = (datetime.utcnow() - timedelta(days=days)).strftime("%Y-%m-%d")

        query = f"created:>{since_date}"
        if language:
            query += f" language:{language}"

        params = {
            "q": query,
            "sort": "stars",
            "order": "desc",
            "per_page": count,
        }

        resp = requests.get(
            "https://api.github.com/search/repositories",
            params=params,
            headers={"Accept": "application/vnd.github+json"},
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()

        items = data.get("items", [])
        if not items:
            lang_part = f" for **{language}**" if language else ""
            return f"No trending repos found{lang_part} ({timeframe})."

        lang_label = language.capitalize() if language else "All Languages"
        lines = [f"## Trending Repos — {lang_label} ({timeframe})\n"]

        for i, repo in enumerate(items, 1):
            name = repo["full_name"]
            url = repo["html_url"]
            desc = repo.get("description") or "No description"
            stars = repo["stargazers_count"]
            lang = repo.get("language") or "N/A"

            lines.append(f"**{i}. [{name}]({url})**")
            lines.append(f"   {desc}")
            lines.append(f"   Stars: {stars} | Language: {lang}\n")

        return "\n".join(lines)

    except requests.exceptions.Timeout:
        return "Error: GitHub API timed out. Try again shortly."
    except requests.exceptions.ConnectionError:
        return "Error: Could not reach GitHub. Check your connection."
    except Exception as e:
        return f"Error: {str(e)}"


TOOL_META = {
    "name": "github_trending",
    "description": "Trending repos on GitHub by language/timeframe",
    "parameters": {
        "type": "object",
        "properties": {
            "language": {
                "type": "string",
                "description": "Programming language to filter by (e.g. 'python', 'javascript'). Empty for all.",
            },
            "timeframe": {
                "type": "string",
                "description": "One of 'daily', 'weekly', 'monthly'.",
                "enum": ["daily", "weekly", "monthly"],
            },
            "count": {
                "type": "integer",
                "description": "Number of repos to return (1-25). Defaults to 5.",
            },
        },
    },
    "function": get_trending_repos,
}
