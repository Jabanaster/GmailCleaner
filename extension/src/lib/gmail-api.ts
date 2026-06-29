import type { GmailMessageSummary } from "./types";

const GMAIL_API = "https://gmail.googleapis.com/gmail/v1/users/me";

async function gmailFetch<T>(path: string, token: string): Promise<T> {
  const response = await fetch(`${GMAIL_API}${path}`, { headers: { Authorization: `Bearer ${token}` } });
  if (!response.ok) throw new Error(`Gmail API returned ${response.status}`);
  return (await response.json()) as T;
}

type GmailPayload = { headers?: Array<{ name: string; value: string }> };
type GmailMessage = { id: string; threadId: string; snippet?: string; labelIds?: string[]; internalDate?: string; payload?: GmailPayload };

function header(message: GmailMessage, name: string): string {
  return message.payload?.headers?.find((item) => item.name.toLowerCase() === name.toLowerCase())?.value ?? "";
}

export function summarizeMessage(message: GmailMessage): GmailMessageSummary {
  return {
    id: message.id,
    threadId: message.threadId,
    subject: header(message, "Subject") || "(No subject)",
    from: header(message, "From") || "Unknown sender",
    receivedAt: message.internalDate ? new Date(Number(message.internalDate)).toISOString() : undefined,
    snippet: message.snippet ?? "",
    labelIds: message.labelIds ?? []
  };
}

export async function listMessages(token: string, limit: number): Promise<Array<{ id: string; threadId: string }>> {
  const query = new URLSearchParams({ maxResults: String(limit), labelIds: "INBOX" });
  const result = await gmailFetch<{ messages?: Array<{ id: string; threadId: string }> }>(`/messages?${query}`, token);
  return result.messages ?? [];
}

export async function getMessage(token: string, messageId: string): Promise<GmailMessageSummary> {
  const query = new URLSearchParams({ format: "metadata", metadataHeaders: "Subject" });
  query.append("metadataHeaders", "From");
  return summarizeMessage(await gmailFetch<GmailMessage>(`/messages/${encodeURIComponent(messageId)}?${query}`, token));
}

export async function listLabels(token: string): Promise<Array<{ id: string; name: string }>> {
  const result = await gmailFetch<{ labels?: Array<{ id: string; name: string }> }>("/labels", token);
  return result.labels ?? [];
}
