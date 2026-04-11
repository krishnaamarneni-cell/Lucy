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
    "linkedin": "https://www.linkedin.com/in/krishnaamarneni/",
    "website": "https://krishna.amarneni.com",
    "email": "krishna.amarneni@gmail.com",
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


# ============================================================================
# PHASE 3: RECRUITER FINDER (Hunter.io + email_finder fallback)
# ============================================================================

def _extract_domain_from_job(job_url: str, job_title: str = "") -> str:
    """Extract company domain from a job URL or title."""
    import re as _re
    from urllib.parse import urlparse
    
    # Extract company from known URL patterns
    parsed = urlparse(job_url)
    host = parsed.netloc.lower()
    
    # LinkedIn: extract from title "at CompanyName"
    if "linkedin.com" in host:
        match = _re.search(r'at-([\w-]+?)(?:-\d|$)', job_url)
        if match:
            return match.group(1).lower().replace("-", "") + ".com"
    
    # IBM, Accenture, Deloitte — company is in the domain
    for known in ["ibm", "accenture", "deloitte", "ey.com", "kpmg", "pwc", "tcs", "infosys", "wipro", "capgemini"]:
        if known in host:
            return known + ".com" if "." not in known else known
    
    # Indeed, Dice, Jobgether, etc — need to pull from job_title
    if job_title:
        # Pattern: "Title at Company" or "Title - Company"
        match = _re.search(r'(?:at|-)\s+([\w\s&]+?)(?:\s+\||\s+-|\s*$|\(|\[)', job_title)
        if match:
            company = match.group(1).strip().lower()
            company = _re.sub(r'[^\w]', '', company)
            if company and len(company) > 2:
                return company + ".com"
    
    return ""


def find_recruiters_for_company(domain: str, company_name: str = "") -> dict:
    """Use Hunter.io to find verified recruiter emails at a company."""
    import os as _os
    import requests as _req
    
    api_key = _os.getenv("HUNTER_API_KEY")
    if not api_key:
        return {"error": "HUNTER_API_KEY not set"}
    
    if not domain:
        return {"error": "No domain to search"}
    
    try:
        # Try domain search first — returns all emails at that domain
        r = _req.get(
            "https://api.hunter.io/v2/domain-search",
            params={
                "domain": domain,
                "api_key": api_key,
                "department": "hr,executive,management",
                "limit": 10,
            },
            timeout=15,
        )
        data = r.json()
        
        if "errors" in data:
            return {"error": data["errors"][0].get("details", "Hunter error")}
        
        emails = data.get("data", {}).get("emails", [])
        if not emails:
            return {"error": f"No recruiters found at {domain}", "company": company_name}
        
        return {
            "domain": domain,
            "company": data.get("data", {}).get("organization", company_name),
            "recruiters": [
                {
                    "email": e["value"],
                    "name": f"{e.get('first_name', '')} {e.get('last_name', '')}".strip() or "Unknown",
                    "position": e.get("position", ""),
                    "confidence": e.get("confidence", 0),
                    "department": e.get("department", ""),
                }
                for e in emails
            ],
        }
    except Exception as e:
        return {"error": f"Hunter API failed: {str(e)}"}


def format_recruiters(result: dict) -> str:
    """Format recruiter results as markdown."""
    if "error" in result:
        return f"❌ {result['error']}"
    
    company = result.get("company", result.get("domain", ""))
    recruiters = result.get("recruiters", [])
    
    if not recruiters:
        return f"No recruiters found at {company}"
    
    lines = [f"# 👥 Recruiters at {company}\n"]
    for i, r in enumerate(recruiters, 1):
        conf = r["confidence"]
        icon = "🟢" if conf >= 90 else "🟡" if conf >= 70 else "⚪"
        lines.append(f"## {i}. {icon} {r['name']}")
        lines.append(f"**Email:** `{r['email']}`")
        if r["position"]:
            lines.append(f"**Role:** {r['position']}")
        lines.append(f"**Confidence:** {conf}%")
        lines.append("")
    
    return "\n".join(lines)


# ============================================================================
# PHASE 4: COVER EMAIL DRAFTER
# ============================================================================

