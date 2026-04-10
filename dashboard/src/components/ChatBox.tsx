"use client";

import { useEffect, useRef, useState, KeyboardEvent } from "react";
import type { ChatMessage } from "@/lib/types";
import { sendChat } from "@/lib/lucy-api";

interface Props {
  speakAloud?: boolean;
}

export function ChatBox({ speakAloud = false }: Props) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages]);

  async function handleSend() {
    const text = input.trim();
    if (!text || sending) return;

    const userMsg: ChatMessage = {
      id: `u-${Date.now()}`,
      role: "user",
      text,
      timestamp: Date.now(),
    };
    setMessages((m) => [...m, userMsg]);
    setInput("");
    setSending(true);
    setError(null);

    try {
      const res = await sendChat(text, speakAloud);
      const lucyMsg: ChatMessage = {
        id: `l-${Date.now()}`,
        role: "lucy",
        text: res.reply,
        timestamp: Date.now(),
      };
      setMessages((m) => [...m, lucyMsg]);
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : String(err);
      setError(errorMsg);
      const sysMsg: ChatMessage = {
        id: `e-${Date.now()}`,
        role: "system",
        text: `Error: ${errorMsg}`,
        timestamp: Date.now(),
      };
      setMessages((m) => [...m, sysMsg]);
    } finally {
      setSending(false);
    }
  }

  function handleKeyDown(e: KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  }

  return (
    <div className="flex h-full flex-col">
      <div ref={scrollRef} className="flex-1 overflow-y-auto px-6 py-8">
        <div className="mx-auto max-w-3xl space-y-4">
          {messages.length === 0 ? (
            <div className="rounded-xl border border-zinc-800 bg-zinc-900/50 p-6 text-center text-zinc-500">
              <p className="text-sm">Start a conversation with Lucy. Ask her anything.</p>
              <p className="mt-1 text-xs text-zinc-600">She&apos;ll respond based on her current mode.</p>
            </div>
          ) : (
            messages.map((msg) => <MessageBubble key={msg.id} message={msg} />)
          )}
          {sending && (
            <div className="flex">
              <div className="rounded-2xl border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-sm text-amber-300">
                <span className="inline-flex items-center gap-2">
                  <span className="h-2 w-2 animate-pulse rounded-full bg-amber-400" />
                  Lucy is thinking…
                </span>
              </div>
            </div>
          )}
        </div>
      </div>

      <div className="border-t border-zinc-800 bg-zinc-900 px-6 py-4">
        <div className="mx-auto max-w-3xl">
          <div className="flex gap-3">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Type a message to Lucy… (Enter to send)"
              disabled={sending}
              className="flex-1 rounded-lg border border-zinc-700 bg-zinc-800 px-4 py-3 text-sm text-zinc-100 placeholder-zinc-500 focus:border-amber-400 focus:outline-none disabled:opacity-50"
            />
            <button
              onClick={handleSend}
              disabled={sending || !input.trim()}
              className="rounded-lg bg-amber-500 px-6 py-3 text-sm font-semibold text-zinc-950 transition hover:bg-amber-400 disabled:opacity-50"
            >
              {sending ? "Sending…" : "Send"}
            </button>
          </div>
          {error && <p className="mt-2 text-xs text-red-400">⚠ {error}</p>}
        </div>
      </div>
    </div>
  );
}

function MessageBubble({ message }: { message: ChatMessage }) {
  if (message.role === "user") {
    return (
      <div className="flex justify-end">
        <div className="max-w-[75%] rounded-2xl bg-zinc-700 px-4 py-3 text-sm text-zinc-100">
          {message.text}
        </div>
      </div>
    );
  }
  if (message.role === "lucy") {
    return (
      <div className="flex justify-start">
        <div className="max-w-[75%] rounded-2xl border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-sm text-amber-100">
          {message.text}
        </div>
      </div>
    );
  }
  return (
    <div className="flex justify-center">
      <div className="rounded-md border border-red-500/30 bg-red-500/10 px-3 py-2 text-xs text-red-300">
        {message.text}
      </div>
    </div>
  );
}
