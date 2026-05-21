/** QualifsPage — unit tests for the comment editor popup and dirty tracking.
 *
 * Full integration of the spreadsheet is covered in e2e; here we exercise
 * the comment editor in isolation since it has non-trivial focus + escape
 * + count behaviour.
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

// Pull only the CommentEditor by mocking the rest. The component is a
// named export internally; expose it via re-export so we can test it.
import { CommentEditor } from "./QualifsPage.testing";

function setup(initial = "") {
  const onSave = vi.fn();
  const onClose = vi.fn();
  const qc = new QueryClient();
  render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <CommentEditor
          alumneLabel="Vilanova, Aleix"
          raLabel="RA1"
          initial={initial}
          onSave={onSave}
          onClose={onClose}
        />
      </MemoryRouter>
    </QueryClientProvider>,
  );
  return { onSave, onClose };
}

describe("CommentEditor", () => {
  it("renders alumne + RA labels", () => {
    setup("");
    expect(screen.getByText(/Comentari · RA1/)).toBeInTheDocument();
    expect(screen.getByText("Vilanova, Aleix")).toBeInTheDocument();
  });

  it("calls onSave with the entered text", async () => {
    const { onSave } = setup("");
    const user = userEvent.setup();
    const ta = screen.getByPlaceholderText(/Observacions/);
    await user.type(ta, "hola");
    await user.click(screen.getByRole("button", { name: /Aplicar/ }));
    expect(onSave).toHaveBeenCalledWith("hola");
  });

  it("preserves the initial value in the textarea", () => {
    setup("existing comment");
    expect(screen.getByDisplayValue("existing comment")).toBeInTheDocument();
  });

  it("shows live char count", async () => {
    setup("");
    const user = userEvent.setup();
    await user.type(screen.getByPlaceholderText(/Observacions/), "abc");
    expect(screen.getByText("3 / 2000")).toBeInTheDocument();
  });

  it("closes on backdrop click", () => {
    const { onClose } = setup("");
    // The backdrop is the outermost div; click via testid-less route — simulate by
    // clicking on the popup parent.
    const backdrop = document.querySelector('[class*="commentBackdrop"]')!;
    fireEvent.click(backdrop);
    expect(onClose).toHaveBeenCalled();
  });
});
