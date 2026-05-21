/** Email/SMTP configuration tab — admin-only.
 *
 * Lets the admin set up SMTP (typically Gmail with an App Password) and test
 * the connection by sending a test email. The password is stored encrypted
 * server-side and never returned to the UI.
 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import { appSettingsApi, type SmtpSettings, type SmtpUpdate } from "@/api/appSettings";
import { Button } from "@/components/ui/Button";
import { useAuthStore } from "@/stores/authStore";
import { toast } from "@/stores/toastStore";

import styles from "./AdminPage.module.css";

type FormState = {
  smtp_host: string;
  smtp_port: number;
  smtp_username: string;
  smtp_password: string; // empty = no change
  clearPassword: boolean;
  smtp_from_email: string;
  smtp_from_name: string;
  smtp_use_tls: boolean;
};

const GMAIL_DEFAULTS: Partial<FormState> = {
  smtp_host: "smtp.gmail.com",
  smtp_port: 587,
  smtp_use_tls: true,
};

function fromSettings(s: SmtpSettings | undefined): FormState {
  return {
    smtp_host: s?.smtp_host ?? "",
    smtp_port: s?.smtp_port ?? 587,
    smtp_username: s?.smtp_username ?? "",
    smtp_password: "",
    clearPassword: false,
    smtp_from_email: s?.smtp_from_email ?? "",
    smtp_from_name: s?.smtp_from_name ?? "",
    smtp_use_tls: s?.smtp_use_tls ?? true,
  };
}

export function EmailTab() {
  const qc = useQueryClient();
  const currentEmail = useAuthStore(s => s.user?.email ?? "");
  const settings = useQuery({
    queryKey: ["smtp-settings"],
    queryFn: () => appSettingsApi.getSmtp(),
  });

  const [form, setForm] = useState<FormState>(fromSettings(settings.data));
  useEffect(() => {
    if (settings.data) setForm(fromSettings(settings.data));
  }, [settings.data]);

  const [showHelp, setShowHelp] = useState(false);
  const [testTo, setTestTo] = useState("");
  useEffect(() => {
    if (currentEmail && !testTo) setTestTo(currentEmail);
  }, [currentEmail, testTo]);

  const set = <K extends keyof FormState>(k: K, v: FormState[K]) =>
    setForm(f => ({ ...f, [k]: v }));

  const saveMut = useMutation({
    mutationFn: (body: SmtpUpdate) => appSettingsApi.updateSmtp(body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["smtp-settings"] });
      toast.success("Configuració SMTP desada");
    },
    onError: (err: Error) => toast.error(err.message || "Error en desar"),
  });

  const testMut = useMutation({
    mutationFn: (toEmail: string) =>
      appSettingsApi.testSmtp({
        to: toEmail,
        // Try with the form values (un-saved) so admin can validate before persisting.
        smtp_host: form.smtp_host || undefined,
        smtp_port: form.smtp_port,
        smtp_username: form.smtp_username || undefined,
        smtp_password: form.smtp_password || undefined,
        smtp_from_email: form.smtp_from_email || undefined,
        smtp_from_name: form.smtp_from_name || undefined,
        smtp_use_tls: form.smtp_use_tls,
      }),
    onSuccess: r => {
      if (r.ok) toast.success(r.detail);
      else toast.error(r.detail);
    },
    onError: (err: Error) => toast.error(err.message),
  });

  const submit = () => {
    const body: SmtpUpdate = {
      smtp_host: form.smtp_host || undefined,
      smtp_port: form.smtp_port,
      smtp_username: form.smtp_username || undefined,
      smtp_from_email: form.smtp_from_email || undefined,
      smtp_from_name: form.smtp_from_name || undefined,
      smtp_use_tls: form.smtp_use_tls,
    };
    if (form.clearPassword) body.smtp_password = "";
    else if (form.smtp_password) body.smtp_password = form.smtp_password;
    // else: omit smtp_password → backend keeps the existing one
    saveMut.mutate(body);
  };

  const applyGmailDefaults = () => {
    setForm(f => ({ ...f, ...GMAIL_DEFAULTS }));
    toast.success("Valors per defecte de Gmail aplicats");
  };

  return (
    <>
      <div className={styles.panelHead}>
        <div>
          <span className={styles.panelTitle}>Configuració SMTP</span>
          {settings.data?.updated_at && (
            <p className={styles.muted} style={{ margin: "4px 0 0", padding: 0, textAlign: "left" }}>
              Última actualització:{" "}
              {new Date(settings.data.updated_at).toLocaleString("ca-ES")}
            </p>
          )}
        </div>
        <div className={styles.toolbar}>
          <Button onClick={() => setShowHelp(s => !s)}>
            {showHelp ? "Amagar guia Gmail" : "ℹ Com configurar Gmail"}
          </Button>
          <Button onClick={applyGmailDefaults}>Servir-se per Gmail</Button>
        </div>
      </div>

      {showHelp && <GmailHelp />}

      <div style={{ padding: 18 }}>
        <div className={styles.formGrid}>
          <label className={styles.field}>
            <span>Servidor SMTP *</span>
            <input
              value={form.smtp_host}
              onChange={e => set("smtp_host", e.target.value)}
              placeholder="smtp.gmail.com"
            />
          </label>
          <label className={styles.field}>
            <span>Port *</span>
            <input
              type="number"
              min={1}
              max={65535}
              value={form.smtp_port}
              onChange={e => set("smtp_port", Number(e.target.value))}
              placeholder="587"
            />
          </label>

          <label className={styles.field}>
            <span>Usuari (compte d'enviament)</span>
            <input
              value={form.smtp_username}
              onChange={e => set("smtp_username", e.target.value)}
              placeholder="centre@inslaferreria.cat"
            />
          </label>
          <label className={styles.field}>
            <span>
              Contrasenya{" "}
              {settings.data?.has_password && !form.smtp_password && !form.clearPassword && (
                <span style={{ color: "var(--accent)", textTransform: "none" }}>
                  · (ja desada — deixa buit per mantenir-la)
                </span>
              )}
            </span>
            <input
              type="password"
              value={form.smtp_password}
              onChange={e => {
                set("smtp_password", e.target.value);
                if (form.clearPassword) set("clearPassword", false);
              }}
              placeholder={
                settings.data?.has_password
                  ? "•••••••••••• (sense canvis)"
                  : "App password de Gmail"
              }
              autoComplete="new-password"
            />
            {settings.data?.has_password && (
              <label className={styles.checkbox} style={{ marginTop: 6 }}>
                <input
                  type="checkbox"
                  checked={form.clearPassword}
                  onChange={e => {
                    set("clearPassword", e.target.checked);
                    if (e.target.checked) set("smtp_password", "");
                  }}
                />
                <span>Esborrar contrasenya actual</span>
              </label>
            )}
          </label>

          <label className={styles.field}>
            <span>Remitent — Email *</span>
            <input
              type="email"
              value={form.smtp_from_email}
              onChange={e => set("smtp_from_email", e.target.value)}
              placeholder="no-reply@inslaferreria.cat"
            />
          </label>
          <label className={styles.field}>
            <span>Remitent — Nom</span>
            <input
              value={form.smtp_from_name}
              onChange={e => set("smtp_from_name", e.target.value)}
              placeholder="Institut la Ferreria"
            />
          </label>

          <label className={`${styles.checkbox} ${styles.full}`}>
            <input
              type="checkbox"
              checked={form.smtp_use_tls}
              onChange={e => set("smtp_use_tls", e.target.checked)}
            />
            <span>
              <strong>Usar TLS</strong> — recomanat. Per a Gmail i la majoria
              de proveïdors moderns ha d'estar marcat. STARTTLS al port 587, TLS
              implícit al port 465.
            </span>
          </label>
        </div>

        <div
          style={{
            borderTop: "1px solid var(--line)",
            marginTop: 18,
            paddingTop: 14,
            display: "flex",
            gap: 12,
            alignItems: "flex-end",
            flexWrap: "wrap",
          }}
        >
          <label className={styles.field} style={{ flex: "1 1 320px" }}>
            <span>Email per a la prova</span>
            <input
              type="email"
              value={testTo}
              onChange={e => setTestTo(e.target.value)}
              placeholder="el-teu@email.cat"
            />
          </label>
          <Button
            disabled={!testTo || testMut.isPending || !form.smtp_host || !form.smtp_from_email}
            onClick={() => testMut.mutate(testTo)}
            title="Envia un correu de prova amb la configuració actual (sense necessitat de guardar abans)"
          >
            {testMut.isPending ? "Provant…" : "Enviar prova"}
          </Button>
          <span style={{ flex: 1 }} />
          <Button
            variant="primary"
            disabled={saveMut.isPending || !form.smtp_host || !form.smtp_from_email}
            onClick={submit}
          >
            {saveMut.isPending ? "Desant…" : "Desar configuració"}
          </Button>
        </div>
      </div>
    </>
  );
}

function GmailHelp() {
  return (
    <div
      style={{
        background: "var(--bg-2)",
        border: "1px solid var(--line)",
        borderRadius: "var(--r)",
        padding: "16px 20px",
        margin: "0 18px 18px",
        fontSize: 13,
        lineHeight: 1.55,
        color: "var(--ink-2)",
      }}
    >
      <h3
        style={{
          margin: "0 0 10px",
          fontFamily: "var(--serif)",
          fontStyle: "italic",
          fontSize: 18,
          color: "var(--ink)",
        }}
      >
        Configurar enviament d'emails amb Gmail
      </h3>
      <p style={{ margin: "0 0 10px" }}>
        Per enviar butlletins i credencials des d'un compte Gmail (recomanat
        per a la majoria d'instituts), <strong>NO s'usa la contrasenya
        habitual del compte</strong>. Cal generar una "Contrasenya
        d'aplicació" (App Password) específica.
      </p>
      <ol style={{ margin: "0 0 10px", paddingLeft: 20 }}>
        <li style={{ marginBottom: 6 }}>
          Activa la <strong>verificació en dos passos (2FA)</strong> al compte
          Gmail des de <code>myaccount.google.com</code> → "Seguretat" → "Verificació
          en 2 passos". Si no està activada, no podràs crear App Passwords.
        </li>
        <li style={{ marginBottom: 6 }}>
          Ves a <code>myaccount.google.com/apppasswords</code> (o cerca "App
          passwords" a Configuració del compte).
        </li>
        <li style={{ marginBottom: 6 }}>
          Crea una nova App Password — anomena-la per exemple "Arxiu Institut
          la Ferreria". Google generarà una contrasenya de 16 caràcters tipus{" "}
          <code>abcd efgh ijkl mnop</code>.
        </li>
        <li style={{ marginBottom: 6 }}>
          Copia aquesta contrasenya (sense espais o amb ells, qualsevol funciona)
          i enganxa-la al camp <strong>Contrasenya</strong> d'aquesta pantalla.
        </li>
        <li style={{ marginBottom: 6 }}>
          Omple els altres camps amb:
          <ul style={{ margin: "4px 0", paddingLeft: 20 }}>
            <li><strong>Servidor SMTP:</strong> <code>smtp.gmail.com</code></li>
            <li><strong>Port:</strong> <code>587</code></li>
            <li><strong>Usuari:</strong> el teu compte Gmail (<code>centre@gmail.com</code>)</li>
            <li><strong>Remitent — Email:</strong> el mateix compte Gmail</li>
            <li><strong>Remitent — Nom:</strong> "Institut la Ferreria" o el que vulguis que vegi la família</li>
            <li><strong>Usar TLS:</strong> ✓ marcat</li>
          </ul>
        </li>
        <li style={{ marginBottom: 6 }}>
          Clica <strong>Enviar prova</strong> (amb el teu email com a destinatari) per validar que tot funciona.
        </li>
        <li>
          Si la prova arriba correctament, clica <strong>Desar configuració</strong>.
        </li>
      </ol>
      <p style={{ margin: "10px 0 0" }}>
        <strong>Notes importants:</strong>
      </p>
      <ul style={{ margin: "4px 0 0", paddingLeft: 20 }}>
        <li>
          La contrasenya es guarda <strong>encriptada</strong> al servidor i mai es retorna a la pantalla.
        </li>
        <li>
          Gmail limita a <strong>~500 emails/dia</strong> per compte gratuït i ~2000/dia per a comptes Workspace de centre.
          Per a un centre de mida normal és més que suficient.
        </li>
        <li>
          Si canvies de contrasenya principal del compte Gmail, l'App Password segueix funcionant. Si vols
          revocar-la, fes-ho des de la mateixa pàgina d'App Passwords de Google.
        </li>
        <li>
          Si el centre té <strong>Google Workspace</strong> propi, valora demanar a l'IT del centre que us creï un
          compte dedicat tipus <code>noreply@inslaferreria.cat</code> en lloc de fer servir un compte personal.
        </li>
      </ul>
    </div>
  );
}
