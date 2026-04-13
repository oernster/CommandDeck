import { apiFetch } from "./http";

export type SnapshotSummary = {
  id: number;
  name: string;
  saved_at: string; // ISO 8601 Z
};

export async function listSnapshots(): Promise<SnapshotSummary[]> {
  return await apiFetch<SnapshotSummary[]>("/api/snapshots");
}

export async function saveSnapshot(): Promise<SnapshotSummary> {
  return await apiFetch<SnapshotSummary>("/api/snapshots", {
    method: "POST",
  });
}

export async function loadSnapshot(snapshotId: number): Promise<{ ok: true }> {
  return await apiFetch<{ ok: true }>(`/api/snapshots/${snapshotId}/load`, {
    method: "POST",
  });
}

export async function patchSnapshot(
  snapshotId: number,
  payload: { name: string }
): Promise<SnapshotSummary> {
  return await apiFetch<SnapshotSummary>(`/api/snapshots/${snapshotId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

