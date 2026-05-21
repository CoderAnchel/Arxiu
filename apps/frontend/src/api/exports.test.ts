/** Exports API client — test the blob download wiring with mocked fetch. */
import { afterEach, describe, expect, it, vi } from "vitest";

import { exportsApi } from "./exports";

const xlsxBlob = new Blob(["FAKE_XLSX"], {
  type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
});

function makeFetchMock(blob = xlsxBlob, filename = "alumne_x.xlsx") {
  return vi.fn(
    async (): Promise<Response> =>
      new Response(blob, {
        status: 200,
        headers: {
          "Content-Type": blob.type,
          "Content-Disposition": `attachment; filename="${filename}"`,
        },
      }),
  );
}

describe("exportsApi", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("calls the expected URL and triggers a download", async () => {
    const fetchMock = makeFetchMock();
    vi.stubGlobal("fetch", fetchMock);

    // jsdom doesn't implement createObjectURL; stub it
    const original = URL.createObjectURL;
    URL.createObjectURL = vi.fn(() => "blob:mock");
    URL.revokeObjectURL = vi.fn();

    await exportsApi.alumne(7, "TOKEN");

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const url = fetchMock.mock.calls[0]![0] as string;
    expect(url).toContain("/export/alumne/7.xlsx");
    const init = fetchMock.mock.calls[0]![1] as RequestInit;
    expect((init.headers as Record<string, string>).Authorization).toBe(
      "Bearer TOKEN",
    );

    URL.createObjectURL = original;
  });

  it("throws on non-ok response", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(
        async () =>
          new Response(JSON.stringify({ message: "permission_denied" }), {
            status: 403,
            headers: { "Content-Type": "application/json" },
          }),
      ),
    );
    await expect(exportsApi.alumne(7, null)).rejects.toThrow(/permission_denied/);
  });

  it("appends avaluacio_id query when provided", async () => {
    const fetchMock = makeFetchMock();
    vi.stubGlobal("fetch", fetchMock);
    URL.createObjectURL = vi.fn(() => "blob:mock");
    URL.revokeObjectURL = vi.fn();

    await exportsApi.grupModul(1, 2, 3, null);
    const url = fetchMock.mock.calls[0]![0] as string;
    expect(url).toContain("/export/grup/1/modul/2.xlsx?avaluacio_id=3");
  });
});
