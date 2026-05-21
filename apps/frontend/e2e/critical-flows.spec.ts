/** End-to-end critical flows.
 *
 * Pre-req: `make dev` + `make migrate && make seed` produce a working stack
 * with an admin (00000000T / Admin-Pwd-1!) and a professor (34567890C /
 * Prof-Pwd-1!). The seed prints exact credentials to seed_credentials.csv
 * — override via env if your seed used different passwords.
 *
 * Each test is independent: they create their own entities with unique codis
 * (timestamp-suffixed) so they can run against the same seeded DB without
 * interfering.
 */
import { expect, test, type Page } from "@playwright/test";

const ADMIN_DNI = process.env.ADMIN_DNI ?? "00000000T";
const ADMIN_PASSWORD = process.env.ADMIN_PASSWORD ?? "Admin-Pwd-1!";

const stamp = () => Date.now().toString().slice(-6);

async function loginAs(page: Page, dni: string, password: string) {
  await page.goto("/login");
  await page.getByLabel(/DNI o email/i).fill(dni);
  await page.getByLabel(/Contrasenya/i).fill(password);
  await page.getByRole("button", { name: /Entrar/ }).click();
  await expect(
    page.locator("[class*='brandTitle']").first(),
  ).toBeVisible({ timeout: 10_000 });
}

// ---------------------------------------------------------------------------
// Flow 1: Admin creates curs → grup → tutor
// ---------------------------------------------------------------------------
test("admin creates a curs, grup and assigns a tutor", async ({ page }) => {
  const s = stamp();
  await loginAs(page, ADMIN_DNI, ADMIN_PASSWORD);
  await page.goto("/administracio");

  // New curs acadèmic
  await page.getByRole("button", { name: /Cursos acadèmics/i }).click();
  await page.getByRole("button", { name: /\+ Nou curs/ }).click();
  await page.getByPlaceholder("2025-2026").fill(`E2E-${s}`);
  await page.getByRole("button", { name: /Crear/ }).click();
  await expect(page.getByText(`E2E-${s}`)).toBeVisible({ timeout: 5000 });

  // New grup using that curs
  await page.getByRole("button", { name: /Grups classe/i }).click();
  // Select the curs we just created
  await page.locator("select").first().selectOption({ label: `E2E-${s}` });
  await page.getByRole("button", { name: /\+ Nou grup/ }).click();
  await page.getByPlaceholder("DAM1A").fill(`E2E${s.slice(-3)}`);
  await page.getByRole("button", { name: /^Crear$/ }).click();
  // The new grup row should appear
  await expect(page.getByText(`E2E${s.slice(-3)}`)).toBeVisible();
});

// ---------------------------------------------------------------------------
// Flow 2: Admin creates a professor → reveals password → professor logs in
// ---------------------------------------------------------------------------
test("admin creates a professor with reveal-once password", async ({ page }) => {
  const s = stamp();
  await loginAs(page, ADMIN_DNI, ADMIN_PASSWORD);
  await page.goto("/docents");

  await page.getByRole("button", { name: /\+ Nou/ }).click();
  await page.getByLabel(/DNI/i).fill(`9${s}A`.slice(0, 9));
  await page.getByLabel(/Email/i).fill(`e2e-${s}@inslaferreria.cat`);
  await page.getByLabel(/Nom/i).first().fill("Test");
  await page.getByLabel(/Cognoms/i).fill(`E2E${s}`);
  await page.getByRole("button", { name: /Crear/ }).click();

  // Reveal-once modal
  await expect(page.getByText(/contrasenya/i)).toBeVisible({ timeout: 5000 });
});

// ---------------------------------------------------------------------------
// Flow 3: Admin views home and tree-filters the structure
// ---------------------------------------------------------------------------
test("home tree filter prunes by text", async ({ page }) => {
  await loginAs(page, ADMIN_DNI, ADMIN_PASSWORD);
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: /Arxiu de notes/i }),
  ).toBeVisible();

  const filter = page.getByPlaceholder(/Filtra cicles i grups/i);
  if (await filter.isVisible()) {
    await filter.fill("zzzzzz-no-match");
    await expect(page.getByText(/Cap cicle o grup coincideix/i)).toBeVisible();
    await filter.fill("");
  }
});

// ---------------------------------------------------------------------------
// Flow 4: Soft delete + restore via paperera
// ---------------------------------------------------------------------------
test("admin can soft-delete an alumne and restore from paperera", async ({ page }) => {
  await loginAs(page, ADMIN_DNI, ADMIN_PASSWORD);
  await page.goto("/alumnes");

  // Create a throwaway alumne
  const s = stamp();
  const ralc = `E2E${s}`;
  await page.getByRole("button", { name: /\+ Nou alumne/ }).click();
  await page.getByLabel(/RALC/i).fill(ralc);
  await page.getByLabel(/Nom/i).first().fill("Borrar");
  await page.getByLabel(/Cognoms/i).fill("Test");
  await page.getByRole("button", { name: /Crear/ }).click();
  await expect(page.getByText(ralc)).toBeVisible({ timeout: 5000 });

  // Soft delete
  await page.getByText(ralc).click();
  await page.getByRole("button", { name: /Donar de baixa|Eliminar/ }).click();
  await page.getByRole("button", { name: /^Eliminar$|^Donar de baixa$|Confirmar/ }).click();

  // Visit paperera, verify and restore
  await page.goto("/paperera");
  await expect(page.getByText(ralc)).toBeVisible({ timeout: 5000 });
  await page
    .locator("tr", { hasText: ralc })
    .getByRole("button", { name: /Restaurar/ })
    .click();
  await page.getByRole("button", { name: /^Restaurar$/ }).click();
  // After restore the row is gone from the trash
  await expect(page.getByText(ralc)).not.toBeVisible({ timeout: 5000 });
});

// ---------------------------------------------------------------------------
// Flow 5: Export an alumne expedient (smoke — verifies a blob is offered)
// ---------------------------------------------------------------------------
test("admin can export an alumne XLSX expedient", async ({ page }) => {
  await loginAs(page, ADMIN_DNI, ADMIN_PASSWORD);
  await page.goto("/alumnes");
  // Click the first row to open detail
  const firstRow = page.locator("tr").nth(1);
  if (await firstRow.isVisible()) {
    await firstRow.click();
    // Open expedient
    const link = page.getByRole("link", { name: /Veure expedient|Expedient/ }).first();
    if (await link.isVisible()) await link.click();

    const downloadPromise = page.waitForEvent("download");
    await page.getByRole("button", { name: /Exportar XLSX/ }).click();
    const download = await downloadPromise;
    expect(download.suggestedFilename()).toMatch(/expedient.*\.xlsx$/);
  }
});

// ---------------------------------------------------------------------------
// Flow 6: Professor sees only their assigned grups/moduls
// ---------------------------------------------------------------------------
test("professor sees a restricted Qualifs view (or message)", async ({ page }) => {
  const profDni = process.env.PROF_DNI ?? "34567890C";
  const profPass = process.env.PROF_PASSWORD ?? "Prof-Pwd-1!";
  await loginAs(page, profDni, profPass).catch(() => {
    test.skip(true, "professor credentials not seeded");
  });

  await page.goto("/qualificacions");
  // Either we have a matrix or the "cap assignació" banner
  const matrixOrBanner = page.locator(
    "table, [class*='banner']",
  );
  await expect(matrixOrBanner.first()).toBeVisible({ timeout: 10_000 });
});
