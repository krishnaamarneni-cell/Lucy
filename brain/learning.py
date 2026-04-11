"""
Lucy's learning system.
Queues topics for overnight research, builds a permanent knowledge base.
"""

import json
import subprocess
import time
from pathlib import Path
from datetime import datetime

QUEUE_FILE = Path.home() / "Lucy" / "memory" / "learning_queue.json"
KNOWLEDGE_FILE = Path.home() / "Lucy" / "memory" / "knowledge.md"
PROGRESS_FILE = Path.home() / "Lucy" / "memory" / "learning_progress.json"


def _load_queue() -> list:
    if QUEUE_FILE.exists():
        try:
            return json.loads(QUEUE_FILE.read_text())
        except Exception:
            return []
    return []


def _save_queue(queue: list):
    QUEUE_FILE.parent.mkdir(parents=True, exist_ok=True)
    QUEUE_FILE.write_text(json.dumps(queue, indent=2))


def add_topic(topic: str, category: str = "general") -> str:
    queue = _load_queue()
    item = {
        "id": len(queue) + 1,
        "topic": topic,
        "category": category,
        "status": "pending",
        "added": datetime.now().isoformat(),
    }
    queue.append(item)
    _save_queue(queue)
    return f"📚 Added to learning queue: **{topic}** ({category})"


def list_queue() -> str:
    queue = _load_queue()
    if not queue:
        return "Learning queue is empty."
    
    pending = [q for q in queue if q["status"] == "pending"]
    done = [q for q in queue if q["status"] == "completed"]
    
    lines = [f"**Learning queue:** {len(pending)} pending, {len(done)} completed\n"]
    
    if pending:
        lines.append("**Pending:**")
        for q in pending[:20]:
            lines.append(f"- #{q['id']} [{q['category']}] {q['topic']}")
    
    if done:
        lines.append(f"\n**Completed:** {len(done)} topics learned")
    
    return "\n".join(lines)


def research_topic(topic: str, category: str = "general") -> str:
    """Ask Claude Code mentor to research a topic and return findings."""
    from brain.mentor import ask_mentor
    
    prompt = (
        f"Research this topic and give me a comprehensive but concise answer: {topic}\n\n"
        f"Category: {category}\n"
        f"Format the answer as markdown with:\n"
        f"- A clear heading\n"
        f"- 5-10 bullet points of key facts\n"
        f"- Real examples where applicable\n"
        f"- Why it matters for someone learning this topic\n"
        f"Keep it under 500 words. Focus on actionable, memorable information."
    )
    
    result = ask_mentor(prompt)
    # Extract the output from the dict
    if isinstance(result, dict):
        if result.get("success"):
            return result.get("output", "")
        else:
            return f"Error: {result.get('error', 'unknown')}"
    return str(result)


LOG_FILE = Path.home() / "Lucy" / "memory" / "learning_log.txt"


def _log(msg: str):
    """Append to learning log with timestamp."""
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with LOG_FILE.open("a") as f:
        f.write(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}\n")


def process_queue(max_items: int = 30) -> str:
    """Process pending topics in the queue. Designed to run overnight."""
    queue = _load_queue()
    pending = [q for q in queue if q["status"] == "pending"]
    
    if not pending:
        return "No pending topics to research."
    
    _log(f"=== Starting learning session: {len(pending)} topics ===")
    
    KNOWLEDGE_FILE.parent.mkdir(parents=True, exist_ok=True)
    
    # Initialize knowledge file if empty
    if not KNOWLEDGE_FILE.exists():
        KNOWLEDGE_FILE.write_text("# Lucy's Knowledge Base\n\n*Learned topics, organized by category.*\n\n")
    
    processed = 0
    for item in pending[:max_items]:
        try:
            _log(f"📚 [{processed+1}/{min(len(pending), max_items)}] Asking mentor about: {item['topic']}")
            print(f"📚 Learning: {item['topic']}")
            start = time.time()
            answer = research_topic(item["topic"], item["category"])
            duration = time.time() - start
            _log(f"   ✅ Got {len(answer)} chars from mentor in {duration:.1f}s")
            
            # Append to knowledge file
            with KNOWLEDGE_FILE.open("a") as f:
                f.write(f"\n---\n\n## {item['topic']}\n")
                f.write(f"*Category: {item['category']} · Learned: {datetime.now().strftime('%Y-%m-%d %H:%M')}*\n\n")
                f.write(answer)
                f.write("\n\n")
            
            item["status"] = "completed"
            item["completed_at"] = datetime.now().isoformat()
            processed += 1
            _save_queue(queue)  # Save after each item
            
            # Small delay to avoid hammering the API
            time.sleep(2)
            
        except Exception as e:
            item["status"] = "failed"
            item["error"] = str(e)
            _save_queue(queue)
    
    return f"✅ Researched {processed} topics. Knowledge saved to ~/Lucy/memory/knowledge.md"


