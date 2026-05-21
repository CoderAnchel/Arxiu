/** Login page. Identifier accepts DNI or email. */
import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { Navigate, useLocation, useNavigate } from "react-router-dom";
import { z } from "zod";

import { authApi } from "@/api/auth";
import type { ApiError } from "@/api/client";
import { useAuthStore } from "@/stores/authStore";

import styles from "./Login.module.css";

const schema = z.object({
  identifier: z
    .string()
    .min(1, "Cal el DNI o email")
    .max(150, "Massa llarg"),
  password: z.string().min(1, "Cal la contrasenya"),
  totp_code: z.string().optional(),
});
type FormValues = z.infer<typeof schema>;

export function Login() {
  const status = useAuthStore(s => s.status);
  const setAccessToken = useAuthStore(s => s.setAccessToken);
  const setPasswordChangeToken = useAuthStore(s => s.setPasswordChangeToken);
  const setStatus = useAuthStore(s => s.setStatus);
  const location = useLocation();
  const navigate = useNavigate();
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [needsTotp, setNeedsTotp] = useState(false);

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { identifier: "", password: "" },
  });

  if (status === "authenticated") return <Navigate to="/" replace />;
  if (status === "must_change_password") return <Navigate to="/change-password" replace />;

  const onSubmit = async (values: FormValues) => {
    setSubmitError(null);
    try {
      const res = await authApi.login(values);
      if (res.must_change_password && res.password_change_token) {
        setPasswordChangeToken(res.password_change_token);
        setStatus("must_change_password");
        navigate("/change-password", { replace: true });
        return;
      }
      if (res.access_token) {
        setAccessToken(res.access_token);
        const me = await authApi.me();
        useAuthStore.getState().setUser(me);
        setStatus("authenticated");
        const target = (location.state as { from?: string } | null)?.from ?? "/";
        navigate(target, { replace: true });
      }
    } catch (err) {
      const e = err as ApiError;
      if (e.code === "invalid_credentials" && !needsTotp && values.totp_code === undefined) {
        // Could be MFA; let the user retry with a code.
        setNeedsTotp(true);
        setSubmitError("Credencials incorrectes. Si tens 2FA activat, introdueix el codi.");
        return;
      }
      const msg =
        e.code === "invalid_credentials"
          ? "DNI/email o contrasenya incorrectes."
          : e.code === "account_inactive"
            ? "El compte està inactiu. Contacta amb administració."
            : e.message || "Error en l'autenticació";
      setSubmitError(msg);
    }
  };

  return (
    <main className={styles.shell}>
      <section className={styles.card}>
        <header className={styles.brand}>
          <span className={styles.brandMark}>A</span>
          <h1>Arxiu de notes</h1>
          <p className={styles.eyebrow}>Institut la Ferreria</p>
        </header>

        <form className={styles.form} onSubmit={handleSubmit(onSubmit)} noValidate>
          <label className={styles.field}>
            <span>DNI o email</span>
            <input
              {...register("identifier")}
              type="text"
              autoComplete="username"
              autoFocus
              placeholder="12345678Z o nom@inslaferreria.cat"
              aria-invalid={!!errors.identifier}
            />
            {errors.identifier && <em className={styles.fieldError}>{errors.identifier.message}</em>}
          </label>

          <label className={styles.field}>
            <span>Contrasenya</span>
            <input
              {...register("password")}
              type="password"
              autoComplete="current-password"
              aria-invalid={!!errors.password}
            />
            {errors.password && <em className={styles.fieldError}>{errors.password.message}</em>}
          </label>

          {needsTotp && (
            <label className={styles.field}>
              <span>Codi 2FA</span>
              <input
                {...register("totp_code")}
                type="text"
                inputMode="numeric"
                pattern="[0-9]*"
                maxLength={8}
                autoComplete="one-time-code"
                placeholder="123456"
              />
            </label>
          )}

          {submitError && <p className={styles.formError}>{submitError}</p>}

          <button type="submit" className={styles.submit} disabled={isSubmitting}>
            {isSubmitting ? "Entrant…" : "Entrar"}
          </button>
        </form>

        <footer className={styles.footer}>
          Si has oblidat la contrasenya, contacta amb l'administració del centre.
        </footer>
      </section>
    </main>
  );
}
