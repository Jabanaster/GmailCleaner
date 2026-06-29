import { beforeEach, describe, expect, it, vi } from "vitest";

const localData: Record<string, unknown> = {};
const sessionData: Record<string, unknown> = {};
function area(data: Record<string, unknown>) {
  return {
    get: vi.fn(async (key: string) => ({ [key]: data[key] })),
    set: vi.fn(async (values: Record<string, unknown>) => Object.assign(data, values)),
    remove: vi.fn(async (key: string) => { delete data[key]; })
  };
}
const local = area(localData);
const session = area(sessionData);
vi.stubGlobal("chrome", { storage: { local, session } });

import { getBackendAccessToken, getBackendRefreshToken, saveSettings, setBackendAccessToken, setBackendRefreshToken } from "../src/lib/chrome-storage";

describe("credential storage", () => {
  beforeEach(() => { for (const key of Object.keys(localData)) delete localData[key]; for (const key of Object.keys(sessionData)) delete sessionData[key]; vi.clearAllMocks(); });

  it("stores access tokens only in session storage", async () => {
    await setBackendAccessToken("access-secret");
    expect(await getBackendAccessToken()).toBe("access-secret");
    expect(session.set).toHaveBeenCalled();
    expect(JSON.stringify(localData)).not.toContain("access-secret");
  });

  it("clears both credentials when the normalized backend URL changes", async () => {
    await setBackendAccessToken("access-secret"); await setBackendRefreshToken("refresh-secret");
    await saveSettings({ backendBaseUrl: "https://api.example.com", scanLimit: 25, dryRunMode: true, lastScanAt: null });
    expect(await getBackendAccessToken()).toBeNull();
    expect(await getBackendRefreshToken()).toBeNull();
  });
});
