import { beforeEach, describe, expect, it, vi } from "vitest";
import { BackendError } from "../src/lib/backend-client";

const mocks = vi.hoisted(() => ({
  backend: { refresh: vi.fn(), me: vi.fn(), pair: vi.fn(), revoke: vi.fn(), classifyPreview: vi.fn(), health: vi.fn() },
  getAccess: vi.fn(), getRefresh: vi.fn(), setAccess: vi.fn(), setRefresh: vi.fn(), clear: vi.fn()
}));
vi.mock("../src/lib/backend-client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../src/lib/backend-client")>();
  return { ...actual, backend: mocks.backend };
});
vi.mock("../src/lib/chrome-storage", () => ({
  getBackendAccessToken: mocks.getAccess, getBackendRefreshToken: mocks.getRefresh,
  setBackendAccessToken: mocks.setAccess, setBackendRefreshToken: mocks.setRefresh, clearBackendCredentials: mocks.clear
}));

import { refreshBackendSession, withBackendAuth } from "../src/lib/backend-auth";

describe("backend authentication", () => {
  beforeEach(() => vi.clearAllMocks());

  it("retries authentication only once", async () => {
    mocks.getAccess.mockResolvedValue("old-access"); mocks.getRefresh.mockResolvedValue("refresh");
    mocks.backend.refresh.mockResolvedValue({ access_token: "new-access", refresh_token: "new-refresh" });
    const request = vi.fn().mockRejectedValueOnce(new BackendError("expired", "authentication", 401)).mockResolvedValue("ok");
    await expect(withBackendAuth(request)).resolves.toBe("ok");
    expect(request).toHaveBeenCalledTimes(2);
    expect(request).toHaveBeenLastCalledWith("new-access");
  });

  it("does not loop after a second 401", async () => {
    mocks.getAccess.mockResolvedValue("old-access"); mocks.getRefresh.mockResolvedValue("refresh");
    mocks.backend.refresh.mockResolvedValue({ access_token: "new-access", refresh_token: "new-refresh" });
    const request = vi.fn().mockRejectedValue(new BackendError("expired", "authentication", 401));
    await expect(withBackendAuth(request)).rejects.toMatchObject({ status: 401 });
    expect(request).toHaveBeenCalledTimes(2);
    expect(mocks.backend.refresh).toHaveBeenCalledTimes(1);
  });

  it("clears credentials after refresh failure", async () => {
    mocks.getRefresh.mockResolvedValue("refresh"); mocks.backend.refresh.mockRejectedValue(new BackendError("reuse", "authentication", 401));
    await expect(refreshBackendSession()).rejects.toBeInstanceOf(BackendError);
    expect(mocks.clear).toHaveBeenCalledOnce();
  });
});
