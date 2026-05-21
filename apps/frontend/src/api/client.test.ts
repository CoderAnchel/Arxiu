/** API client — auth header injection + 401 refresh-and-retry. */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { api, configureClient } from "./client";

let token: string | null = "TOKEN1";

beforeEach(() => {
  token = "TOKEN1";
  configureClient({
    getAccessToken: () => token,
    setAccessToken: t => {
      token = t;
    },
    onAuthLost: () => {
      token = null;
    },
  });
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("api client", () => {
  it("injects the access token", async () => {
    const fetchMock = vi.fn(
      async () => new Response("{}", { status: 200, headers: { "Content-Type": "application/json" } }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await api("/test");

    const init = fetchMock.mock.calls[0]![1] as RequestInit;
    expect((init.headers as Record<string, string>).Authorization).toBe("Bearer TOKEN1");
  });

  it("refreshes once on 401 and retries", async () => {
    let n = 0;
    const fetchMock = vi.fn(async (url: string) => {
      n += 1;
      if (url.endsWith("/auth/refresh")) {
        return new Response(JSON.stringify({ access_token: "TOKEN2" }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      }
      if (n === 1) {
        return new Response("{}", { status: 401 });
      }
      return new Response(JSON.stringify({ ok: true }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    });
    vi.stubGlobal("fetch", fetchMock);

    const res = await api<{ ok: boolean }>("/test");
    expect(res).toEqual({ ok: true });
    expect(token).toBe("TOKEN2");
    // initial + refresh + retry
    expect(fetchMock).toHaveBeenCalledTimes(3);
  });

  it("calls onAuthLost when refresh also fails", async () => {
    const fetchMock = vi.fn(async () => new Response("{}", { status: 401 }));
    vi.stubGlobal("fetch", fetchMock);

    await expect(api("/test")).rejects.toMatchObject({ status: 401 });
    expect(token).toBeNull();
  });
});
