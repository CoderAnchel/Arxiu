/** Forced password change screen — reached when the user has must_change_password=true. */
import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { Navigate, useNavigate } from "react-router-dom";
import { z } from "zod";

import { authApi } from "@/api/auth";
import type { ApiError } from "@/api/client";
import { useAuthStore } from "@/stores/authStore";

import styles from "./Login.module.css";

const schema = z
  .object({
    current_password: z.string().min(1, "Cal la contrasenya temporal"),
    new_password: z.string().min(12, "Mínim 12 caràcters"),
    confirm: z.string().min(12),
  })
  .refine(d => d.new_password === d.confirm, {
    path: ["confirm"],
    message: "Les contrasenyes no coincideixen",
  });
type FormValues = z.infer<typeof schema>;

export function ChangePassword() {
  const status = useAuthStore(s => s.status);
  const passwordChangeToken = useAuthStore(s => s.passwordChangeToken);
  const setStatus = useAuthStore(s => s.setStatus);
  const setAccessToken = useAuthStore(s => s.setAccessToken);
  const setPasswordChangeToken = useAuthStore(s => s.setPasswordChangeToken);
  const navigate = useNavigate();
  const [submitError, setSubmitError] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { current_password: "", new_password: "", confirm: "" },
  });

  if (status === "anonymous") return <Navigate to="/login" replace />;
  if (status === "authenticated") return <Navigate to="/" replace />;

  const onSubmit = async (values: FormValues) => {
    setSubmitError(null);
    try {
      // The backend accepts the password-change-scoped token here.
      await authApi.changePassword(
        { current_password: values.current_password, new_password: values.new_password },
        passwordChangeToken ?? undefined,
      );

      // After success, server has set a fresh refresh cookie. Refresh access token + me.
      const refreshed = await authApi.refresh();
      setAccessToken(refreshed.access_token);
      setPasswordChangeToken(null);
      const me = await authApi.me();
      useAuthStore.getState().setUser(me);
      setStatus("authenticated");
      navigate("/", { replace: true });
    } catch (err) {
      const e = err as ApiError;
      const msg =
        e.code === "invalid_credentials"
          ? "La contrasenya temporal no és correcta."
          : e.message || "No s'ha pogut canviar la contrasenya";
      setSubmitError(msg);
    }
  };

  return (
    <main className={styles.shell}>
      <section className={styles.card}>
        <header className={styles.brand}>
          <span className={styles.brandMark}>A</span>
          <h1>Canvi obligatori</h1>
          <p className={styles.eyebrow}>Has d'establir una contrasenya pròpia</p>
        </header>

        <form className={styles.form} onSubmit={handleSubmit(onSubmit)} noValidate>
          <label className={styles.field}>
            <span>Contrasenya temporal</span>
            <input
              {...register("current_password")}
              type="password"
              autoComplete="current-password"
              autoFocus
              aria-invalid={!!errors.current_password}
            />
            {errors.current_password && (
              <em className={styles.fieldError}>{errors.current_password.message}</em>
            )}
          </label>

          <label className={styles.field}>
            <span>Nova contrasenya (mín. 12 caràcters)</span>
            <input
              {...register("new_password")}
              type="password"
              autoComplete="new-password"
              aria-invalid={!!errors.new_password}
            />
            {errors.new_password && <em className={styles.fieldError}>{errors.new_password.message}</em>}
          </label>

          <label className={styles.field}>
            <span>Repeteix la nova contrasenya</span>
            <input
              {...register("confirm")}
              type="password"
              autoComplete="new-password"
              aria-invalid={!!errors.confirm}
            />
            {errors.confirm && <em className={styles.fieldError}>{errors.confirm.message}</em>}
          </label>

          {submitError && <p className={styles.formError}>{submitError}</p>}

          <button type="submit" className={styles.submit} disabled={isSubmitting}>
            {isSubmitting ? "Canviant…" : "Canviar contrasenya i entrar"}
          </button>
        </form>
      </section>
    </main>
  );
}
