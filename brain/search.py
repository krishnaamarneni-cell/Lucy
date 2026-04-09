from ddgs import DDGS

def web_search(query, max_results=3):
    results = DDGS().text(query, max_results=max_results)
    if not results:
        return "No results found."
    summary = ""
    for r in results:
        summary += f"- {r['title']}: {r['body']}\n"
    return summary
