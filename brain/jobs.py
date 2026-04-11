"""Lucy's job search pipeline - Phase 1: Score jobs against CV."""

import os
import re
import json
from pathlib import Path
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

CV_PATH = Path.home() / "career-ops" / "cv.md"
_client = Groq(api_key=os.getenv("GROQ_API_KEY"))

PROFILE = {
    "target_roles": ["SAP MM", "SAP Ariba", "SAP SD", "Master Data", "MDG"],
    "location": "New Jersey, US",
    "past_clients": ["Xiromed", "Coca-Cola", "PepsiCo"],
}


def _load_cv() -> str:
    return CV_PATH.read_text() if CV_PATH.exists() else ""


def score_job(job_description: str, job_title: str = "", company: str = "") -> dict:
    cv = _load_cv()
    if not cv:
        return {"error": "CV not found at ~/career-ops/cv.md"}
    
    prompt = f"""You are a senior SAP recruiter evaluating fit for Krishna.

## Krishna's Profile
- Target: {', '.join(PROFILE['target_roles'])}
- Location: {PROFILE['location']}
- Past clients: {', '.join(PROFILE['past_clients'])}

## Krishna's CV
{cv}

## Job to Evaluate
Title: {job_title or 'Unknown'}
Company: {company or 'Unknown'}

### Description
{job_description}

Score this job 0-100% honestly. Scoring guide:
- 90-100: Perfect match, apply immediately
- 80-89: Strong match, apply with targeted resume
- 70-79: Good match, apply if other criteria fit
- 60-69: Partial match, consider only if market is quiet
- Below 60: Skip

Return ONLY valid JSON (no markdown, no preamble):
{{
  "match_percent": 85,
  "reasons_for": ["specific match 1", "specific match 2", "specific match 3"],
  "reasons_against": ["concern 1", "concern 2"],
  "recommendation": "Strong fit — apply" or "Partial fit — consider" or "Skip",
  "tailoring_notes": "What to emphasize in cover letter and resume for this role"
}}"""
    
    try:
        response = _client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
        )
        text = response.choices[0].message.content.strip()
        text = re.sub(r'^```(?:json)?\s*', '', text)
        text = re.sub(r'\s*```$', '', text)
        return json.loads(text)
    except json.JSONDecodeError as e:
        return {"error": f"JSON parse failed: {e}", "raw": text[:500]}
    except Exception as e:
        return {"error": f"Scoring failed: {str(e)}"}


def format_score(score: dict) -> str:
    if "error" in score:
        return f"❌ **Error:** {score['error']}"
    
    pct = score.get("match_percent", 0)
    icon = "🔥" if pct >= 85 else "✅" if pct >= 70 else "⚠️" if pct >= 60 else "❌"
    
    lines = [f"# {icon} Match: {pct}%"]
    lines.append(f"**Recommendation:** {score.get('recommendation', '')}")
    
    if score.get("reasons_for"):
        lines.append("\n## ✅ Why it fits")
        for r in score["reasons_for"]:
            lines.append(f"- {r}")
    
    if score.get("reasons_against"):
        lines.append("\n## ⚠️ Concerns")
        for r in score["reasons_against"]:
            lines.append(f"- {r}")
    
    if score.get("tailoring_notes"):
        lines.append(f"\n## 🎯 Tailoring advice\n{score['tailoring_notes']}")
    
    return "\n".join(lines)
"""Phase 2: Job scraper using Tavily."""

import os
import json
import re
from pathlib import Path
from datetime import datetime

import os as _os
from tavily import TavilyClient as _TavilyClient

_tavily = _TavilyClient(api_key=_os.getenv("TAVILY_API_KEY"))


def _tavily_search(query: str, max_results: int = 10) -> dict:
    try:
        return _tavily.search(query=query, max_results=max_results, search_depth="basic")
    except Exception as e:
        return {"error": str(e), "results": []}

SEEN_JOBS_FILE = Path.home() / "Lucy" / "memory" / "seen_jobs.json"


def _load_seen() -> set:
    if SEEN_JOBS_FILE.exists():
        try:
            return set(json.loads(SEEN_JOBS_FILE.read_text()))
        except Exception:
            return set()
    return set()


