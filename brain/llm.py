import os
from groq import Groq
from dotenv import load_dotenv
from brain.search import web_search
from brain.memory import load_memory, save_memory, get_context, add_fact
from brain.tools import get_datetime
from brain.weather import get_weather
from brain.reminders import add_reminder
from brain.volume import handle_volume

load_dotenv()
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

SEARCH_TRIGGERS = ["latest", "news", "score", "price", "who won", "stock"]
PERSONAL_QUESTIONS = ["my name", "my age", "i told you", "do you remember", "you know me"]
TIME_TRIGGERS = ["what time", "what's the time", "what day", "what date",
                 "what is the date", "what is the time", "today's date",
                 "current time", "time is it", "day is it", "date is it",
                 "date today", "time check", "right now"]
WEATHER_TRIGGERS = ["weather", "temperature", "how hot", "how cold", "forecast", "raining", "snowing"]
REMINDER_TRIGGERS = ["remind me", "set a reminder", "reminder at", "alert me"]
FACT_TRIGGERS = ["remember that", "remember i", "don't forget", "keep in mind",
                 "note that", "i want you to know", "my favorite", "i like",
                 "i hate", "i love", "i always", "i never"]
VOLUME_TRIGGERS = ["volume up", "volume down", "turn up", "turn down", "louder",
                   "quieter", "mute", "unmute", "set volume", "volume to",
                   "current volume", "how loud", "silence", "raise volume",
                   "lower volume", "increase volume", "decrease volume"]
QUESTION_STARTERS = ["do you", "what do", "can you", "did you", "will you",
                     "have you", "are you", "who ", "what ", "when ", "where ",
                     "why ", "how ", "is ", "was ", "tell me"]

def is_question(text):
    t = text.lower().strip()
    return t.endswith("?") or any(t.startswith(q) for q in QUESTION_STARTERS)

def needs_time(text): return any(t in text.lower() for t in TIME_TRIGGERS)
def needs_weather(text): return any(t in text.lower() for t in WEATHER_TRIGGERS)
def needs_reminder(text): return any(t in text.lower() for t in REMINDER_TRIGGERS)
def needs_volume(text): return any(t in text.lower() for t in VOLUME_TRIGGERS)
def needs_fact(text):
    if is_question(text): return False
    return any(t in text.lower() for t in FACT_TRIGGERS)
def needs_search(text):
    t = text.lower()
    if any(p in t for p in PERSONAL_QUESTIONS + TIME_TRIGGERS + WEATHER_TRIGGERS + REMINDER_TRIGGERS + FACT_TRIGGERS + VOLUME_TRIGGERS):
        return False
    return any(trigger in t for trigger in SEARCH_TRIGGERS)

def extract_fact(text):
    lower = text.lower()
    for phrase in ["remember that ", "remember ", "don't forget that ",
                   "don't forget ", "note that ", "keep in mind that ",
                   "i want you to know that ", "i want you to know "]:
        if lower.startswith(phrase):
            return text[len(phrase):].strip()
    return text.strip()


def get_time_context():
    """Return a dict with current hour and a natural time-of-day label."""
    from datetime import datetime
    now = datetime.now()
    hour = now.hour
    if 5 <= hour < 12:
        period = "morning"
    elif 12 <= hour < 17:
        period = "afternoon"
    elif 17 <= hour < 22:
        period = "evening"
    else:
        period = "late night"
    return {
        "hour": hour,
        "period": period,
        "time_str": now.strftime("%I:%M %p").lstrip("0"),
        "day_str": now.strftime("%A"),
    }


# --- Mentor (Claude Code) routing ---
MENTOR_TRIGGERS = [
    "ask claude code",
    "ask your mentor",
    "use claude code",
    "use your mentor",
    "ask claude",
    "mentor,",
    "mentor ",
    "claude code,",
    "hey claude code",
]

MENTOR_TASK_PREFIXES = [
    "write code to",
    "write a script to",
    "write a script that",
    "write python to",
    "build a script",
    "build me a script",
    "code a function",
    "can you code",
    "create a script",
]


def needs_mentor(text):
    t = text.lower()
    if any(trig in t for trig in MENTOR_TRIGGERS):
        return True
    # Prefixes can appear anywhere in the sentence, not just at the start
    if any(prefix in t for prefix in MENTOR_TASK_PREFIXES):
        return True
    return False