def draft_application_email(
    recruiter_email: str,
    recruiter_name: str = "",
    company: str = "",
    job_title: str = "",
    job_description: str = "",
    job_url: str = "",
) -> dict:
    """Draft a personalized application email using Krishna's CV + job details."""
    cv = _load_cv()
    if not cv:
        return {"error": "CV not found at ~/career-ops/cv.md"}
    
    greeting = f"Hi {recruiter_name.split()[0]}" if recruiter_name else "Hello"
    
    prompt = f"""You are writing a personalized job application email for Krishna.

## Krishna's CV
{cv}

## Job Opportunity
Title: {job_title}
Company: {company}
URL: {job_url}

Job Description:
{job_description[:2500]}

## Format rules (MANDATORY)
- Start with "{greeting},"
- Then a BLANK LINE
- Then paragraph 1 (2-3 sentences): why excited about THIS role
- Then a BLANK LINE
- Then paragraph 2 (2-3 sentences): specific matches to the JD from Krishna's actual experience
- Then a BLANK LINE
- Then paragraph 3 (1-2 sentences): CTA + "I've attached my CV for your review"
- Then a BLANK LINE
- Then this EXACT signature (copy verbatim, do not modify):

Best,
Krishna Amarneni
SAP Functional Consultant
krishna.amarneni@gmail.com | 203-804-9291
LinkedIn: https://www.linkedin.com/in/krishnaamarneni/
Portfolio: https://krishna.amarneni.com

## Content rules
- ONLY use facts and metrics from the CV above. NEVER invent numbers or achievements.
- Reference real past clients (Xiromed, Coca-Cola, PepsiCo) when relevant.
- Under 180 words total.
- Confident, technical, direct tone.
- NO "I believe", "I feel", "To whom it may concern", filler phrases.

Return ONLY valid JSON (preserve newlines in body as \\n):
{{
  "subject": "Short compelling subject line with the job title",
  "body": "Full email with \\n for newlines, including the signature block exactly as shown above"
}}"""
    
    try:
        response = _client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.4,
        )
        text = response.choices[0].message.content.strip()
        text = re.sub(r'^```(?:json)?\s*', '', text)
        text = re.sub(r'\s*```$', '', text)
        draft = json.loads(text)
        return {
            "to": recruiter_email,
            "subject": draft.get("subject", f"Application for {job_title}"),
            "body": draft.get("body", ""),
        }
    except Exception as e:
        return {"error": f"Draft failed: {str(e)}"}


def save_to_gmail_drafts(draft: dict, attach_cv: bool = True, custom_attachment: str = "") -> str:
    """Save the application draft to Gmail with CV attached."""
    if "error" in draft:
        return f"❌ {draft['error']}"
    try:
        from brain.gmail import draft_email_with_attachment
        
        cv_path = custom_attachment
        if not cv_path and attach_cv:
            from pathlib import Path as _P
            candidates = [
                _P.home() / "career-ops" / "cv.pdf",
                _P.home() / "career-ops" / "cv.md",
            ]
            for c_path in candidates:
                if c_path.exists():
                    cv_path = str(c_path)
                    break
        
        result = draft_email_with_attachment(
            draft["to"],
            draft["subject"],
            draft["body"],
            attachment_path=cv_path,
        )
        return f"✅ Draft saved: **{draft['subject']}**\n\nTo: {draft['to']}\n\n---\n\n{draft['body']}\n\n---\n\n{result}"
    except Exception as e:
        return f"❌ Failed to save draft: {str(e)}"



# ============================================================================
# PHASE 4.5: PER-JOB RESUME TAILORING
# ============================================================================

CV_MASTER_PATH = Path.home() / "career-ops" / "cv_master.md"
TAILORED_DIR = Path.home() / "career-ops" / "tailored"


def _load_master_cv() -> str:
    if CV_MASTER_PATH.exists():
        return CV_MASTER_PATH.read_text()
    return _load_cv()  # fallback


def _slug(text: str) -> str:
    import re as _re
    s = _re.sub(r'[^\w\s-]', '', text.lower())
    s = _re.sub(r'[-\s]+', '-', s).strip('-')
    return s[:40]