def _save_seen(seen: set):
    SEEN_JOBS_FILE.parent.mkdir(parents=True, exist_ok=True)
    SEEN_JOBS_FILE.write_text(json.dumps(list(seen), indent=2))


def search_sap_jobs(query: str = None, max_results: int = 10) -> list:
    """Search for individual SAP job postings (not listing pages)."""
    import re as _re
    
    queries = [
        query or "SAP MM Ariba functional consultant contract 2026",
        "SAP S/4HANA consultant contract remote senior",
        "SAP master data governance consultant contract",
    ]
    
    all_jobs = []
    for q in queries[:1 if query else 3]:
        # Target specific job URL patterns, not category pages
        results = _tavily_search(q, max_results=max_results)
        if isinstance(results, dict):
            for r in results.get("results", []):
                url = r.get("url", "")
                # Filter out category/listing pages — only keep actual job posts
                is_job_url = any([
                    "/jobs/view/" in url,  # LinkedIn job posts
                    "/job-detail/" in url,  # Dice
                    "/viewjob?" in url,  # Indeed
                    "/jobs/detail/" in url,
                    _re.search(r'/\d{6,}', url),  # Has numeric job ID
                    _re.search(r'[a-f0-9]{8,}', url.lower()),  # Has hash ID
                ])
                # Skip if it is an obvious listing page
                is_listing = any([
                    url.endswith("/jobs"),
                    "/q-" in url and "-jobs" in url,
                    "?q=" in url and "&" not in url.split("?")[1],
                ])
                
                if is_job_url and not is_listing:
                    all_jobs.append({
                        "title": r.get("title", "Unknown")[:150],
                        "url": url,
                        "snippet": r.get("content", "")[:1500],
                        "source": "tavily",
                    })
    
    # Dedupe by URL
    seen_urls = set()
    unique = []
    for j in all_jobs:
        if j["url"] and j["url"] not in seen_urls:
            seen_urls.add(j["url"])
            unique.append(j)
    
    return unique


def _fetch_job_content(url: str, fallback: str = "") -> str:
    """Fetch full job description from a URL via browser.py."""
    try:
        from brain.browser import fetch_page
        result = fetch_page(url, max_chars=5000)
        if isinstance(result, dict) and result.get("success"):
            content = result.get("text", "")
            title = result.get("title", "")
            if content and len(content) > len(fallback):
                return (title + "\n\n" + content)[:5000]
    except Exception as e:
        print(f"   fetch fail {url[:60]}: {e}")
    return fallback


def find_matching_jobs(min_score: int = 75, max_jobs: int = 10) -> str:
    """Find SAP jobs, fetch each page, score them, return matches above threshold."""
    jobs = search_sap_jobs(max_results=max_jobs)
    
    if not jobs:
        return "No jobs found. Try again later."
    
    seen = _load_seen()
    results = []
    new_count = 0
    
    for job in jobs[:max_jobs]:
        # Skip if we've already seen this URL
        if job["url"] in seen:
            continue
        
        # Fetch full page content for better scoring
        full_content = _fetch_job_content(job["url"], fallback=job["snippet"])
        
        # Score against real content
        score_result = score_job(
            job_description=full_content,
            job_title=job["title"],
            company="",
        )
        
        pct = score_result.get("match_percent", 0)
        
        if pct >= min_score:
            results.append({
                **job,
                "score": pct,
                "recommendation": score_result.get("recommendation", ""),
                "reasons": score_result.get("reasons_for", [])[:2],
            })
        
        seen.add(job["url"])
        new_count += 1
    
    _save_seen(seen)
    
    if not results:
        return f"Scanned {new_count} new jobs. None matched your {min_score}%+ threshold."
    
    # Sort by score
    results.sort(key=lambda x: x["score"], reverse=True)
    
    lines = [f"# 🎯 Found {len(results)} matching jobs ({min_score}%+)\n"]
    for i, r in enumerate(results, 1):
        icon = "🔥" if r["score"] >= 85 else "✅"
        lines.append(f"## {i}. {icon} {r['score']}% — {r['title'][:80]}")
        lines.append(f"**URL:** {r['url']}")
        lines.append(f"**Recommendation:** {r['recommendation']}")
        if r['reasons']:
            lines.append(f"**Why it fits:** {' · '.join(r['reasons'])}")
        lines.append("")
    
    return "\n".join(lines)
