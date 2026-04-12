import { apiFetch } from "./http";

export type Category = "Design" | "Build" | "Review" | "Maintain" | "Recover";
export type Status = "Not Started" | "In Progress" | "Blocked" | "Complete";

export type Command = {
  id: number;
  title: string;
  category: Category;
  status: Status;
  created_at: string;
};

export type CreateCommandInput = {
  title: string;
  category: Category;
  status?: Status;
};

export type UpdateCommandInput = {
  title?: string;
  category?: Category;
  status?: Status;
};

export async function listCommands(params?: {
  category?: Category;
  status?: Status;
}): Promise<Command[]> {
  const qs = new URLSearchParams();
  if (params?.category) qs.set("category", params.category);
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
  by_category: Record<Category, number[]>;
}): Promise<{ ok: true }> {
  return await apiFetch<{ ok: true }>("/api/commands/reorder", {
    method: "POST",
    body: JSON.stringify(input),
  });
}