def tailor_resume(
    job_title: str,
    company: str,
    job_description: str,
) -> dict:
    """Generate a tailored resume markdown + PDF for a specific job."""
    master = _load_master_cv()
    if not master:
        return {"error": "Master CV not found at ~/career-ops/cv_master.md"}
    
    TAILORED_DIR.mkdir(parents=True, exist_ok=True)
    
    prompt = f"""You are tailoring Krishna's SAP resume for a specific job.

## Krishna's Master Resume (use ONLY facts from this)
{master}

## Target Job
Title: {job_title}
Company: {company}

Description:
{job_description[:3000]}

## Your Task
Produce a tailored version of Krishna's resume that emphasizes skills and experience matching THIS job.

MANDATORY HEADER (output EXACTLY this at the very top):
# Krishna Amarneni
**SAP Business Analyst | SAP Master Data Analyst | SAP MM / SD**

📍 New Jersey, USA · 📧 krishna.amarneni@gmail.com · 📞 203-804-9291 · 🔗 LinkedIn: linkedin.com/in/krishnaamarneni · 🌐 krishna.amarneni.com

Then continue with ## Professional Summary, ## Core Skills, etc.

Rules:
1. ONLY use facts, metrics, and experience that appear in the master resume. NEVER invent.
2. Reorder bullets so the most job-relevant ones come first in each role.
3. Rewrite the SUMMARY section to directly target this role (mention specific technologies from the JD).
4. Emphasize keywords from the JD in your bullet phrasing (but don't keyword-stuff).
5. Keep the overall structure: header → summary → core skills → experience → education.
6. INCLUDE ALL EXPERIENCE from master CV. Do NOT drop roles. All 6 companies (Coca-Cola, Xiromed, PepsiCo, DenKen, IFF, SAAS IT) must appear.
7. Keep length similar to the master (do not add content, just reorder/rephrase).
7. Output clean markdown — use # for name, ## for sections, ### for jobs, - for bullets.

Return ONLY the tailored resume in markdown. No preamble, no explanation."""
    
    try:
        response = _client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
        )
        tailored_md = response.choices[0].message.content.strip()
        tailored_md = re.sub(r'^```(?:markdown|md)?\s*', '', tailored_md)
        tailored_md = re.sub(r'\s*```$', '', tailored_md)
        
        # Save md
        slug = _slug(f"{company}-{job_title}")
        md_path = TAILORED_DIR / f"{slug}.md"
        md_path.write_text(tailored_md)
        
        # Generate PDF
        pdf_path = TAILORED_DIR / f"{slug}.pdf"
        try:
            import markdown as _md
            from weasyprint import HTML
            
            # Preprocess: ensure blank line before every list and header
            preprocessed = tailored_md
            preprocessed = re.sub(r'(\n)(#+ )', r'\n\n\2', preprocessed)
            preprocessed = re.sub(r'(\n)([-*] )', r'\n\n\2', preprocessed)
            # Collapse 3+ newlines to 2
            preprocessed = re.sub(r'\n{3,}', '\n\n', preprocessed)
            html_body = _md.markdown(preprocessed, extensions=["extra", "sane_lists", "nl2br"])
            full_html = f"""<!DOCTYPE html><html><head><meta charset="utf-8"><style>
@page {{ margin: 0.5in 0.6in; size: Letter; }}
body {{ font-family: 'Helvetica Neue', 'Arial', sans-serif; font-size: 10pt; line-height: 1.4; color: #222; margin: 0; }}
h1 {{ font-size: 22pt; color: #0b2545; margin: 0 0 2pt 0; font-weight: 800; letter-spacing: 0.3pt; border: none; text-align: center; }}
h1 + p, h1 + ul li {{ text-align: center; font-size: 9.5pt; color: #555; }}
h2 {{ font-size: 11pt; color: #0b2545; margin-top: 14pt; margin-bottom: 5pt; text-transform: uppercase; letter-spacing: 1.2pt; border-bottom: 2pt solid #0b2545; padding-bottom: 3pt; font-weight: 700; }}
h3 {{ font-size: 10.5pt; color: #0b2545; margin-top: 9pt; margin-bottom: 1pt; font-weight: 700; }}
h3 + p {{ font-style: italic; color: #666; font-size: 9pt; margin: 0 0 3pt 0; }}
ul {{ margin: 3pt 0 7pt 0; padding-left: 16pt; }}
li {{ margin-bottom: 3pt; text-align: justify; }}
p {{ margin: 3pt 0; }}
strong {{ color: #0b2545; font-weight: 700; }}
em {{ color: #666; font-style: italic; }}
</style></head><body>{html_body}</body></html>"""
            HTML(string=full_html).write_pdf(str(pdf_path))
        except Exception as e:
            return {"error": f"PDF generation failed: {e}", "md_path": str(md_path)}
        
        return {
            "md_path": str(md_path),
            "pdf_path": str(pdf_path),
            "slug": slug,
            "preview": tailored_md[:600],
        }
    except Exception as e:
        return {"error": f"Tailoring failed: {str(e)}"}



