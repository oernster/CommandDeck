import { apiFetch } from "./http";

export type Outcome = {
  id: number;
  command_id: number;
  note: string;
  created_at: string;
};

export async function listOutcomes(commandId: number): Promise<Outcome[]> {
  return await apiFetch<Outcome[]>(`/api/commands/${commandId}/outcomes`);
}

export async function createOutcome(
  commandId: number,
  input: { note: string }
): Promise<Outcome> {
  return await apiFetch<Outcome>(`/api/commands/${commandId}/outcomes`, {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export async function deleteOutcome(outcomeId: number): Promise<{ ok: true }> {
  return await apiFetch<{ ok: true }>(`/api/outcomes/${outcomeId}`, {
    method: "DELETE",
  });
}

export async function getLatestOutcomes(commandIds: number[]): Promise<Record<number, Outcome>> {
  if (commandIds.length === 0) return {};

  const resp = await apiFetch<{ by_command_id: Record<number, Outcome> }>(
    "/api/outcomes/latest",
    {
      method: "POST",
      body: JSON.stringify({ command_ids: commandIds }),
    }
  );
  return resp.by_command_id ?? {};
}

