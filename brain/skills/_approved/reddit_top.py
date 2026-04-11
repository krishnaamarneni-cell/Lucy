"""Lucy skill: reddit_top — Top posts from a subreddit."""
import os
import requests
from dotenv import load_dotenv

load_dotenv()

HEADERS = {"User-Agent": "LucyAI/1.0"}


def get_reddit_top(subreddit: str = "popular", limit: int = 10) -> str:
    """Fetch top posts from a subreddit and return markdown-formatted results."""
    try:
        limit = max(1, min(int(limit), 25))
        url = f"https://www.reddit.com/r/{subreddit}/top.json"
        resp = requests.get(url, headers=HEADERS, params={"limit": limit, "t": "day"}, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        posts = data.get("data", {}).get("children", [])
        if not posts:
            return f"No top posts found in r/{subreddit}."

        lines = [f"**Top {len(posts)} posts in r/{subreddit}:**\n"]
        for i, post in enumerate(posts, 1):
            p = post["data"]
            title = p.get("title", "Untitled")
            score = p.get("score", 0)
            author = p.get("author", "unknown")
            num_comments = p.get("num_comments", 0)
            permalink = f"https://reddit.com{p.get('permalink', '')}"
            lines.append(
                f"{i}. **{title}**\n"
                f"   {score} pts | u/{author} | {num_comments} comments\n"
                f"   {permalink}\n"
            )
        return "\n".join(lines)
    except requests.HTTPError as e:
        if e.response is not None and e.response.status_code == 404:
            return f"Error: Subreddit r/{subreddit} not found."
        return f"Error fetching r/{subreddit}: {e}"
    except Exception as e:
        return f"Error: {e}"


TOOL_META = {
    "name": "reddit_top",
    "description": "Top posts from a subreddit",
    "parameters": {
        "type": "object",
        "properties": {
            "subreddit": {
                "type": "string",
                "description": "Subreddit name (without r/ prefix)",
                "default": "popular",
            },
            "limit": {
                "type": "integer",
                "description": "Number of posts to fetch (1-25)",
                "default": 10,
            },
        },
    },
    "function": get_reddit_top,
}
