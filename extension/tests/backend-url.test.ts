import { describe, expect, it } from "vitest";
import { isLocalDevelopmentUrl, normalizeBackendUrl } from "../src/lib/backend-url";

describe("backend URL policy", () => {
  it("permits explicit localhost HTTP development", () => {
    expect(normalizeBackendUrl("http://localhost:8000/")).toBe("http://localhost:8000");
    expect(normalizeBackendUrl("http://127.0.0.1:8000")).toBe("http://127.0.0.1:8000");
    expect(isLocalDevelopmentUrl("http://localhost:8000")).toBe(true);
  });

  it("rejects non-HTTPS production URLs", () => {
    expect(() => normalizeBackendUrl("http://api.example.com")).toThrow(/HTTPS/);
  });

  it("rejects URL credentials and paths", () => {
    expect(() => normalizeBackendUrl("https://user:pass@example.com")).toThrow(/credentials/);
    expect(() => normalizeBackendUrl("https://example.com/api")).toThrow(/path/);
  });
});
