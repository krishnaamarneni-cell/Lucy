"""
Lucy's browser tool.
Fetches web pages and extracts readable text content.
Used by Goose agent and directly by Lucy for "go to" / "read this site" commands.
"""

import re
import requests
from bs4 import BeautifulSoup


# Known sites — Lucy recognizes these by name
# Known sites — Lucy recognizes these by name
# Order matters: more specific matches first
KNOWN_SITES_CONTEXTUAL = [
    # WealthClaude subpages
    (["wealthclaude news", "wealthclaude latest news", "wealth claude news"], "https://wealthclaude.com/news"),
    (["wealthclaude blog", "wealthclaude latest blog", "wealth claude blog"], "https://wealthclaude.com/blog"),
    (["wealthclaude globe", "wealth claude globe"], "https://wealthclaude.com/globe"),
    # North Falmouth subpages
    (["pharmacy blog", "nfpltc blog", "north falmouth blog"], "https://nfpltc.com/blog"),
    (["pharmacy news", "north falmouth news"], "https://nfpltc.com/news"),
]

KNOWN_SITES = {
    "wealthclaude": "https://wealthclaude.com",
    "wealth claude": "https://wealthclaude.com",
    "north falmouth": "https://nfpltc.com",
    "pharmacy": "https://nfpltc.com",
    "nfpltc": "https://nfpltc.com",
    "saint francis": "https://saintfrancismedical.com",
    "saint francis medical": "https://saintfrancismedical.com",
    "hacker news": "https://news.ycombinator.com",
    "hackernews": "https://news.ycombinator.com",
    "github": "https://github.com/krishnaamarneni-cell",
    "my github": "https://github.com/krishnaamarneni-cell",
    "lucy repo": "https://github.com/krishnaamarneni-cell/Lucy",
    "reddit": "https://reddit.com",
    "product hunt": "https://producthunt.com",
    "linkedin": "https://linkedin.com",
}


def resolve_site(text: str) -> str | None:
    if text.lower().strip().startswith("mentor"):
        return None
    """Try to find a known site name in the text."""
    t = text.lower()
    
    # Check contextual matches first (more specific)
    for triggers, url in KNOWN_SITES_CONTEXTUAL:
        if any(trigger in t for trigger in triggers):
            return url
    
    # Then check base sites
    for name, url in KNOWN_SITES.items():
        if name in t:
            # If user says "news" or "blog", try appending the path
            if "news" in t or "latest" in t:
                return url + "/news"
            if "blog" in t:
                return url + "/blog"
            return url
    return None


def fetch_page(url: str, max_chars: int = 3000) -> dict:
    """
    Fetch a web page and extract readable text.
    Returns dict with success, title, text, url.
    """
    if not url.startswith("http"):
        url = "https://" + url

    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")

        # Remove script and style elements
        for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
            tag.decompose()

        title = soup.title.string.strip() if soup.title and soup.title.string else ""

        # Extract text
        text = soup.get_text(separator="\n", strip=True)

        # Clean up whitespace
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        text = "\n".join(lines)

        # Truncate
        if len(text) > max_chars:
            text = text[:max_chars] + "\n\n[Content truncated...]"

        return {
            "success": True,
            "title": title,
            "text": text,
            "url": url,
        }

    except requests.exceptions.ConnectionError:
        return {"success": False, "title": "", "text": f"Could not connect to {url}", "url": url}
    except requests.exceptions.Timeout:
        return {"success": False, "title": "", "text": f"Timeout loading {url}", "url": url}
    except Exception as e:
        return {"success": False, "title": "", "text": f"Error: {str(e)}", "url": url}


def format_page_for_llm(result: dict) -> str:
    """Format fetched page content for LLM consumption."""
    if not result["success"]:
        return result["text"]

    parts = []
    if result["title"]:
        parts.append(f"**{result['title']}**")
        parts.append(f"*{result['url']}*")
        parts.append("")
    parts.append(result["text"])
    return "\n".join(parts)


def summarize_page(url: str, task_hint: str = "") -> str:
    """Fetch a page and return a clean, formatted summary via LLM."""
    import os
    from groq import Groq
    from dotenv import load_dotenv
    load_dotenv()
    
    # Fetch more content for list/news requests
    task_lower = task_hint.lower() if task_hint else ""
    if any(w in task_lower for w in ["top 10", "top 5", "top 20", "list", "all news", "headlines"]):
        max_fetch = 8000
    else:
        max_fetch = 4000
    result = fetch_page(url, max_chars=max_fetch)
    if not result["success"]:
        return result["text"]
    
    client = Groq(api_key=os.getenv("GROQ_API_KEY"))
    
    # Detect if user wants a list or detailed response
    task_lower = task_hint.lower() if task_hint else ""
    wants_list = any(w in task_lower for w in ["top 10", "top 5", "top 20", "list", "all news", "headlines", "stories"])
    wants_detail = any(w in task_lower for w in ["detail", "explain", "full", "everything"])
    
    if wants_list:
        format_instructions = (
            f"Extract ALL distinct news stories/headlines from this page.\n"
            f"FORMAT RULES:\n"
            f"- First line: ## followed by a short title like 'CNBC Top Headlines'\n"
            f"- One blank line, then list EVERY news story as a numbered item\n"
            f"- Format: 1. **Headline** — brief 1-sentence summary\n"
            f"- Include at least 10 items if available\n"
            f"- NEVER use === or --- underlines\n"
        )
    else:
        format_instructions = (
            f"FORMAT RULES (follow exactly):\n"
            f"- First line: ## followed by the page title (use ## not underlines)\n"
            f"- One blank line, then a 1-2 sentence overview\n"
            f"- Then a blank line and **Key Points** as a bold label\n"
            f"- Use - for bullet points (not *)\n"
            f"- Use **bold** for important terms in bullets\n"
            f"- Max 10 bullet points, each 1 sentence\n"
            f"- NEVER use === or --- underlines for headings\n"
        )
    
    prompt = (
        f"Summarize this web page clearly and concisely.\n\n"
        f"Page: {result['url']}\n"
        f"Title: {result['title']}\n\n"
        f"{result['text']}\n\n"
        f"{format_instructions}"
    )
    
    try:
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": prompt}],
        )
        text = response.choices[0].message.content.strip()
        # Clean up any setext-style headings (=== or ---)
        import re as _re
        text = _re.sub(r"\n[=]{2,}\n", "\n", text)
        text = _re.sub(r"\n[-]{2,}\n", "\n", text)
        text = _re.sub(r"^[=]{2,}$", "", text, flags=_re.MULTILINE)
        text = _re.sub(r"^[-]{3,}$", "", text, flags=_re.MULTILINE)
        return text.strip()
    except Exception:
        return format_page_for_llm(result)