def search_knowledge(query: str) -> str:
    """Search Lucy's knowledge base for a topic."""
    if not KNOWLEDGE_FILE.exists():
        return "Knowledge base is empty. Add topics and run overnight learning first."
    
    content = KNOWLEDGE_FILE.read_text()
    
    # Simple keyword search
    sections = content.split("---")
    matches = []
    query_lower = query.lower()
    
    for section in sections:
        if query_lower in section.lower():
            matches.append(section.strip())
    
    if not matches:
        return f"Nothing in my knowledge base about '{query}' yet. Want me to learn it?"
    
    return "\n\n---\n\n".join(matches[:3])


# Predefined curriculums
CURRICULUMS = {
    "sap": [
        ("SAP S/4HANA core architecture and modules", "sap"),
        ("SAP MM full lifecycle from PR to payment", "sap"),
        ("SAP SD order to cash process flow", "sap"),
        ("SAP Ariba Buying vs Sourcing vs Contracts differences", "sap"),
        ("SAP Master Data Governance (MDG) overview", "sap"),
        ("S/4HANA migration strategies - greenfield vs brownfield vs bluefield", "sap"),
        ("SAP Fiori apps and UX5 framework", "sap"),
        ("SAP Business Technology Platform (BTP) services", "sap"),
        ("SAP EWM vs WM differences and when to use which", "sap"),
        ("SAP IBP (Integrated Business Planning) capabilities", "sap"),
    ],
    "python": [
        ("Python async/await patterns and asyncio", "python"),
        ("Python decorators and when to use them", "python"),
        ("Python type hints and mypy best practices", "python"),
        ("FastAPI vs Flask vs Django for modern APIs", "python"),
        ("Python virtual environments and dependency management", "python"),
        ("Python multiprocessing vs multithreading vs async", "python"),
        ("Python testing with pytest and fixtures", "python"),
        ("Python dataclasses and Pydantic for validation", "python"),
    ],
    "culture": [
        ("Andhra Pradesh culture, food, and traditions", "culture"),
        ("Guntur district - history, geography, famous for", "culture"),
        ("Telugu language basics - greetings, common phrases, grammar", "culture"),
        ("Chennai culture and Tamil traditions", "culture"),
        ("Major festivals in Andhra Pradesh - Sankranti, Ugadi, Dussehra", "culture"),
        ("Telugu cinema (Tollywood) - history and major figures", "culture"),
        ("Andhra cuisine - signature dishes and regional variations", "culture"),
    ],
    "self_improvement": [
        ("Deep work by Cal Newport - key principles", "self_improvement"),
        ("Atomic Habits by James Clear - core concepts", "self_improvement"),
        ("First principles thinking explained with examples", "self_improvement"),
        ("Ray Dalio's principles for life and decision making", "self_improvement"),
        ("How to have high-quality productive conversations", "self_improvement"),
        ("Stoicism basics - Marcus Aurelius and Epictetus", "self_improvement"),
        ("Building a second brain - Tiago Forte's method", "self_improvement"),
    ],
}


def load_curriculum(name: str) -> str:
    if name not in CURRICULUMS:
        available = ", ".join(CURRICULUMS.keys())
        return f"Unknown curriculum. Available: {available}"
    
    for topic, category in CURRICULUMS[name]:
        add_topic(topic, category)
    
    return f"📚 Loaded {len(CURRICULUMS[name])} topics from the **{name}** curriculum."


LEARNING_TRIGGERS = [
    "learn about", "research this", "study this",
    "add to learning", "learn while i sleep", "overnight learning",
    "learning queue", "what have you learned", "knowledge base",
    "load curriculum", "start learning",
]


def needs_learning(text: str) -> bool:
    t = text.lower()
    return any(trigger in t for trigger in LEARNING_TRIGGERS)


def handle_learning(text: str) -> str:
    t = text.lower()
    
    if "load" in t and "curriculum" in t:
        for name in CURRICULUMS.keys():
            if name in t:
                return load_curriculum(name)
        return f"Which curriculum? Available: {', '.join(CURRICULUMS.keys())}"
    
    if "queue" in t or "what's pending" in t or "what have you learned" in t:
        return list_queue()
    
    if "start learning" in t or "learn while i sleep" in t or "research all" in t:
        return process_queue()
    
    if "knowledge" in t:
        query = text.replace("knowledge", "").replace("search", "").strip()
        if query:
            return search_knowledge(query)
        return list_queue()
    
    # Add topic to queue
    topic = text
    for prefix in ["learn about ", "research ", "study ", "add to learning "]:
        if prefix in t:
            topic = text[t.index(prefix) + len(prefix):].strip()
            break
    
    if topic:
        return add_topic(topic, "general")
    
    return "Tell me what to learn. Examples:\n- 'learn about SAP HANA architecture'\n- 'load SAP curriculum'\n- 'show learning queue'"
