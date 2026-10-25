import type { CommandResult } from "./types";

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

const HEADERS = { "X-Requested-With": "deebot-lv" };

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  let response: Response;
  try {
    response = await fetch(path, {
      method,
      credentials: "same-origin",
      headers: body === undefined ? HEADERS : { ...HEADERS, "Content-Type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch {
    throw new ApiError(0, "Nav savienojuma ar lietotnes serveri. Pārbaudiet Wi-Fi.");
  }
  if (!response.ok) {
    let message = `Kļūda (${response.status}).`;
    try {
      const data = await response.json();
      if (typeof data?.detail === "string") message = data.detail;
    } catch {
      /* not JSON */
    }
    if (response.status === 401) window.dispatchEvent(new Event("deebot:logged-out"));
    throw new ApiError(response.status, message);
  }
  return (await response.json()) as T;
}

export const api = {
  get: <T>(path: string) => request<T>("GET", path),
  post: <T>(path: string, body: unknown = {}) => request<T>("POST", path, body),
  put: <T>(path: string, body: unknown) => request<T>("PUT", path, body),
  del: <T>(path: string, body: unknown) => request<T>("DELETE", path, body),
  command: (name: string, params: Record<string, unknown> = {}) =>
    request<CommandResult>("POST", "/api/commands", { name, params }),
};
