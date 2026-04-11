"use client";

import { useEffect, useRef, useState } from "react";
import type { LucyEvent } from "@/lib/types";
import { openEventStream, getEventHistory } from "@/lib/lucy-api";

const KIND_STYLES: Record<string, { color: string; icon: string }> = {
  "status.booted": { color: "text-emerald-400", icon: "●" },
  "api.started": { color: "text-emerald-400", icon: "●" },
  "api.stopped": { color: "text-zinc-500", icon: "○" },
  "voice.awake": { color: "text-sky-400", icon: "👂" },
  "voice.sleeping": { color: "text-zinc-500", icon: "😴" },
  "voice.transcribed": { color: "text-sky-300", icon: "🗣" },
  "chat.received": { color: "text-amber-300", icon: "💬" },
  "chat.replied": { color: "text-amber-400", icon: "💭" },
  "mode.changed": { color: "text-purple-300", icon: "⚙" },
  "action.denied": { color: "text-red-400", icon: "⛔" },
  "stop.triggered": { color: "text-red-500", icon: "🛑" },
  "error": { color: "text-red-400", icon: "⚠" },
};

function styleForKind(kind: string) {
  return KIND_STYLES[kind] ?? { color: "text-zinc-400", icon: "•" };
}

function formatTime(iso: string): string {
  try {
    const d = new Date(iso);
    return d.toLocaleTimeString([], { hour12: false });
  } catch {
    return iso;
  }
}

function formatData(data: Record<string, unknown>): string {
  const keys = Object.keys(data);
  if (keys.length === 0) return "";
  // Try to show the most meaningful field
  if ("text" in data) return String(data.text).slice(0, 60);
  if ("message" in data) return String(data.message).slice(0, 60);
  if ("reply" in data) return String(data.reply).slice(0, 60);
  if ("task" in data) return String(data.task).slice(0, 60);
  if ("from" in data && "to" in data) return `${data.from} → ${data.to}`;
  return JSON.stringify(data).slice(0, 60);
}

export function EventStream() {
  const [events, setEvents] = useState<LucyEvent[]>([]);
  const [connected, setConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    let cancelled = false;

    // Load recent history first
    getEventHistory(50)
      .then((res) => {
        if (!cancelled) setEvents(res.events);
      })
      .catch(() => {});

    // Then open the live stream
    const ws = openEventStream(
      (event) => {
        if (cancelled) return;
        setEvents((prev) => {
          // Avoid duplicates (history + stream overlap)
          if (prev.some((e) => e.id === event.id)) return prev;
          return [...prev, event].slice(-100); // keep last 100
        });
      },
      () => setConnected(false),
      () => setConnected(true)
    );
    wsRef.current = ws;

    return () => {
      cancelled = true;
      try {
        ws.close();
      } catch {}
    };
  }, []);

  // Auto-scroll to bottom when new events arrive
  const scrollRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [events]);

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center justify-between border-b border-zinc-800 px-4 py-3">
        <h2 className="text-xs font-semibold uppercase tracking-widest text-zinc-400">
          Live events
        </h2>
        <div className="flex items-center gap-2 text-xs">
          <span
            className={
              connected
                ? "h-2 w-2 rounded-full bg-emerald-400 shadow-[0_0_8px_rgba(16,185,129,0.8)]"
                : "h-2 w-2 rounded-full bg-zinc-600"
            }
          />
          <span className="text-zinc-500">{connected ? "live" : "offline"}</span>
        </div>
      </div>
      <div
        ref={scrollRef}
        className="flex-1 overflow-y-auto px-3 py-2 text-xs"
      >
        {events.length === 0 ? (
          <p className="px-2 py-4 text-center text-zinc-600">
            No events yet. Lucy will populate this when she acts.
          </p>
        ) : (
          <ul className="space-y-1">
            {events.map((ev, i) => {
              const style = styleForKind(ev.kind);
              const dataStr = formatData(ev.data as Record<string, unknown>);
              return (
                <li
                  key={`${ev.id}-${i}`}
                  className="rounded border border-transparent px-2 py-1.5 font-mono hover:border-zinc-800 hover:bg-zinc-900"
                >
                  <div className="flex items-center gap-2">
                    <span className={style.color}>{style.icon}</span>
                    <span className={`${style.color} font-semibold`}>
                      {ev.kind}
                    </span>
                    <span className="ml-auto text-[10px] text-zinc-600">
                      {formatTime(ev.timestamp)}
                    </span>
                  </div>
                  {dataStr && (
                    <div className="mt-0.5 truncate pl-5 text-[11px] text-zinc-500">
                      {dataStr}
                    </div>
                  )}
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </div>
  );
}
