import { apiFetch } from "./http";

export type BoardState = {
  name: string;
  user_named: boolean;
  is_new_unnamed: boolean;
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

