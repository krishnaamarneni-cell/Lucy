// Shared types that match Lucy's Python API schemas in brain/api.py

export type LucyMode = "read" | "ask" | "edit";

export interface LucyStatus {
  running: boolean;
  mode: LucyMode;
  speaking: boolean;
  subscribers: number;
}

export interface LucyEvent {
  id: number;
  timestamp: string;
  kind: string;
  data: Record<string, unknown>;
}

export interface ChatResponse {
  reply: string;
  mode: LucyMode;
}

export interface ChatMessage {
  id: string;
  role: "user" | "lucy" | "system";
  text: string;
  timestamp: number;
}