# ============================================================================
# PHASE 5: APPLICATION TRACKER (Google Sheets)
# ============================================================================

APPLICATIONS_CONFIG = Path.home() / "Lucy" / "memory" / "applications_sheet.json"


def _get_or_create_tracker_sheet() -> str:
    """Return the sheet ID for the applications tracker, create if missing."""
    import json as _json
    
    if APPLICATIONS_CONFIG.exists():
        try:
            data = _json.loads(APPLICATIONS_CONFIG.read_text())
            if data.get("sheet_id"):
                return data["sheet_id"]
        except Exception:
            pass
    
    # Create a new sheet
    try:
        from brain.sheets import _get_sheets_service
        service = _get_sheets_service()
        
        body = {
            "properties": {"title": "Lucy Job Applications Tracker"},
            "sheets": [{"properties": {"title": "Applications"}}],
        }
        sheet = service.spreadsheets().create(body=body, fields="spreadsheetId").execute()
        sheet_id = sheet["spreadsheetId"]
        
        # Add headers
        headers = [["Date", "Company", "Job Title", "Match %", "Recruiter", "Email", "Status", "Resume File", "Notes", "Job URL"]]
        service.spreadsheets().values().update(
            spreadsheetId=sheet_id,
            range="Applications!A1:J1",
            valueInputOption="RAW",
            body={"values": headers},
        ).execute()
        
        # Save config
        APPLICATIONS_CONFIG.parent.mkdir(parents=True, exist_ok=True)
        APPLICATIONS_CONFIG.write_text(_json.dumps({
            "sheet_id": sheet_id,
            "url": f"https://docs.google.com/spreadsheets/d/{sheet_id}",
        }, indent=2))
        
        return sheet_id
    except Exception as e:
        print(f"Failed to create tracker sheet: {e}")
        return ""


def log_application(
    company: str,
    job_title: str,
    match_percent: int = 0,
    recruiter_name: str = "",
    recruiter_email: str = "",
    status: str = "draft",
    resume_file: str = "",
    notes: str = "",
    job_url: str = "",
) -> str:
    """Append a new application row to the tracker sheet."""
    from datetime import datetime
    
    sheet_id = _get_or_create_tracker_sheet()
    if not sheet_id:
        return "❌ Could not access tracker sheet"
    
    try:
        from brain.sheets import _get_sheets_service
        service = _get_sheets_service()
        
        row = [[
            datetime.now().strftime("%Y-%m-%d %H:%M"),
            company,
            job_title,
            f"{match_percent}%" if match_percent else "",
            recruiter_name,
            recruiter_email,
            status,
            Path(resume_file).name if resume_file else "",
            notes,
            job_url,
        ]]
        
        service.spreadsheets().values().append(
            spreadsheetId=sheet_id,
            range="Applications!A:J",
            valueInputOption="RAW",
            insertDataOption="INSERT_ROWS",
            body={"values": row},
        ).execute()
        
        url = f"https://docs.google.com/spreadsheets/d/{sheet_id}"
        return f"✅ Logged to tracker: **{company}** - {job_title}\n📊 Sheet: {url}"
    except Exception as e:
        return f"❌ Failed to log: {str(e)}"


def get_tracker_url() -> str:
    """Get the URL of the applications tracker sheet."""
    import json as _json
    if APPLICATIONS_CONFIG.exists():
        try:
            data = _json.loads(APPLICATIONS_CONFIG.read_text())
            return data.get("url", "")
        except Exception:
            pass
    return ""


