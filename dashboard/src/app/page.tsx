"use client";

import Link from "next/link";

import { useEffect, useState } from "react";
import { getStatus } from "@/lib/lucy-api";
import { ModeToggle } from "@/components/ModeToggle";
import { ChatBox } from "@/components/ChatBox";
import { EventStream } from "@/components/EventStream";
import { KillSwitch } from "@/components/KillSwitch";
import { ModelSelector } from "@/components/ModelSelector";
import type { LucyStatus } from "@/lib/types";

export default function DashboardPage() {
  const [status, setStatus] = useState<LucyStatus | null>(null);
  const [connectionError, setConnectionError] = useState<string | null>(null);

  // Poll Lucy's status every 2 seconds
  useEffect(() => {
    let cancelled = false;

    async function fetchStatus() {
      try {
        const s = await getStatus();
        if (!cancelled) {
          setStatus(s);
          setConnectionError(null);
        }
      } catch (err) {
        if (!cancelled) {
          setConnectionError(err instanceof Error ? err.message : String(err));
        }
      }
    }

    fetchStatus();
    const interval = setInterval(fetchStatus, 2000);

    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, []);

  return (
    <div className="flex h-screen flex-col bg-zinc-950 text-zinc-100">
      {/* Header bar */}
      <header className="flex items-center justify-between border-b border-zinc-800 bg-zinc-900 px-6 py-4">
        <div className="flex items-center gap-3">
          <div className="h-3 w-3 rounded-full bg-emerald-400 shadow-[0_0_12px_rgba(16,185,129,0.6)]" />
          <h1 className="text-xl font-semibold tracking-tight">Lucy</h1>
          <span className="text-xs uppercase tracking-widest text-zinc-500">
            dashboard
          </span>
        </div>

        <div className="flex items-center gap-6">
          {/* Status indicator placeholder */}
          <div className="flex items-center gap-2 text-sm">
            <span className="text-zinc-500">status:</span>
            {connectionError ? (
              <span className="text-red-400">offline</span>
            ) : status ? (
              <span className="text-emerald-400">
                {status.speaking ? "speaking" : "idle"}
              </span>
            ) : (
              <span className="text-zinc-500">connecting…</span>
            )}
          </div>

          {/* Mode toggle — click to change Lucy's mode */}
          <ModelSelector />
          <Link
            href="/voice"
            className="rounded-md border border-amber-500/30 bg-amber-500/10 px-3 py-1.5 text-xs font-semibold uppercase tracking-widest text-amber-300 transition hover:bg-amber-500/20"
          >
            🎙 Voice
          </Link>

          <ModeToggle
            currentMode={status?.mode ?? null}
            onChanged={(newMode) => setStatus((s) => s ? { ...s, mode: newMode } : s)}
          />

          {/* Kill switch — emergency stop */}
          <KillSwitch />
        </div>
      </header>

      {/* Main content — chat + event sidebar */}
      <div className="flex flex-1 overflow-hidden">
        {/* Chat area */}
        <main className="flex flex-1 flex-col">
          <ChatBox speakAloud={false} />
        </main>

        {/* Event sidebar */}
        <aside className="w-80 border-l border-zinc-800 bg-zinc-900/70">
          <EventStream />
        </aside>
      </div>

      {/* Debug banner if Lucy is unreachable */}
      {connectionError && (
        <div className="border-t border-red-900 bg-red-950/60 px-6 py-2 text-xs text-red-300">
          Cannot reach Lucy API: {connectionError}
        </div>
      )}
    </div>
  );
}
