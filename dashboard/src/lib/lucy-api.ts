// Thin client wrapper around Lucy's HTTP API.
// Reads config from .env.local

import type { LucyMode, LucyStatus, LucyEvent, ChatResponse } from "./types";

const API_URL = process.env.NEXT_PUBLIC_LUCY_API_URL ?? "http://127.0.0.1:8765";
const TOKEN = process.env.NEXT_PUBLIC_LUCY_TOKEN ?? "";

function authHeaders(): HeadersInit {
  return {
    Authorization: `Bearer ${TOKEN}`,
    "Content-Type": "application/json",
  };
}

async function handleResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`Lucy API ${res.status}: ${text || res.statusText}`);
  }
  return res.json() as Promise<T>;
}

export async function getStatus(): Promise<LucyStatus> {
  const res = await fetch(`${API_URL}/status`, { headers: authHeaders() });
  return handleResponse<LucyStatus>(res);
}

export async function getMode(): Promise<{ mode: LucyMode }> {
  const res = await fetch(`${API_URL}/mode`, { headers: authHeaders() });
  return handleResponse<{ mode: LucyMode }>(res);
}

export async function setMode(mode: LucyMode): Promise<{ mode: LucyMode }> {
  const res = await fetch(`${API_URL}/mode`, {
    method: "POST",
    headers: authHeaders(),
    body: JSON.stringify({ mode }),
  });
  return handleResponse<{ mode: LucyMode }>(res);
}

export async function sendChat(
  message: string,
  speak: boolean = true
): Promise<ChatResponse> {
  const res = await fetch(`${API_URL}/chat`, {
    method: "POST",
    headers: authHeaders(),
    body: JSON.stringify({ message, speak }),
  });
  return handleResponse<ChatResponse>(res);
}

export async function emergencyStop(): Promise<{ stopped: boolean }> {
  const res = await fetch(`${API_URL}/stop`, {
    method: "POST",
    headers: authHeaders(),
  });
  return handleResponse<{ stopped: boolean }>(res);
}

export async function getEventHistory(limit: number = 50): Promise<{
  events: LucyEvent[];
}> {
  const res = await fetch(
    `${API_URL}/events/history?limit=${limit}`,
    { headers: authHeaders() }
  );
  return handleResponse<{ events: LucyEvent[] }>(res);
}

/**
 * Open a WebSocket connection to stream live events.
 * Returns the WebSocket so the caller can .close() it on unmount.
 */
export function openEventStream(
  onEvent: (event: LucyEvent) => void,
  onError?: (err: Event) => void,
  onOpen?: () => void
): WebSocket {
  // Convert http(s) -> ws(s) and append token as query param
  const wsUrl =
    API_URL.replace(/^http/, "ws") + `/events/stream?token=${encodeURIComponent(TOKEN)}`;
  const ws = new WebSocket(wsUrl);
  ws.addEventListener("open", () => onOpen?.());
  ws.addEventListener("message", (ev) => {
    try {
      const parsed = JSON.parse(ev.data) as LucyEvent;
      onEvent(parsed);
    } catch (e) {
      console.error("Bad event JSON", e);
    }
  });
  ws.addEventListener("error", (e) => onError?.(e));
  return ws;
}

export const LUCY_API_URL = API_URL;
export const LUCY_TOKEN = TOKEN;
