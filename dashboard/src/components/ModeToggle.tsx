"use client";

import { useState } from "react";
import type { LucyMode } from "@/lib/types";
import { setMode as setLucyMode } from "@/lib/lucy-api";

interface Props {
  currentMode: LucyMode | null;
  onChanged: (mode: LucyMode) => void;
}

const MODES: Array<{
  value: LucyMode;
  label: string;
  color: string;
  hint: string;
}> = [
  {
    value: "read",
    label: "READ",
    color: "bg-emerald-500/20 border-emerald-500 text-emerald-300",
    hint: "Lucy can only read. Safest mode.",
  },
  {
    value: "ask",
    label: "ASK",
    color: "bg-amber-500/20 border-amber-500 text-amber-300",
    hint: "Lucy proposes actions and waits for confirmation.",
  },
  {
    value: "edit",
    label: "EDIT",
    color: "bg-red-500/20 border-red-500 text-red-300",
    hint: "Lucy acts directly. Use with care.",
  },
];

export function ModeToggle({ currentMode, onChanged }: Props) {
  const [busy, setBusy] = useState<LucyMode | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleClick(mode: LucyMode) {
    if (mode === currentMode || busy) return;
    setBusy(mode);
    setError(null);
    try {
      const res = await setLucyMode(mode);
      onChanged(res.mode);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="flex items-center gap-2">
      <span className="text-xs uppercase tracking-widest text-zinc-500">mode</span>
      <div className="flex items-center gap-1 rounded-lg border border-zinc-800 bg-zinc-900 p-1">
        {MODES.map((m) => {
          const isActive = currentMode === m.value;
          const isBusy = busy === m.value;
          return (
            <button
              key={m.value}
              onClick={() => handleClick(m.value)}
              title={m.hint}
              disabled={busy !== null}
              className={[
                "rounded-md px-3 py-1 text-xs font-mono font-semibold uppercase transition",
                isActive
                  ? `${m.color} border`
                  : "border border-transparent text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800",
                isBusy ? "opacity-50" : "",
              ].join(" ")}
            >
              {m.label}
            </button>
          );
        })}
      </div>
      {error && (
        <span className="text-xs text-red-400" title={error}>
          ⚠ error
        </span>
      )}
    </div>
  );
}
