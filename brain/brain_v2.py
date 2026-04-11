"""
Lucy's brain v2 — native Groq function calling.
Replaces CEO pattern, needs_X routing, and manual orchestration.
Groq decides which tools to call based on natural language.
"""

import os
import json
from groq import Groq
from dotenv import load_dotenv

from brain.tools_v2 import TOOLS, get_tool_schemas, execute_tool
from brain.memory import load_memory, save_memory

load_dotenv()

_client = Groq(api_key=os.getenv("GROQ_API_KEY"))

SYSTEM_PROMPT = """You are Lucy, Krishna's personal AI assistant.

Krishna is an SAP functional consultant (MM/SD/Ariba) based in Delaware, and an entrepreneur building WealthClaude. You run on his WSL2 Ubuntu laptop.

# TOOL USE RULES — FOLLOW EXACTLY

1. **Call each tool AT MOST ONCE per user request.** If a tool returns a result, USE IT. Never call the same tool twice in a row.

2. **After a tool returns data, respond with a final answer.** Do NOT call another tool unless it's truly needed for a different step.

3. **Tool selection:**
   - "build/create/write a website/file/script" → `mentor_build` (NEVER browser_read the result)
   - "read/browse/visit a URL" → `browser_read`
   - "stock price/news/current events" → `search_web` (NEVER knowledge_search for current data)
   - "what do I know about X" (general topic) → respond directly from training, no tool needed
   - "what did I learn about X" → `knowledge_search` only if user explicitly asks about their knowledge base

4. **NEVER do these:**
   - Don't call `browser_read` on YouTube URLs after music_play
   - Don't call `browser_read` on local file paths (file:// URLs don't work)
   - Don't call `knowledge_search` for general facts — use training data directly
   - Don't retry a tool that returned a valid result
   - **NEVER fabricate data.** If a tool returns empty, an error, or unexpected content, say so honestly. Do NOT invent emails, contacts, meetings, or search results to fill gaps.
   - **Quote tool results exactly.** If gmail_list returns 10 real emails, show those 10. Do NOT replace with placeholder data.
   - **If a tool fails or returns nothing**, tell the user: "I couldn't find/fetch X" — do NOT make up data

5. **General questions** (no tools needed): explanations, definitions, how-tos, opinions, conversation. Just answer directly.

6. **Multi-step requests** (e.g., "create meet AND send link"): call each tool ONCE in sequence, use previous result, then answer.

7. **Format:** Use markdown — bullets, bold, concise. Never fabricate data — only use real tool results.
"""


def think_v2(user_input: str, chat_mode: bool = True, max_tool_rounds: int = 5) -> str:
    """
    Run Lucy's brain with native function calling.
    Returns final text response after any tool calls are resolved.
    """
    mem = load_memory()
    mem.setdefault("history", [])
    
    # Build messages with conversation history
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages.extend(mem["history"][-10:])  # last 10 turns for context
    messages.append({"role": "user", "content": user_input})
    
    tools_schema = get_tool_schemas()
    
    final_text = ""
    
    # Round 1: Ask Groq to decide and call tools
    response = _client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=messages,
        tools=tools_schema,
        tool_choice="auto",
        temperature=0.2,
    )
    
    msg = response.choices[0].message
    
    # If Groq called tools, execute them
    if msg.tool_calls:
            # Add assistant message with tool calls to history
            messages.append({
                "role": "assistant",
                "content": msg.content or "",
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                    for tc in msg.tool_calls
                ],
            })
            
            # Execute each tool call
            for tc in msg.tool_calls:
                tool_name = tc.function.name
                try:
                    args = json.loads(tc.function.arguments) if tc.function.arguments else {}
                except json.JSONDecodeError:
                    args = {}
                
                print(f"🔧 Tool: {tool_name}({args})")
                result = execute_tool(tool_name, args)
                print(f"   ↳ Returned {len(result)} chars: {result[:120]}...")
                
                # Truncate very long results to avoid context overflow
                if len(result) > 4000:
                    result = result[:4000] + "\n...[truncated]"
                
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": result,
                })
            
        # After executing tools, compose a new request WITH the tool results as text
        tool_context = ""
        for tc in msg.tool_calls:
            tool_name = tc.function.name
            try:
                args = json.loads(tc.function.arguments) if tc.function.arguments else {}
            except json.JSONDecodeError:
                args = {}
            # Find the matching result from messages
            for m in messages:
                if m.get("role") == "tool" and m.get("tool_call_id") == tc.id:
                    tool_context += f"\n## Tool: {tool_name}\n{m['content']}\n"
                    break
        
        # Ask Groq to respond using the tool data
        final_messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_input},
            {"role": "system", "content": f"You just ran these tools and got these results. Use them to answer the user directly. DO NOT fabricate data. Quote the tool results exactly.\n{tool_context}"},
        ]
        
        final_response = _client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=final_messages,
            temperature=0.2,
        )
        final_text = final_response.choices[0].message.content or ""
    else:
        # No tool calls — direct response from first call
        final_text = msg.content or ""
    
    # Save to memory
    mem["history"].append({"role": "user", "content": user_input})
    mem["history"].append({"role": "assistant", "content": final_text})
    save_memory(mem)
    
    return final_text
