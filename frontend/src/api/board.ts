import { apiFetch } from "./http";

export type BoardState = {
  name: string;
  user_named: boolean;
  is_new_unnamed: boolean;
  stage_labels: Record<string, string> | null;
};

export async function getBoard(): Promise<BoardState> {
  return await apiFetch<BoardState>("/api/board");
}

export async function updateBoard(input: { name: string }): Promise<BoardState> {
  return await apiFetch<BoardState>("/api/board", {
    method: "PATCH",
    body: JSON.stringify(input),
  });
}

export async function updateStageLabels(input: {
  stage_labels: Record<string, string>;
}): Promise<BoardState> {
  return await apiFetch<BoardState>("/api/board/stage-labels", {
    method: "PATCH",
    body: JSON.stringify(input),
  });
}