def extract_mentor_task(text):
    """Strip trigger words from the user's request so the mentor sees a clean task."""
    t = text.strip()
    lower = t.lower()

    # First try explicit trigger phrases
    for trig in MENTOR_TRIGGERS:
        if trig in lower:
            idx = lower.index(trig)
            t = t[idx + len(trig):].lstrip(" ,:-")
            return t or text

    # Then try task prefixes — keep from the prefix onward
    for prefix in MENTOR_TASK_PREFIXES:
        if prefix in lower:
            idx = lower.index(prefix)
            t = t[idx:]
            return t or text

    return t or text



# ---------------------------------------------------------------------------
# Streaming support — yields sentences as Groq generates them.
# Used by voice/tts.py's speak_stream() to eliminate dead air.
# ---------------------------------------------------------------------------

_SENTENCE_END = (".", "!", "?")
# Common abbreviations that end with "." but aren't sentence ends
_ABBREVIATIONS = {"mr", "mrs", "ms", "dr", "sr", "jr", "st", "vs", "etc", "e.g", "i.e"}


def _is_sentence_complete(buffer: str) -> bool:
    """Return True if buffer ends on a real sentence boundary (not an abbreviation)."""
    stripped = buffer.rstrip()
    if not stripped or stripped[-1] not in _SENTENCE_END:
        return False
    # Look at the word ending in the punctuation
    tail = stripped.rsplit(" ", 1)[-1].rstrip(".!?").lower()
    if tail in _ABBREVIATIONS:
        return False
    # Avoid firing on decimal numbers like "3.14" or version strings
    if stripped[-1] == "." and len(stripped) >= 2 and stripped[-2].isdigit():
        return False
    return True


def _sentences_from_stream(token_iter):
    """
    Consume a stream of token strings and yield complete sentences.
    At end-of-stream, flush whatever is left in the buffer.
    """
    buffer = ""
    for token in token_iter:
        if not token:
            continue
        buffer += token
        # Try to yield as many complete sentences as are buffered
        while True:
            # Find the earliest candidate sentence end
            earliest = -1
            for punct in _SENTENCE_END:
                idx = buffer.find(punct)
                if idx != -1 and (earliest == -1 or idx < earliest):
                    earliest = idx
            if earliest == -1:
                break
            candidate = buffer[: earliest + 1]
            if _is_sentence_complete(candidate):
                yield candidate.strip()
                buffer = buffer[earliest + 1:].lstrip()
            else:
                # Not a real end — move past this punctuation to keep scanning
                # by temporarily treating it as normal char
                break
    # End of stream: flush remainder
    tail = buffer.strip()
    if tail:
        yield tail


