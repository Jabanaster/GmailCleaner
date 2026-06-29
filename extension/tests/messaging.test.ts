import { describe, expect, it } from "vitest";
import { isRuntimeMessage } from "../src/lib/messaging";

describe("runtime router boundary", () => {
  it("accepts allowlisted operations", () => expect(isRuntimeMessage({ type: "backend:authStatus" })).toBe(true));
  it("rejects unknown and arbitrary request operations", () => {
    expect(isRuntimeMessage({ type: "backend:request", url: "https://evil.example" })).toBe(false);
    expect(isRuntimeMessage({ type: "backend:getCredentials" })).toBe(false);
    expect(isRuntimeMessage({ type: "unknown" })).toBe(false);
  });
});
