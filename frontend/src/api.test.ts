import { describe, it, expect, vi, afterEach } from "vitest";
import { api, setAccess, ApiError } from "./api";
afterEach(() => {
  vi.unstubAllGlobals();
  setAccess(null);
});
describe("API authentication and errors", () => {
  it("sends the access token in an Authorization header", async () => {
    const fetcher = vi
      .fn()
      .mockResolvedValue(new Response('{"ok":true}', { status: 200 }));
    vi.stubGlobal("fetch", fetcher);
    setAccess("ephemeral-token");
    await api("/members");
    expect(fetcher.mock.calls[0][1].headers.get("Authorization")).toBe(
      "Bearer ephemeral-token",
    );
    expect(fetcher.mock.calls[0][1].credentials).toBe("include");
  });
  it("exposes validation fields instead of fabricating success", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({
            error: {
              message: "Check fields",
              fields: [{ field: "amount", message: "must be positive" }],
            },
          }),
          { status: 422 },
        ),
      ),
    );
    await expect(api("/payments")).rejects.toThrow("amount: must be positive");
  });
  it("does not renew on a rejected login", async () => {
    const fetcher = vi
      .fn()
      .mockResolvedValue(
        new Response('{"error":{"message":"Invalid login"}}', { status: 401 }),
      );
    vi.stubGlobal("fetch", fetcher);
    await expect(api("/auth/login")).rejects.toBeInstanceOf(ApiError);
    expect(fetcher).toHaveBeenCalledTimes(1);
  });
});
