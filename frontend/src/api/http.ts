export type ApiError = {
  error: string;
};

export class HttpError extends Error {
  public readonly status: number;
  public readonly body: unknown;

  constructor(message: string, status: number, body: unknown) {
    super(message);
    this.status = status;
    this.body = body;
  }
}

async function parseJsonSafe(resp: Response): Promise<unknown> {
  const contentType = resp.headers.get("content-type") ?? "";
  if (!contentType.includes("application/json")) {
    return await resp.text();
  }
  try {
    return await resp.json();
  } catch {
    return null;
  }
}

export async function apiFetch<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const resp = await fetch(path, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(options.headers ?? {}),
    },
  });

  const body = await parseJsonSafe(resp);

  if (!resp.ok) {
    const msg =
      typeof body === "object" && body !== null && "error" in body
        ? String((body as ApiError).error)
        : `Request failed (${resp.status})`;
    throw new HttpError(msg, resp.status, body);
  }

  return body as T;
}

export function isHttpError(err: unknown): err is HttpError {
  return err instanceof HttpError;
}

