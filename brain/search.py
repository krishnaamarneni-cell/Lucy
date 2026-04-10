"""
Real-time web search for Lucy using Tavily.

Tavily returns clean, structured results optimized for LLMs.
Free tier: 1,000 searches/month.
"""

import os
from dotenv import load_dotenv

load_dotenv()

_client = None


def _get_client():
    global _client
    if _client is None:
        from tavily import TavilyClient
        key = os.getenv("TAVILY_API_KEY")
        if not key:
            raise ValueError("TAVILY_API_KEY not set in .env")
        _client = TavilyClient(api_key=key)
    return _client


def web_search(query: str, max_results: int = 5) -> str:
    """
    Search the web using Tavily and return clean text results.

    Returns a formatted string of results ready to pass to the LLM.
    """
    try:
        client = _get_client()
        response = client.search(
            query=query,
            max_results=max_results,
            search_depth="basic",
            include_answer=True,
        )

        parts = []

        # Tavily can provide a direct answer
        if response.get("answer"):
            parts.append(f"Answer: {response['answer']}")

        # Individual results
        for i, result in enumerate(response.get("results", []), 1):
            title = result.get("title", "")
            content = result.get("content", "")
            url = result.get("url", "")
            parts.append(f"{i}. {title}: {content[:200]}")

        return "\n".join(parts) if parts else "No results found."

    except Exception as e:
        return f"Search error: {str(e)}"


def needs_search(text: str) -> bool:
    """Check if the user's message needs a web search."""
    t = text.lower()
    triggers = [
        "search for", "look up", "google", "find out",
        "what's happening", "latest news", "current",
        "who is", "what is the price", "stock price",
        "weather in", "score of", "results of",
        "news about", "search", "look up",
        "what happened", "tell me about",
    ]
    return any(trigger in t for trigger in triggers)
