"""Lucy skill: quotable — Random inspirational quotes for morning briefing."""
import os
import requests
from dotenv import load_dotenv

load_dotenv()


def get_random_quote(tag: str = "") -> str:
    """Fetch a random inspirational quote, optionally filtered by tag.

    Args:
        tag: Optional tag to filter quotes (e.g. 'wisdom', 'motivation', 'happiness').

    Returns:
        Markdown-formatted quote string.
    """
    try:
        params = {}
        if tag:
            params["tags"] = tag
        resp = requests.get("https://api.quotable.io/random", params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        content = data["content"]
        author = data["author"]
        tags = ", ".join(data.get("tags", []))
        result = f"> *\"{content}\"*\n>\n> — **{author}**"
        if tags:
            result += f"\n\n`{tags}`"
        return result
    except requests.exceptions.Timeout:
        return "Error: Quote API timed out. Try again shortly."
    except requests.exceptions.ConnectionError:
        return "Error: Could not reach the quote service. Check your connection."
    except Exception as e:
        return f"Error: {str(e)}"


TOOL_META = {
    "name": "quotable",
    "description": "Random inspirational quotes for morning briefing",
    "parameters": {
        "type": "object",
        "properties": {
            "tag": {
                "type": "string",
                "description": "Optional tag to filter quotes (e.g. 'wisdom', 'motivation', 'happiness')",
            },
        },
    },
    "function": get_random_quote,
}