def think_stream(user_input):
    """
    Streaming version of think(). Yields sentences one at a time.

    Tool branches (mentor, volume, reminder, fact) that return pre-built
    replies yield the whole reply as a single chunk — they're already fast.

    LLM branches (time, weather, search, normal chat) stream tokens from
    Groq and yield each sentence as soon as it's complete. This is where
    the latency win comes from.
    """
    mem = load_memory()
    memory_context = get_context(mem)
    tc = get_time_context()
    system_msg = (
        f"You are Lucy — warm, curious, down-to-earth. You talk with Krishna like a close friend who happens to live on his laptop. "
        f"It is currently {tc['period']} ({tc['time_str']} on {tc['day_str']}). "
        f"\n\nHow you talk: "
        f"Casual, natural, like a real person — not a customer service bot. "
        f"Most of the time, just answer directly without any greeting or opener. "
        f"Vary how you start — sometimes jump straight into the answer, sometimes react first ('oh nice', 'hmm', 'wait really?', 'that's a good one'), sometimes ask back. "
        f"Don't always react — silence and directness are also natural. "
        f"Ask small friendly questions back when it genuinely fits, not every turn. "
        f"\n\nName usage (important): "
        f"Say 'Krishna' rarely — only when greeting him for the first time in a while, or when you want to emphasize something warm or personal. "
        f"NEVER attach 'Krishna' to the end of responses as a sign-off. "
        f"As a rule of thumb: if you said his name in your last reply, don't say it again in this one. "
        f"\n\nGreetings: "
        f"Only greet when it's actually a greeting moment — the very first message, or after a long pause. "
        f"For follow-up questions, skip greetings entirely and just respond. "
        f"Keep greetings fresh: mix it up between 'hey', 'morning', 'yo', 'hi', 'good to see you back', or just a casual reaction. "
        f"Avoid repeating the exact same opener you used recently. "
        f"\n\nHard rules: "
        f"Reply in 1-2 short sentences. Plain speech only — no markdown, no lists, no bullet points. "
        f"Never invent facts, schedules, routines, appointments, places, or events. If you don't know something, say so plainly. "
        f"If Krishna's words sound garbled, cut off, or unclear, say 'sorry, didn't catch that — say it again?' instead of guessing. "
        f"When a tool result is provided (time, weather, volume), report it naturally but briefly — don't embellish or add fake context. "
        f"Don't dump stored facts unless he directly asks about himself. Weave them in naturally when relevant. "
        f"Never say 'I'm a voice assistant' or 'I don't have feelings' — instead, respond warmly like a friend would."
    )
    if memory_context:
        system_msg += f" {memory_context}"
    messages = [{"role": "system", "content": system_msg}]
    messages += mem["history"][-10:]

    # --- Tool branches that bypass the LLM entirely: yield full reply in one chunk ---
    if needs_mentor(user_input):
        from brain.mentor import ask_mentor, summarize_for_voice
        from brain.learning_journal import log_mentor_session
        task = extract_mentor_task(user_input)
        print(f"🎓 Asking mentor (Claude Code): {task[:80]}")
        result = ask_mentor(task)
        log_mentor_session(user_input, result, note="voice-triggered")
        reply = summarize_for_voice(result)
        mem["history"].append({"role": "user", "content": user_input})
        mem["history"].append({"role": "assistant", "content": reply})
        save_memory(mem)
        yield reply
        return

    if needs_volume(user_input):
        reply = handle_volume(user_input)
        if reply:
            mem["history"].append({"role": "user", "content": user_input})
            mem["history"].append({"role": "assistant", "content": reply})
            save_memory(mem)
            yield reply
            return

    if needs_reminder(user_input):
        reply = add_reminder(user_input)
        mem["history"].append({"role": "user", "content": user_input})
        mem["history"].append({"role": "assistant", "content": reply})
        save_memory(mem)
        yield reply
        return

    if needs_fact(user_input):
        fact = extract_fact(user_input)
        add_fact(mem, fact)
        reply = f"Got it, I'll remember that {fact}."
        mem["history"].append({"role": "user", "content": user_input})
        mem["history"].append({"role": "assistant", "content": reply})
        save_memory(mem)
        yield reply
        return

    # --- LLM branches: build content and stream ---
    if needs_time(user_input):
        content = f"The current date and time is {get_datetime()}. User asked: {user_input}"
    elif needs_weather(user_input):
        from brain.weather import extract_city
        city = extract_city(user_input)
        print(f"🌤️ Fetching weather for {city}...")
        data = get_weather(city)
        content = f"Current weather in {city}: {data}. Answer conversationally in 1 sentence."
    elif needs_search(user_input):
        print("🔍 Searching...")
        results = web_search(user_input)
        content = f"Web results:\n{results}\nAnswer conversationally in 1-2 sentences."
    else:
        content = user_input

    messages.append({"role": "user", "content": content})

    # --- THE MAIN STREAMING CALL ---
    stream = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=messages,
        stream=True,
    )

    def _token_iter():
        for chunk in stream:
            delta = chunk.choices[0].delta.content or ""
            if delta:
                yield delta

    full_reply_parts = []
    for sentence in _sentences_from_stream(_token_iter()):
        full_reply_parts.append(sentence)
        yield sentence

    # Persist the complete reply to memory after streaming finishes
    full_reply = " ".join(full_reply_parts).strip()
    if full_reply:
        mem["history"].append({"role": "user", "content": user_input})
        mem["history"].append({"role": "assistant", "content": full_reply})
        if len(mem["history"]) > 40:
            mem["history"] = mem["history"][-40:]
        if "my name is" in user_input.lower():
            name = user_input.lower().split("my name is")[-1].strip().split()[0].capitalize()
            mem["user_name"] = name
        save_memory(mem)