def list_applications() -> str:
    """List all applications from the tracker sheet."""
    sheet_id = _get_or_create_tracker_sheet()
    if not sheet_id:
        return "❌ No tracker sheet available"
    
    try:
        from brain.sheets import _get_sheets_service
        service = _get_sheets_service()
        
        result = service.spreadsheets().values().get(
            spreadsheetId=sheet_id,
            range="Applications!A2:J",
        ).execute()
        
        rows = result.get("values", [])
        if not rows:
            return "No applications yet. Use `apply_to_job` to start."
        
        lines = [f"# 📊 Applications Tracker ({len(rows)} total)\n"]
        for i, row in enumerate(rows[-10:], 1):
            date = row[0] if len(row) > 0 else ""
            company = row[1] if len(row) > 1 else ""
            title = row[2] if len(row) > 2 else ""
            match = row[3] if len(row) > 3 else ""
            status = row[6] if len(row) > 6 else "draft"
            icon = "📝" if status == "draft" else "📤" if status == "sent" else "💬" if status == "replied" else "🎯"
            lines.append(f"{icon} **{company}** — {title} ({match}) — {status} — {date}")
        
        lines.append(f"\n📊 [Open sheet]({get_tracker_url()})")
        return "\n".join(lines)
    except Exception as e:
        return f"❌ Failed to read tracker: {str(e)}"



# ============================================================================
# PHASE 6A: RECRUITERS DATABASE + BATCH SEND SCHEDULING
# ============================================================================

RECRUITERS_CONFIG = Path.home() / "Lucy" / "memory" / "recruiters_sheet.json"


def _get_or_create_recruiters_sheet() -> str:
    """Create or get the recruiters database sheet."""
    import json as _json
    
    if RECRUITERS_CONFIG.exists():
        try:
            data = _json.loads(RECRUITERS_CONFIG.read_text())
            if data.get("sheet_id"):
                return data["sheet_id"]
        except Exception:
            pass
    
    try:
        from brain.sheets import _get_sheets_service
        service = _get_sheets_service()
        
        body = {
            "properties": {"title": "Lucy Recruiters Database"},
            "sheets": [{"properties": {"title": "Recruiters"}}],
        }
        sheet = service.spreadsheets().create(body=body, fields="spreadsheetId").execute()
        sheet_id = sheet["spreadsheetId"]
        
        headers = [[
            "Name", "Company", "Email", "Role", "Source",
            "Added Date", "Last Contacted", "Status", "Priority", "Notes"
        ]]
        service.spreadsheets().values().update(
            spreadsheetId=sheet_id,
            range="Recruiters!A1:J1",
            valueInputOption="RAW",
            body={"values": headers},
        ).execute()
        
        RECRUITERS_CONFIG.parent.mkdir(parents=True, exist_ok=True)
        RECRUITERS_CONFIG.write_text(_json.dumps({
            "sheet_id": sheet_id,
            "url": f"https://docs.google.com/spreadsheets/d/{sheet_id}",
        }, indent=2))
        
        return sheet_id
    except Exception as e:
        return ""


def add_recruiter(
    name: str,
    company: str,
    email: str,
    role: str = "",
    source: str = "manual",
    priority: str = "medium",
    notes: str = "",
) -> str:
    """Add a recruiter to the database sheet."""
    from datetime import datetime
    
    sheet_id = _get_or_create_recruiters_sheet()
    if not sheet_id:
        return "❌ Could not create recruiters sheet"
    
    try:
        from brain.sheets import _get_sheets_service
        service = _get_sheets_service()
        
        row = [[
            name, company, email, role, source,
            datetime.now().strftime("%Y-%m-%d"),
            "",  # last contacted (empty)
            "new",  # status
            priority,
            notes,
        ]]
        
        service.spreadsheets().values().append(
            spreadsheetId=sheet_id,
            range="Recruiters!A:J",
            valueInputOption="RAW",
            insertDataOption="INSERT_ROWS",
            body={"values": row},
        ).execute()
        
        return f"✅ Added: **{name}** at **{company}** ({email})"
    except Exception as e:
        return f"❌ Failed: {str(e)}"


