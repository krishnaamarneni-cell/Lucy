"use client";

import { useState } from "react";
import { emergencyStop } from "@/lib/lucy-api";

export function KillSwitch() {
  const [pressing, setPressing] = useState(false);
  const [justStopped, setJustStopped] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleClick() {
    if (pressing) return;
    setPressing(true);
    setError(null);
    try {
      await emergencyStop();
      setJustStopped(true);
      // Show confirmation briefly
      setTimeout(() => setJustStopped(false), 3000);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setPressing(false);
    }
  }

  return (
    <div className="flex flex-col items-end">
      <button
        onClick={handleClick}
        disabled={pressing}
        title="Emergency stop — halts any current operation"
        className={[
          "rounded-md px-4 py-2 text-sm font-semibold text-white shadow-lg transition",
          justStopped
            ? "bg-zinc-600 hover:bg-zinc-500"
            : "bg-red-600 hover:bg-red-500 active:bg-red-700",
          "disabled:opacity-50",
        ].join(" ")}
      >
        {pressing ? "STOPPING…" : justStopped ? "STOPPED ✓" : "STOP"}
      </button>
      {error && (
        <p className="mt-1 text-[10px] text-red-400" title={error}>
          ⚠ {error.slice(0, 40)}
        </p>
      )}
    </div>
  );
}
