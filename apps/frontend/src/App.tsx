/**
 * App routing — full system.
 *
 * Index   → OverviewPage (dashboard)
 * /audit  → admin-only audit log
 * other 9 → feature pages
 */
import { Navigate, Route, Routes } from "react-router-dom";

import { AppShell } from "@/components/layout/AppShell";
import { AdminPage } from "@/features/admin/AdminPage";
import { AlumnesPage } from "@/features/alumnes/AlumnesPage";
import { AlumneExpedientPage } from "@/features/archive/AlumneExpedientPage";
import { GrupExpedientPage } from "@/features/archive/GrupExpedientPage";
import { AuditPage } from "@/features/audit/AuditPage";
import { AuthGuard } from "@/features/auth/AuthGuard";
import { AuthProvider } from "@/features/auth/AuthProvider";
import { ChangePassword } from "@/features/auth/ChangePassword";
import { Login } from "@/features/auth/Login";
import { AvaluacionsPage } from "@/features/avaluacions/AvaluacionsPage";
import { ButlletinsPage } from "@/features/butlletins/ButlletinsPage";
import { CurriculumsPage } from "@/features/curriculums/CurriculumsPage";
import { DocentsPage } from "@/features/docents/DocentsPage";
import { EnviamentsPage } from "@/features/enviaments/EnviamentsPage";
import { ImportacionsPage } from "@/features/importacions/ImportacionsPage";
import { OverviewPage } from "@/features/overview/OverviewPage";
import { QualifsPage } from "@/features/qualificacions/QualifsPage";
import { TrashPage } from "@/features/trash/TrashPage";

export function App() {
  return (
    <AuthProvider>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/change-password" element={<ChangePassword />} />

        <Route
          path="/"
          element={
            <AuthGuard>
              <AppShell />
            </AuthGuard>
          }
        >
          <Route index element={<OverviewPage />} />
          <Route path="curriculums" element={<CurriculumsPage />} />
          <Route path="qualificacions" element={<QualifsPage />} />
          <Route path="avaluacions" element={<AvaluacionsPage />} />
          <Route path="alumnes" element={<AlumnesPage />} />
          <Route path="alumnes/:id/expedient" element={<AlumneExpedientPage />} />
          <Route path="grups/:id/expedient" element={<GrupExpedientPage />} />
          <Route path="docents" element={<DocentsPage />} />
          <Route path="butlletins" element={<ButlletinsPage />} />
          <Route path="enviaments" element={<EnviamentsPage />} />
          <Route
            path="importacions"
            element={
              <AuthGuard requireRole="admin">
                <ImportacionsPage />
              </AuthGuard>
            }
          />
          <Route
            path="administracio"
            element={
              <AuthGuard requireRole="admin">
                <AdminPage />
              </AuthGuard>
            }
          />
          <Route
            path="audit"
            element={
              <AuthGuard requireRole="admin">
                <AuditPage />
              </AuthGuard>
            }
          />
          <Route
            path="paperera"
            element={
              <AuthGuard requireRole="admin">
                <TrashPage />
              </AuthGuard>
            }
          />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </AuthProvider>
  );
}
