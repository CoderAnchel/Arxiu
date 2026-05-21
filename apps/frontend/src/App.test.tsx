/**
 * Phase 1 smoke test: an unauthenticated user lands on the login screen.
 *
 * The AuthProvider tries POST /auth/refresh on mount; we mock fetch to fail it
 * (simulating no refresh cookie), so the auth store moves to "anonymous" and
 * AuthGuard redirects to /login.
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { App } from "./App";
import { useAuthStore } from "./stores/authStore";

function renderApp() {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={["/"]}>
        <App />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("App routing", () => {
  beforeEach(() => {
    useAuthStore.getState().reset();
    useAuthStore.setState({ status: "loading" });
  });

  it("redirects unauthenticated users to /login", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response(null, { status: 401 })),
    );

    renderApp();

    await waitFor(() =>
      expect(screen.getByRole("heading", { name: "Arxiu de notes" })).toBeInTheDocument(),
    );
    expect(screen.getByLabelText(/DNI o email/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Contrasenya/i)).toBeInTheDocument();
  });
});
