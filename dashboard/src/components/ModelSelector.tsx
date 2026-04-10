"use client";

import { useEffect, useState } from "react";
import { getModelInfo, setModel } from "@/lib/lucy-api";

interface ModelInfo {
  active: string;
  models: Record<string, {
    name: string;
    provider: string;
    model: string;
    speed: string;
    cost: string;
    needs_internet: boolean;
  }>;
}

export function ModelSelector() {
  const [info, setInfo] = useState<ModelInfo | null>(null);
  const [switching, setSwitching] = useState(false);

  useEffect(() => {
    getModelInfo().then(setInfo).catch(() => {});
    const interval = setInterval(() => {
      getModelInfo().then(setInfo).catch(() => {});
    }, 5000);
    return () => clearInterval(interval);
  }, []);

  async function handleChange(modelId: string) {
    setSwitching(true);
    try {
      const updated = await setModel(modelId);
      setInfo(updated);
    } catch {
      // ignore
    } finally {
      setSwitching(false);
    }
  }

  if (!info) return null;

  const providerColors: Record<string, string> = {
    groq: "text-green-400 border-green-500/30 bg-green-500/10",
    ollama: "text-blue-400 border-blue-500/30 bg-blue-500/10",
  };

  return (
    <div className="flex items-center gap-2">
      <span className="text-[10px] uppercase tracking-widest text-zinc-600">model</span>
      <div className="relative">
        <select
          value={info.active}
          onChange={(e) => handleChange(e.target.value)}
          disabled={switching}
          className={[
            "appearance-none rounded-md border px-3 py-1.5 pr-7 text-xs font-medium transition cursor-pointer",
            "focus:outline-none disabled:opacity-50",
            providerColors[info.models[info.active]?.provider || "groq"] || "text-zinc-400 border-zinc-700 bg-zinc-800",
          ].join(" ")}
        >
          {Object.entries(info.models).map(([id, model]) => (
            <option key={id} value={id} className="bg-zinc-900 text-zinc-100">
              {model.name} ({model.speed})
            </option>
          ))}
        </select>
        <div className="pointer-events-none absolute right-2 top-1/2 -translate-y-1/2">
          <svg width="10" height="6" viewBox="0 0 10 6" fill="none">
            <path d="M1 1L5 5L9 1" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
        </div>
      </div>
      {switching && <span className="h-2 w-2 animate-pulse rounded-full bg-amber-400" />}
    </div>
  );
}