def import_recruiters_from_hunter(domain: str, company: str = "") -> str:
    """Find recruiters at a company via Hunter.io and add all to the database."""
    result = find_recruiters_for_company(domain, company)
    if "error" in result:
        return f"❌ {result['error']}"
    
    recruiters = result.get("recruiters", [])
    if not recruiters:
        return f"No recruiters found at {domain}"
    
    added = 0
    for r in recruiters:
        if r["confidence"] >= 85:  # only high-confidence
            add_recruiter(
                name=r["name"],
                company=result.get("company", company or domain),
                email=r["email"],
                role=r["position"],
                source=f"hunter.io ({r['confidence']}%)",
                priority="high" if "talent" in r["position"].lower() or "recruit" in r["position"].lower() else "medium",
            )
            added += 1
    
    return f"✅ Added {added} recruiters from {domain} to database"


def list_recruiters(status: str = "all", limit: int = 20) -> str:
    """List recruiters from the database, optionally filtered by status."""
    sheet_id = _get_or_create_recruiters_sheet()
    if not sheet_id:
        return "❌ No recruiters sheet"
    
    try:
        from brain.sheets import _get_sheets_service
        service = _get_sheets_service()
        
        result = service.spreadsheets().values().get(
            spreadsheetId=sheet_id,
            range="Recruiters!A2:J",
        ).execute()
        
        rows = result.get("values", [])
        if not rows:
            return "No recruiters in database yet. Use `import recruiters from [domain]` or `add recruiter` to start."
        
        filtered = rows
        if status != "all":
            filtered = [r for r in rows if len(r) > 7 and r[7] == status]
        
        lines = [f"# 👥 Recruiters Database ({len(filtered)} / {len(rows)} total)\n"]
        for r in filtered[:limit]:
            name = r[0] if len(r) > 0 else ""
            company = r[1] if len(r) > 1 else ""
            email = r[2] if len(r) > 2 else ""
            role = r[3] if len(r) > 3 else ""
            last = r[6] if len(r) > 6 else "never"
            status = r[7] if len(r) > 7 else "new"
            icon = "🆕" if status == "new" else "📤" if status == "contacted" else "💬" if status == "replied" else "⏸️"
            lines.append(f"{icon} **{name}** — {role} at {company} | `{email}` | last: {last or 'never'}")
        
        import json as _json
        url = _json.loads(RECRUITERS_CONFIG.read_text()).get("url", "")
        lines.append(f"\n📊 [Open sheet]({url})")
        return "\n".join(lines)
    except Exception as e:
        return f"❌ Failed: {str(e)}"


def batch_draft_applications(
    job_title: str,
    job_description: str,
    daily_limit: int = 50,
    status_filter: str = "new",
) -> str:
    """
    Batch-create drafts for recruiters in the database.
    Respects daily_limit to stay under Gmail thresholds.
    Marks each recruiter as 'drafted' in the sheet after processing.
    """
    from datetime import datetime
    
    sheet_id = _get_or_create_recruiters_sheet()
    if not sheet_id:
        return "❌ No recruiters sheet"
    
    try:
        from brain.sheets import _get_sheets_service
        service = _get_sheets_service()
        
        # Read all recruiters
        result = service.spreadsheets().values().get(
            spreadsheetId=sheet_id,
            range="Recruiters!A2:J",
        ).execute()
        rows = result.get("values", [])
        
        if not rows:
            return "No recruiters in database"
        
        # Filter by status and limit
        eligible = [(i, r) for i, r in enumerate(rows) if (len(r) > 7 and r[7] == status_filter) or status_filter == "all"]
        batch = eligible[:daily_limit]
        
        if not batch:
            return f"No {status_filter} recruiters to process. All contacted or filter returned empty."
        
        # Generate one tailored resume for this job (reuse for all recruiters — same job)
        from brain.jobs import tailor_resume, draft_application_email, save_to_gmail_drafts
        
        tailor = tailor_resume(job_title, batch[0][1][1] if batch[0][1] else "", job_description)
        if "error" in tailor:
            return f"❌ Tailoring failed: {tailor['error']}"
        
        drafts_created = 0
        today = datetime.now().strftime("%Y-%m-%d")
        
        for idx, recruiter in batch:
            try:
                name = recruiter[0] if len(recruiter) > 0 else ""
                company = recruiter[1] if len(recruiter) > 1 else ""
                email = recruiter[2] if len(recruiter) > 2 else ""
                
                if not email:
                    continue
                
                # Draft personalized email for THIS recruiter
                draft = draft_application_email(
                    recruiter_email=email,
                    recruiter_name=name,
                    company=company,
                    job_title=job_title,
                    job_description=job_description,
                )
                
                save_to_gmail_drafts(draft, custom_attachment=tailor["pdf_path"])
                
                # Update the sheet row: status=drafted, last_contacted=today
                row_num = idx + 2  # +1 for header, +1 for 1-indexed
                service.spreadsheets().values().update(
                    spreadsheetId=sheet_id,
                    range=f"Recruiters!G{row_num}:H{row_num}",
                    valueInputOption="RAW",
                    body={"values": [[today, "drafted"]]},
                ).execute()
                
                drafts_created += 1
            except Exception as e:
                print(f"Failed for {recruiter}: {e}")
        
        return f"✅ Created **{drafts_created} drafts** for {job_title}. Check Gmail drafts. Recruiters marked as 'drafted' in the sheet."
    except Exception as e:
        return f"❌ Batch failed: {str(e)}"



