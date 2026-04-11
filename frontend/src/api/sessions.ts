import { apiFetch } from "./http";

import type { Category } from "./commands";

export type SessionActive =
  | { active: false }
  | {
      id: number;
      category: Category;
      started_at: string;
      ended_at: string | null;
    };

export async function getActiveSession(): Promise<SessionActive> {
  return await apiFetch<SessionActive>("/api/sessions/active");
}

export async function startSession(category: Category): Promise<SessionActive> {
  return await apiFetch<SessionActive>("/api/sessions/start", {
    method: "POST",
    body: JSON.stringify({ category }),
  });
}

export async function stopSession(): Promise<SessionActive> {
  return await apiFetch<SessionActive>("/api/sessions/stop", {
    method: "POST",
  });
}

