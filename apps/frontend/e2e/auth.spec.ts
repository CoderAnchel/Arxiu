/** Phase-6 E2E: smoke flow that proves the dev stack is wired end-to-end.
 *
 * Pre-req for `pnpm e2e`:
 *   1. `make dev` (compose stack up)
 *   2. `make migrate && make seed`  — the seed prints an admin password
 *      to seed_credentials.csv. Set ADMIN_PASSWORD before running.
 */
import { expect, test } from "@playwright/test";

const ADMIN_DNI = process.env.ADMIN_DNI ?? "00000000T";
const ADMIN_PASSWORD = process.env.ADMIN_PASSWORD ?? "Admin-Pwd-1!";

test.describe("Auth flow", () => {
  test("redirects unauthenticated to /login", async ({ page }) => {
    await page.goto("/curriculums");
    await expect(page).toHaveURL(/\/login$/);
    await expect(page.getByRole("heading", { name: "Arxiu de notes" })).toBeVisible();
  });

  test("admin login → dashboard → logout", async ({ page }) => {
    await page.goto("/login");
    await page.getByLabel(/DNI o email/i).fill(ADMIN_DNI);
    await page.getByLabel(/Contrasenya/i).fill(ADMIN_PASSWORD);
    await page.getByRole("button", { name: /Entrar/ }).click();

    // Either we get the dashboard placeholder, or — if we hit the real index —
    // we'll see the sidebar with our Arxiu brand mark.
    await expect(page.locator(".brandTitle, [class*='brandTitle']").first())
      .toBeVisible({ timeout: 10_000 });

    // Navigate to a fully wired page
    await page.getByRole("link", { name: "Currículums" }).click();
    await expect(page).toHaveURL(/\/curriculums$/);

    // Logout via topbar
    await page.getByRole("button", { name: /Sortir/ }).click();
    await expect(page).toHaveURL(/\/login$/);
  });

  test("rejects bad credentials", async ({ page }) => {
    await page.goto("/login");
    await page.getByLabel(/DNI o email/i).fill("00000000T");
    await page.getByLabel(/Contrasenya/i).fill("definitely-wrong");
    await page.getByRole("button", { name: /Entrar/ }).click();
    await expect(page.getByText(/incorrectes|2FA/i)).toBeVisible({ timeout: 8_000 });
  });
});
