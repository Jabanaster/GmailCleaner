import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("../src/lib/chrome-storage", () => ({ getSettings: vi.fn(async () => ({ backendBaseUrl: "https://api.example.com" })) }));
import { backendRequest } from "../src/lib/backend-client";

describe("backend error redaction", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("does not expose authorization headers or response payloads in errors", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({ detail: "secret-response-data" }), { status: 401, headers: { "Content-Type": "application/json" } })));
    let message = "";
    try { await backendRequest("/api/extension/auth/me", { accessToken: "secret-access-token" }); }
    catch (error) { message = error instanceof Error ? error.message : String(error); }
    expect(message).toContain("401");
    expect(message).not.toContain("secret-access-token");
    expect(message).not.toContain("secret-response-data");
  });
});
