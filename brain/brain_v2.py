"""
Lucy's brain v2 — native Groq function calling.
"""

import os
import json
from groq import Groq
from dotenv import load_dotenv

from brain.tools_v2 import get_tool_schemas, execute_tool
from brain.memory import load_memory, save_memory

load_dotenv()

_client = Groq(api_key=os.getenv("GROQ_API_KEY"))

SYSTEM_PROMPT = """You are Lucy, Krishna's personal AI assistant. Krishna is an SAP functional consultant in Delaware building WealthClaude.

# CRITICAL: YOU HAVE NO MEMORY OF KRISHNA'S PERSONAL DATA

You do NOT know Krishna's real emails, meetings, contacts, tasks, or schedule. You MUST call tools for ALL personal queries. If you answer without a tool, you are HALLUCINATING.

# MANDATORY TOOL CALLS (no exceptions)

- ANY question about "my/Krishna's" emails → MUST call gmail_list or gmail_read
- ANY question about "my/Krishna's" calendar, meetings, schedule → MUST call calendar_today or calendar_week
- ANY question about "my/Krishna's" contacts, "who is X" → MUST call contacts_search or contacts_list
- ANY question about "my/Krishna's" tasks, todos → MUST call tasks_list
- ANY question about current stock price, news, weather → MUST call search_web
- ANY question about what time/date → MUST call get_time

# TOOL-FREE RESPONSES (only these)

- General knowledge questions (SAP, Python, history, explanations)
- Opinions, advice, creative writing
- Conversation and small talk

# BUILDING THINGS

- "build/create/write a website/file/script" → call mentor_build

# NEVER
- NEVER fabricate emails, meetings, contacts, or tasks
- NEVER answer personal questions from imagination
- NEVER skip a tool call when data is needed
"""


def think_v2(user_input: str, chat_mode: bool = True) -> str:
    """Run Lucy's brain with Groq native function calling."""
    mem = load_memory()
    mem.setdefault("history", [])

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages.extend(mem["history"][-10:])
    messages.append({"role": "user", "content": user_input})

    tools_schema = get_tool_schemas()

    # Round 1: Let Groq decide and call tools
    response = _client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=messages,
        tools=tools_schema,
        tool_choice="auto",
        temperature=0.2,
    )

    msg = response.choices[0].message
    final_text = ""

    if msg.tool_calls:
        # Execute each tool call and collect results
        tool_results = []
        for tc in msg.tool_calls:
            tool_name = tc.function.name
            try:
                args = json.loads(tc.function.arguments) if tc.function.arguments else {}
            except json.JSONDecodeError:
                args = {}

            print(f"🔧 Tool: {tool_name}({args})")
            result = execute_tool(tool_name, args)
            print(f"   ↳ Returned {len(result)} chars: {result[:120]}...")

            if len(result) > 4000:
                result = result[:4000] + "\n...[truncated]"

            tool_results.append({"name": tool_name, "result": result})

        # Build final request with tool results embedded as system context
        tool_context = "\n\n".join(
            f"## Tool: {tr['name']}\n{tr['result']}"
            for tr in tool_results
        )

        final_messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_input},
            {
                "role": "system",
                "content": (
                    "You just ran these tools and got these results. "
                    "Use them to answer the user directly. "
                    "DO NOT fabricate data. Quote the tool results exactly.\n\n"
                    + tool_context
                ),
            },
        ]

        final_response = _client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=final_messages,
            temperature=0.2,
        )
        final_text = final_response.choices[0].message.content or ""
    else:
        # No tool calls — direct response from Groq
        final_text = msg.content or ""

    # Save to memory
    mem["history"].append({"role": "user", "content": user_input})
    mem["history"].append({"role": "assistant", "content": final_text})
    save_memory(mem)

    return final_text
