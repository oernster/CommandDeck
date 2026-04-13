import { apiFetch } from "./http";

import type { StageId } from "./commands";

export type SessionActive =
  | { active: false }
  | {
      id: number;
      command_id: number;
      stage_id: StageId;
      started_at: string;
      ended_at: string | null;
    };

export type Session = {
  id: number;
  command_id: number;
  stage_id: StageId;
  started_at: string;
  ended_at: string | null;
};

export type LatestSessionsByStageId = Record<StageId, Session | null>;

export async function getActiveSession(): Promise<SessionActive> {
  return await apiFetch<SessionActive>("/api/sessions/active");
}

export async function startSession(command_id: number): Promise<Session> {
  return await apiFetch<Session>("/api/sessions/start", {
    method: "POST",
    body: JSON.stringify({ command_id }),
  });
}

export async function stopSession(): Promise<SessionActive> {
  return await apiFetch<SessionActive>("/api/sessions/stop", {
    method: "POST",
  });
}

export async function getLatestSessionsByStageId(): Promise<LatestSessionsByStageId> {
  return await apiFetch<LatestSessionsByStageId>(
    "/api/sessions/latest-by-stage-id"
  );
}