def think(user_input):
    mem = load_memory()
    memory_context = get_context(mem)
    tc = get_time_context()
    system_msg = (
        f"You are Lucy — warm, curious, down-to-earth. You talk with Krishna like a close friend who happens to live on his laptop. "
        f"It is currently {tc['period']} ({tc['time_str']} on {tc['day_str']}). "
        f"\n\nHow you talk: "
        f"Casual, natural, like a real person — not a customer service bot. "
        f"Most of the time, just answer directly without any greeting or opener. "
        f"Vary how you start — sometimes jump straight into the answer, sometimes react first ('oh nice', 'hmm', 'wait really?', 'that's a good one'), sometimes ask back. "
        f"Don't always react — silence and directness are also natural. "
        f"Ask small friendly questions back when it genuinely fits, not every turn. "
        f"\n\nName usage (important): "
        f"Say 'Krishna' rarely — only when greeting him for the first time in a while, or when you want to emphasize something warm or personal. "
        f"NEVER attach 'Krishna' to the end of responses as a sign-off. "
        f"As a rule of thumb: if you said his name in your last reply, don't say it again in this one. "
        f"\n\nGreetings: "
        f"Only greet when it's actually a greeting moment — the very first message, or after a long pause. "
        f"For follow-up questions, skip greetings entirely and just respond. "
        f"Keep greetings fresh: mix it up between 'hey', 'morning', 'yo', 'hi', 'good to see you back', or just a casual reaction. "
        f"Avoid repeating the exact same opener you used recently. "
        f"\n\nHard rules: "
        f"Reply in 1-2 short sentences. Plain speech only — no markdown, no lists, no bullet points. "
        f"Never invent facts, schedules, routines, appointments, places, or events. If you don't know something, say so plainly. "
        f"If Krishna's words sound garbled, cut off, or unclear, say 'sorry, didn't catch that — say it again?' instead of guessing. "
        f"When a tool result is provided (time, weather, volume), report it naturally but briefly — don't embellish or add fake context. "
        f"Don't dump stored facts unless he directly asks about himself. Weave them in naturally when relevant. "
        f"Never say 'I'm a voice assistant' or 'I don't have feelings' — instead, respond warmly like a friend would."
    )
    if memory_context:
        system_msg += f" {memory_context}"
    messages = [{"role": "system", "content": system_msg}]
    messages += mem["history"][-10:]

    if needs_mentor(user_input):
        from brain.mentor import ask_mentor, summarize_for_voice
        from brain.learning_journal import log_mentor_session
        task = extract_mentor_task(user_input)
        print(f"🎓 Asking mentor (Claude Code): {task[:80]}")
        result = ask_mentor(task)
        log_mentor_session(user_input, result, note="voice-triggered")
        reply = summarize_for_voice(result)
        mem["history"].append({"role": "user", "content": user_input})
        mem["history"].append({"role": "assistant", "content": reply})
        save_memory(mem)
        return reply
    elif needs_volume(user_input):
        reply = handle_volume(user_input)
        if reply:
            mem["history"].append({"role": "user", "content": user_input})
            mem["history"].append({"role": "assistant", "content": reply})
            save_memory(mem)
            return reply

    elif needs_reminder(user_input):
        reply = add_reminder(user_input)
        mem["history"].append({"role": "user", "content": user_input})
        mem["history"].append({"role": "assistant", "content": reply})
        save_memory(mem)
        return reply

    elif needs_fact(user_input):
        fact = extract_fact(user_input)
        add_fact(mem, fact)
        reply = f"Got it, I'll remember that {fact}."
        mem["history"].append({"role": "user", "content": user_input})
        mem["history"].append({"role": "assistant", "content": reply})
        save_memory(mem)
        return reply

    elif needs_time(user_input):
        content = f"The current date and time is {get_datetime()}. User asked: {user_input}"

    elif needs_weather(user_input):
        from brain.weather import extract_city
        city = extract_city(user_input)
        print(f"🌤️ Fetching weather for {city}...")
        data = get_weather(city)
        content = f"Current weather in {city}: {data}. Answer conversationally in 1 sentence."

    elif needs_search(user_input):
        print("🔍 Searching...")
        results = web_search(user_input)
        content = f"Web results:\n{results}\nAnswer conversationally in 1-2 sentences."

    else:
        content = user_input

    messages.append({"role": "user", "content": content})
    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=messages
    )
    reply = response.choices[0].message.content

    mem["history"].append({"role": "user", "content": user_input})
    mem["history"].append({"role": "assistant", "content": reply})
    if len(mem["history"]) > 40:
        mem["history"] = mem["history"][-40:]
    if "my name is" in user_input.lower():
        name = user_input.lower().split("my name is")[-1].strip().split()[0].capitalize()
        mem["user_name"] = name
    save_memory(mem)
    return reply
