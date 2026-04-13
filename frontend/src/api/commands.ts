import { apiFetch } from "./http";

export type StageId = "DESIGN" | "BUILD" | "REVIEW" | "COMPLETE";
export type Status = "Not Started" | "In Progress" | "Blocked" | "Complete";

export type Command = {
  id: number;
  title: string;
  stage_id: StageId;
  status: Status;
  created_at: string;
};

export type CreateCommandInput = {
  title: string;
  stage_id: StageId;
  status?: Status;
};

export type UpdateCommandInput = {
  title?: string;
  stage_id?: StageId;
  status?: Status;
};

export async function listCommands(params?: {
  stage_id?: StageId;
  status?: Status;
}): Promise<Command[]> {
  const qs = new URLSearchParams();
  if (params?.stage_id) qs.set("stage_id", params.stage_id);
  if (params?.status) qs.set("status", params.status);

  const path = qs.toString() ? `/api/commands?${qs.toString()}` : "/api/commands";
  return await apiFetch<Command[]>(path);
}

export async function createCommand(input: CreateCommandInput): Promise<Command> {
  return await apiFetch<Command>("/api/commands", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export async function updateCommand(
  id: number,
  input: UpdateCommandInput
): Promise<Command> {
  return await apiFetch<Command>(`/api/commands/${id}`, {
    method: "PATCH",
    body: JSON.stringify(input),
  });
}

export async function deleteCommand(id: number): Promise<{ ok: true }> {
  return await apiFetch<{ ok: true }>(`/api/commands/${id}`, {
    method: "DELETE",
  });
}

export async function reorderCommands(input: {
  by_stage_id: Record<StageId, number[]>;
}): Promise<{ ok: true }> {
  return await apiFetch<{ ok: true }>("/api/commands/reorder", {
    method: "POST",
    body: JSON.stringify(input),
  });
}
