import type { RuntimeMessage, RuntimeResponse } from "./types";

export async function sendRuntimeMessage<T>(message: RuntimeMessage): Promise<T> {
  const response = (await chrome.runtime.sendMessage(message)) as RuntimeResponse<T>;
  if (!response?.ok) throw new Error(response?.error || "Extension request failed");
  return response.data as T;
}

export function isRuntimeMessage(value: unknown): value is RuntimeMessage {
  const allowed = new Set<RuntimeMessage["type"]>([
    "auth:getToken", "auth:clearToken", "auth:getProfile", "gmail:listMessages", "gmail:getMessage",
    "gmail:listLabels", "scan:previewInbox", "scan:getLatest", "backend:pair", "backend:authStatus",
    "backend:refresh", "backend:disconnect", "backend:openDashboard", "backend:health", "sidepanel:open"
  ]);
  return Boolean(value && typeof value === "object" && "type" in value && allowed.has((value as RuntimeMessage).type));
}
