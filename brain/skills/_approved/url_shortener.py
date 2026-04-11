"""Lucy skill: url_shortener — Free URL shortener via is.gd"""
import os
import requests
from dotenv import load_dotenv

load_dotenv()


def shorten_url(url: str = "") -> str:
    """Shorten a URL using the is.gd service. Returns markdown string."""
    try:
        if not url:
            return "Error: please provide a URL to shorten."

        resp = requests.get(
            "https://is.gd/create.php",
            params={"format": "simple", "url": url},
            timeout=10,
        )

        if resp.status_code != 200:
            return f"Error: is.gd returned status {resp.status_code}."

        short = resp.text.strip()

        if short.startswith("Error:"):
            return short

        return f"**Shortened URL**\n\n{url} → {short}"

    except Exception as e:
        return f"Error: {str(e)}"


TOOL_META = {
    "name": "url_shortener",
    "description": "Free URL shortener via is.gd",
    "parameters": {
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "The URL to shorten",
            },
        },
        "required": ["url"],
    },
    "function": shorten_url,
}
