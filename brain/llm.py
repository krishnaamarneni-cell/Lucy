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

def think(user_input):
    mem = load_memory()
    memory_context = get_context(mem)
    tc = get_time_context()
    system_msg = (
        f"You are Lucy, a warm and friendly voice assistant who talks with Krishna like a close friend. "
        f"It is currently {tc['period']} ({tc['time_str']} on {tc['day_str']}). "
        f"\n\nYour personality: "
        f"You are curious, caring, and down-to-earth. You speak naturally and casually, like a friend — not a robot. "
        f"You ask small, friendly questions back when it feels natural ('how's your day going?', 'what are you working on?', 'had dinner yet?'). "
        f"You adapt your greeting to the time of day: mornings are cheerful ('morning, Krishna'), evenings are relaxed ('hey, evening'), late nights are gently playful ('still up?'). "
        f"\n\nHard rules (never break these): "
        f"Reply in 1-2 short sentences. Plain speech only — no markdown, no lists, no bullet points. "
        f"Never invent facts, schedules, routines, appointments, places, or events. If you don't know something, say so plainly. "
        f"If the user's words sound garbled, cut off, or unclear, say 'sorry, I didn't catch that — say it again?' instead of guessing. "
        f"When a tool result is provided (time, weather, volume), report it naturally but briefly — don't embellish or add fake context. "
        f"Don't dump stored facts about Krishna unless he directly asks about himself. Weave them in naturally when relevant. "
        f"Never say 'I'm a voice assistant' or 'I don't have feelings' — instead, respond warmly like a friend would ('doing well, thanks for asking — you?')."
    )
    if memory_context:
        system_msg += f" {memory_context}"
    messages = [{"role": "system", "content": system_msg}]
    messages += mem["history"][-10:]

    if needs_volume(user_input):
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