# ============================================================================
# PHASE 6A.5: AUTO-SYNC SENT EMAILS → UPDATE RECRUITER STATUS
# ============================================================================

def sync_sent_emails_to_recruiters() -> str:
    """
    Scan Gmail Sent folder for emails to recruiters in our database.
    Auto-update their status from 'drafted' to 'contacted' with the sent date.
    """
    from datetime import datetime
    import json as _json
    
    sheet_id = _get_or_create_recruiters_sheet()
    if not sheet_id:
        return "❌ No recruiters sheet"
    
    try:
        from brain.sheets import _get_sheets_service
        from brain.google_auth import get_gmail_service
        
        sheets_service = _get_sheets_service()
        gmail_service = get_gmail_service()
        
        # Load all recruiters
        result = sheets_service.spreadsheets().values().get(
            spreadsheetId=sheet_id,
            range="Recruiters!A2:J",
        ).execute()
        rows = result.get("values", [])
        
        if not rows:
            return "No recruiters in database"
        
        # Build email -> (row_index, current_status) map
        recruiters_map = {}
        for i, r in enumerate(rows):
            if len(r) > 2 and r[2]:  # has email
                status = r[7] if len(r) > 7 else "new"
                recruiters_map[r[2].lower()] = (i, status, r[0] if len(r) > 0 else "")
        
        # Search Gmail sent folder for emails to any of these recruiters
        # Use "in:sent" + "to:" query for each batch
        updated = 0
        newly_contacted = []
        
        for email_addr, (row_idx, current_status, name) in recruiters_map.items():
            if current_status == "contacted":
                continue  # already tracked
            
            try:
                # Search sent folder for this specific recruiter
                query = f"in:sent to:{email_addr}"
                results = gmail_service.users().messages().list(
                    userId="me", q=query, maxResults=1,
                ).execute()
                
                messages = results.get("messages", [])
                if messages:
                    # Get the sent date
                    msg = gmail_service.users().messages().get(
                        userId="me", id=messages[0]["id"], format="metadata",
                        metadataHeaders=["Date"],
                    ).execute()
                    
                    # Extract date
                    headers = msg.get("payload", {}).get("headers", [])
                    sent_date = ""
                    for h in headers:
                        if h["name"] == "Date":
                            sent_date = h["value"][:16]  # first 16 chars = day + month
                            break
                    
                    today = datetime.now().strftime("%Y-%m-%d")
                    
                    # Update the sheet
                    row_num = row_idx + 2
                    sheets_service.spreadsheets().values().update(
                        spreadsheetId=sheet_id,
                        range=f"Recruiters!G{row_num}:H{row_num}",
                        valueInputOption="RAW",
                        body={"values": [[today, "contacted"]]},
                    ).execute()
                    
                    updated += 1
                    newly_contacted.append(name)
            except Exception as e:
                continue  # skip failures
        
        if updated == 0:
            return "✅ Sync complete. No new sent emails found to recruiters in database."
        
        lines = [f"✅ **Synced {updated} recruiter(s)** from Gmail Sent folder:\n"]
        for name in newly_contacted[:20]:
            lines.append(f"  - {name} → contacted")
        return "\n".join(lines)
    except Exception as e:
        return f"❌ Sync failed: {str(e)}"
