"""Lucy skill: hackernews_top — Top stories from HackerNews"""
import os
import requests
from dotenv import load_dotenv

load_dotenv()

HN_API = "https://hacker-news.firebaseio.com/v0"


def get_top_hn_stories(count: str = "10") -> str:
    """Fetch top HackerNews stories. Returns markdown-formatted list."""
    try:
        num = int(count)
        num = max(1, min(num, 30))

        resp = requests.get(f"{HN_API}/topstories.json", timeout=10)
        resp.raise_for_status()
        story_ids = resp.json()[:num]

        lines = [f"**Top {num} HackerNews Stories**\n"]
        for i, sid in enumerate(story_ids, 1):
            item = requests.get(f"{HN_API}/item/{sid}.json", timeout=10).json()
            title = item.get("title", "Untitled")
            url = item.get("url", f"https://news.ycombinator.com/item?id={sid}")
            score = item.get("score", 0)
            comments = item.get("descendants", 0)
            hn_link = f"https://news.ycombinator.com/item?id={sid}"
            lines.append(
                f"{i}. [{title}]({url})\n"
                f"   {score} points | {comments} comments | [discuss]({hn_link})"
            )

        return "\n".join(lines)
    except Exception as e:
        return f"Error fetching HackerNews stories: {e}"


def main_function(param: str = "10") -> str:
    """Main entry point — returns markdown string."""
    return get_top_hn_stories(param)


TOOL_META = {
    "name": "hackernews_top",
    "description": "Top stories from HackerNews",
    "parameters": {
        "type": "object",
        "properties": {
            "count": {
                "type": "string",
                "description": "Number of top stories to fetch (1-30, default 10)",
            },
        },
    },
    "function": main_function,
}
