"""
Lucy's LLM router — now a thin wrapper around brain_v2 (native tool calling).
Old keyword routing removed. See llm_old_backup.py for the legacy version.
"""

from brain.brain_v2 import think_v2
from brain.memory import load_memory, save_memory


def think(user_input, chat_mode=False):
    """Main entry point — delegates to brain_v2."""
    return think_v2(user_input, chat_mode=chat_mode)


def think_stream(user_input, chat_mode=False):
    """
    Streaming version — for now, yields the full brain_v2 response as one chunk.
    True token streaming with tool calling requires a separate implementation.
    """
    reply = think_v2(user_input, chat_mode=chat_mode)
    # Split into sentences for pseudo-streaming
    import re
    sentences = re.split(r'(?<=[.!?])\s+', reply)
    for s in sentences:
        if s.strip():
            yield s + " "
