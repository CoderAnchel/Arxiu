/** Docents page — list users, create with reveal-once password, regenerate, email. */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { adminApi, type AdminUser, type AdminUserCreate } from "@/api/admin";
import { catalogApi } from "@/api/catalog";
import type { ApiError } from "@/api/client";
import { exportsApi } from "@/api/exports";
import { assignacionsApi, grupsApi } from "@/api/grups";
import { Button } from "@/components/ui/Button";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import { Modal } from "@/components/ui/Modal";
import { useExport } from "@/hooks/useExport";
import { useAuthStore } from "@/stores/authStore";
import { toast } from "@/stores/toastStore";

import styles from "./DocentsPage.module.css";

export function DocentsPage() {
  const qc = useQueryClient();
  const users = useQuery({ queryKey: ["admin-users"], queryFn: () => adminApi.list() });
  const [searchParams] = useSearchParams();
  const accessToken = useAuthStore(s => s.accessToken);
  const currentUser = useAuthStore(s => s.user);
  const isAdmin = currentUser?.role === "admin";

  const [selected, setSelected] = useState<number | null>(null);
  const [bulkSelected, setBulkSelected] = useState<Set<number>>(new Set());
  const [bulkRunning, setBulkRunning] = useState(false);
  const [confirmBulk, setConfirmBulk] = useState(false);

  // Honour ?selected=ID coming from other pages (e.g. tutor link in GrupExpedient).
  useEffect(() => {
    const target = searchParams.get("selected");
    if (target && users.data?.some(u => u.id === Number(target))) {
      setSelected(Number(target));
    }
  }, [searchParams, users.data]);

  const toggleBulk = (id: number) =>
    setBulkSelected(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });

  const runBulkRegen = async () => {
    setBulkRunning(true);
    try {
      await adminApi.bulkGeneratePasswordsCsv(Array.from(bulkSelected), accessToken);
      toast.success(`${bulkSelected.size} contrasenyes regenerades · CSV descarregat`);
      setBulkSelected(new Set());
      setConfirmBulk(false);
    } catch (err) {
      toast.error((err as Error).message || "Bulk regen ha fallat");
    } finally {
      setBulkRunning(false);
    }
  };
  const [createOpen, setCreateOpen] = useState(false);
  const [revealedPassword, setRevealedPassword] = useState<{
    user: AdminUser;
    password: string;
  } | null>(null);
  const [confirmDelete, setConfirmDelete] = useState<AdminUser | null>(null);
  const [confirmRegen, setConfirmRegen] = useState<AdminUser | null>(null);

  const sel = users.data?.find(u => u.id === selected) ?? null;

  // --- Mutations -----------------------------------------------------------

  const createMut = useMutation({
    mutationFn: (body: AdminUserCreate) => adminApi.create(body),
    onSuccess: created => {
      qc.invalidateQueries({ queryKey: ["admin-users"] });
      setCreateOpen(false);
      setRevealedPassword({ user: created, password: created.generated_password });
      toast.success(`${created.nom} ${created.cognoms} creat amb contrasenya temporal`);
    },
    onError: (err: ApiError) => {
      const msg =
        err.code === "conflict"
          ? "Ja existeix un usuari amb aquest DNI o email"
          : err.message || "Error en crear l'usuari";
      toast.error(msg);
    },
  });

  const regenMut = useMutation({
    mutationFn: (id: number) => adminApi.regeneratePassword(id),
    onSuccess: data => {
      const u = users.data?.find(x => x.id === data.user_id);
      if (u) setRevealedPassword({ user: u, password: data.generated_password });
      toast.success("Nova contrasenya generada");
      qc.invalidateQueries({ queryKey: ["admin-users"] });
    },
    onError: () => toast.error("No s'ha pogut regenerar la contrasenya"),
  });

  const emailMut = useMutation({
    mutationFn: (id: number) => adminApi.emailPassword(id),
    onSuccess: () => toast.success("Contrasenya enviada per email"),
    onError: (err: ApiError) => {
      if (err.status === 410) {
        toast.warn("La contrasenya ja no és recuperable. Regenera'n una de nova.");
      } else {
        toast.error("No s'ha pogut enviar l'email");
      }
    },
  });

  const deleteMut = useMutation({
    mutationFn: (id: number) => adminApi.delete(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["admin-users"] });
      setSelected(null);
      toast.success("Usuari donat de baixa");
    },
    onError: () => toast.error("No s'ha pogut donar de baixa"),
  });

  // --- Render --------------------------------------------------------------

  return (
    <div className={styles.page}>
      <header className={styles.head}>
        <p className={styles.eyebrow}>Personal · {users.data?.length ?? 0} comptes</p>
        <h1 className={styles.title}>Docents</h1>
        <p className={styles.sub}>
          Crea i gestiona comptes d'admin i professorat. Quan crees un compte, el sistema
          genera una contrasenya forta que pots compartir manualment o enviar per email
          dins dels propers 5 minuts.
        </p>
      </header>

      {isAdmin && bulkSelected.size > 0 && (
        <div className={styles.bulkBar}>
          <span>
            <strong>{bulkSelected.size}</strong>{" "}
            {bulkSelected.size === 1 ? "compte seleccionat" : "comptes seleccionats"}
          </span>
          <span style={{ flex: 1 }} />
          <Button onClick={() => setBulkSelected(new Set())}>Buidar selecció</Button>
          <Button
            variant="danger"
            disabled={bulkRunning}
            onClick={() => setConfirmBulk(true)}
          >
            Regenerar contrasenyes seleccionades
          </Button>
        </div>
      )}

      <div className={styles.layout}>
        <aside className={styles.list}>
          <div className={styles.listHead}>
            <span>Comptes</span>
            {isAdmin && (
              <Button variant="primary" size="sm" onClick={() => setCreateOpen(true)}>
                + Nou
              </Button>
            )}
          </div>
          {users.isLoading && <div className={styles.muted}>Carregant…</div>}
          {users.data?.map(u => (
            <div
              key={u.id}
              className={`${styles.listItem} ${selected === u.id ? styles.active : ""}`}
            >
              {isAdmin && (
                <input
                  type="checkbox"
                  checked={bulkSelected.has(u.id)}
                  onChange={() => toggleBulk(u.id)}
                  onClick={e => e.stopPropagation()}
                  className={styles.bulkCheck}
                  title="Selecció per a regeneració massiva"
                />
              )}
              <button
                type="button"
                className={styles.itemBody}
                onClick={() => setSelected(u.id)}
              >
                <div className={styles.avatar}>{u.nom[0]}</div>
                <div className={styles.itemMeta}>
                  <div className={styles.itemName}>
                    {u.nom} {u.cognoms}
                  </div>
                  <div className={styles.itemSub}>{u.email}</div>
                </div>
                <span className={`${styles.tag} ${styles[u.role]}`}>{u.role}</span>
              </button>
            </div>
          ))}
        </aside>

        <section className={styles.detail}>
          {sel ? (
            <DocentDetail
              user={sel}
              onRegenerate={() => setConfirmRegen(sel)}
              onEmailPassword={() => emailMut.mutate(sel.id)}
              emailing={emailMut.isPending}
              onDelete={() => setConfirmDelete(sel)}
              isAdmin={isAdmin}
              isSelf={currentUser?.id === sel.id}
            />
          ) : (
            <div className={styles.empty}>
              <p>Selecciona un docent o crea'n un de nou.</p>
            </div>
          )}
        </section>
      </div>

      {createOpen && (
        <CreateDocentModal
          onClose={() => setCreateOpen(false)}
          onSubmit={body => createMut.mutate(body)}
          submitting={createMut.isPending}
        />
      )}

      {revealedPassword && (
        <RevealPasswordModal
          user={revealedPassword.user}
          password={revealedPassword.password}
          onClose={() => setRevealedPassword(null)}
          onEmail={() => {
            emailMut.mutate(revealedPassword.user.id);
            setRevealedPassword(null);
          }}
        />
      )}

      {confirmRegen && (
        <ConfirmDialog
          title="Regenerar contrasenya"
          message={`Generaràs una nova contrasenya per ${confirmRegen.nom} ${confirmRegen.cognoms}. La contrasenya actual deixarà de funcionar immediatament.`}
          detail="L'usuari serà obligat a canviar la contrasenya en el primer accés."
          confirmLabel="Regenerar"
          variant="danger"
          onConfirm={() => regenMut.mutate(confirmRegen.id)}
          onClose={() => setConfirmRegen(null)}
        />
      )}

      {confirmBulk && (
        <ConfirmDialog
          title="Regenerar contrasenyes massivament"
          message={`Generaràs noves contrasenyes per ${bulkSelected.size} usuari/s. Les contrasenyes actuals deixaran de funcionar immediatament i els usuaris hauran de canviar-les al primer accés.`}
          detail="Es descarregarà un CSV amb les credencials. Guarda'l de forma segura — només es mostraran un cop."
          confirmLabel={bulkRunning ? "Regenerant…" : "Regenerar i descarregar CSV"}
          variant="danger"
          onConfirm={runBulkRegen}
          onClose={() => !bulkRunning && setConfirmBulk(false)}
        />
      )}

      {confirmDelete && (
        <ConfirmDialog
          title="Donar de baixa el compte"
          message={`Donaràs de baixa ${confirmDelete.nom} ${confirmDelete.cognoms}. El compte queda inactiu però no s'esborra del registre (arxiu permanent).`}
          confirmLabel="Donar de baixa"
          variant="danger"
          onConfirm={() => deleteMut.mutate(confirmDelete.id)}
          onClose={() => setConfirmDelete(null)}
        />
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------

function DocentDetail({
  user,
  onRegenerate,
  onEmailPassword,
  emailing,
  onDelete,
  isAdmin,
  isSelf,
}: {
  user: AdminUser;
  onRegenerate: () => void;
  onEmailPassword: () => void;
  emailing: boolean;
  onDelete: () => void;
  isAdmin: boolean;
  isSelf: boolean;
}) {
  const exporter = useExport();
  // A professor can only export their own fitxa.
  const canExport = isAdmin || isSelf;
  return (
    <div>
      <div className={styles.detailHead}>
        <p className={styles.eyebrow}>Fitxa de docent</p>
        <h2>
          {user.nom} {user.cognoms}
        </h2>
        <p className={styles.detailSub}>{user.email}</p>
        <div className={styles.tags}>
          {user.departament && <span className={styles.tag}>{user.departament}</span>}
          <span className={`${styles.tag} ${styles[user.role]}`}>{user.role}</span>
          {user.must_change_password && (
            <span className={`${styles.tag} ${styles.warn}`}>contrasenya pendent</span>
          )}
          {!user.active && <span className={`${styles.tag} ${styles.danger}`}>inactiu</span>}
          {user.has_oauth_linked && <span className={styles.tag}>Google</span>}
          {user.has_mfa && <span className={styles.tag}>2FA</span>}
        </div>
      </div>

      <div className={styles.section}>
        <h3>Compte</h3>
        <dl className={styles.kv}>
          <dt>DNI</dt>
          <dd className={styles.mono}>{user.dni}</dd>
          <dt>Email</dt>
          <dd>{user.email}</dd>
          <dt>Departament</dt>
          <dd>{user.departament ?? "—"}</dd>
          <dt>Últim accés</dt>
          <dd className={styles.mono}>
            {user.last_login_at ? new Date(user.last_login_at).toLocaleString("ca-ES") : "mai"}
          </dd>
          <dt>Creat</dt>
          <dd className={styles.mono}>
            {new Date(user.created_at).toLocaleDateString("ca-ES")}
          </dd>
        </dl>
      </div>

      <DocentAssignacions userId={user.id} />

      <div className={styles.actions}>
        {isAdmin && (
          <>
            <Button onClick={onRegenerate}>Regenerar contrasenya</Button>
            <Button onClick={onEmailPassword} disabled={emailing}>
              {emailing ? "Enviant…" : "Enviar contrasenya per email"}
            </Button>
          </>
        )}
        {canExport && (
          <Button
            disabled={exporter.exporting}
            onClick={() =>
              exporter.run(t => exportsApi.docent(user.id, t), "Fitxa de docent")
            }
          >
            {exporter.exporting ? "Exportant…" : "⬇ Exportar"}
          </Button>
        )}
        {isAdmin && (
          <>
            <span style={{ flex: 1 }} />
            <Button variant="danger" onClick={onDelete}>
              Donar de baixa
            </Button>
          </>
        )}
      </div>

      <p className={styles.hint} style={{ display: isAdmin ? undefined : "none" }}>
        L'enviament per email només funciona dins dels primers 5 minuts després de
        generar/regenerar la contrasenya. Passat aquest temps cal regenerar-la.
      </p>
    </div>
  );
}

function DocentAssignacions({ userId }: { userId: number }) {
  const cursos = useQuery({ queryKey: ["cursos"], queryFn: () => catalogApi.listCursos() });
  const moduls = useQuery({ queryKey: ["moduls-all"], queryFn: () => catalogApi.listModuls() });
  const grups = useQuery({ queryKey: ["grups-all"], queryFn: () => grupsApi.list() });
  const assigs = useQuery({
    queryKey: ["assignacions", userId],
    queryFn: () => assignacionsApi.list({ user_id: userId }),
  });

  const grupById = new Map((grups.data ?? []).map(g => [g.id, g]));
  const modulById = new Map((moduls.data ?? []).map(m => [m.id, m]));
  const cursById = new Map((cursos.data ?? []).map(c => [c.id, c]));

  const tutorOf = (grups.data ?? []).filter(g => g.tutor_user_id === userId);

  // Group assignacions per curs acadèmic for clarity.
  const byCurs = new Map<number, { curs_nom: string; rows: typeof assigs.data extends (infer T)[] ? T[] : never[] }>();
  for (const a of assigs.data ?? []) {
    const curs = cursById.get(a.curs_acad_id);
    const key = a.curs_acad_id;
    if (!byCurs.has(key))
      byCurs.set(key, { curs_nom: curs?.nom ?? `#${a.curs_acad_id}`, rows: [] });
    byCurs.get(key)!.rows.push(a);
  }

  return (
    <div className={styles.section}>
      <h3>Assignacions docents</h3>
      {assigs.isLoading && <p className={styles.hint}>Carregant…</p>}
      {(assigs.data ?? []).length === 0 && tutorOf.length === 0 && (
        <p className={styles.hint}>
          Aquest docent no té cap mòdul assignat ni cap tutoria.
        </p>
      )}
      {tutorOf.length > 0 && (
        <div className={styles.kv} style={{ marginBottom: 10 }}>
          <dt>Tutories</dt>
          <dd>
            {tutorOf.map(g => (
              <Link
                key={g.id}
                to={`/grups/${g.id}/expedient`}
                className={styles.link}
                style={{ marginRight: 8 }}
              >
                {g.codi}
                {g.curs_acad_id && cursById.get(g.curs_acad_id)
                  ? ` (${cursById.get(g.curs_acad_id)!.nom})`
                  : ""}
              </Link>
            ))}
          </dd>
        </div>
      )}
      {Array.from(byCurs.entries()).map(([cursId, { curs_nom, rows }]) => (
        <div key={cursId} className={styles.kv} style={{ marginBottom: 10 }}>
          <dt>{curs_nom}</dt>
          <dd>
            <ul style={{ listStyle: "none", padding: 0, margin: 0 }}>
              {rows.map(a => {
                const m = modulById.get(a.modul_id);
                const g = grupById.get(a.grup_id);
                return (
                  <li key={a.id} style={{ display: "flex", gap: 8, alignItems: "baseline" }}>
                    <span className={styles.mono}>{m?.codi ?? "?"}</span>
                    <span>{m?.nom ?? `mòdul #${a.modul_id}`}</span>
                    <span style={{ color: "var(--ink-3)" }}>·</span>
                    <Link to={`/grups/${a.grup_id}/expedient`} className={styles.link}>
                      {g?.codi ?? `grup #${a.grup_id}`}
                    </Link>
                    <Link
                      to={`/qualificacions?curs=${a.curs_acad_id}&grup=${a.grup_id}&modul=${a.modul_id}`}
                      className={styles.link}
                      style={{ marginLeft: "auto", fontSize: 11 }}
                    >
                      Notes →
                    </Link>
                  </li>
                );
              })}
            </ul>
          </dd>
        </div>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------

function CreateDocentModal({
  onClose,
  onSubmit,
  submitting,
}: {
  onClose: () => void;
  onSubmit: (body: AdminUserCreate) => void;
  submitting: boolean;
}) {
  const [form, setForm] = useState<AdminUserCreate>({
    dni: "",
    email: "",
    nom: "",
    cognoms: "",
    role: "professor",
    departament: "",
  });

  const set = <K extends keyof AdminUserCreate>(k: K, v: AdminUserCreate[K]) =>
    setForm(f => ({ ...f, [k]: v }));

  return (
    <Modal
      title="Nou docent"
      subtitle="El sistema generarà una contrasenya forta que veuràs un cop"
      onClose={onClose}
      maxWidth={520}
      footer={
        <>
          <Button onClick={onClose}>Cancel·lar</Button>
          <Button
            variant="primary"
            disabled={submitting || !form.dni || !form.email || !form.nom || !form.cognoms}
            onClick={() => onSubmit({ ...form, departament: form.departament || null })}
          >
            {submitting ? "Creant…" : "Crear i generar contrasenya"}
          </Button>
        </>
      }
    >
      <div className={styles.formGrid}>
        <Field label="DNI / NIE *" mono>
          <input
            value={form.dni}
            onChange={e => set("dni", e.target.value.toUpperCase())}
            placeholder="12345678Z"
          />
        </Field>
        <Field label="Email institucional *">
          <input
            type="email"
            value={form.email}
            onChange={e => set("email", e.target.value)}
            placeholder="nom.cognom@inslaferreria.cat"
          />
        </Field>
        <Field label="Nom *">
          <input value={form.nom} onChange={e => set("nom", e.target.value)} />
        </Field>
        <Field label="Cognoms *">
          <input value={form.cognoms} onChange={e => set("cognoms", e.target.value)} />
        </Field>
        <Field label="Departament">
          <input
            value={form.departament ?? ""}
            onChange={e => set("departament", e.target.value)}
            placeholder="Informàtica, Sanitat, …"
          />
        </Field>
        <Field label="Rol *">
          <select value={form.role} onChange={e => set("role", e.target.value as "admin" | "professor")}>
            <option value="professor">Professor/a</option>
            <option value="admin">Administrador/a</option>
          </select>
        </Field>
      </div>
    </Modal>
  );
}

function Field({
  label,
  children,
  mono,
}: {
  label: string;
  children: React.ReactNode;
  mono?: boolean;
}) {
  return (
    <label className={`${styles.field} ${mono ? styles.fieldMono : ""}`}>
      <span>{label}</span>
      {children}
    </label>
  );
}

// ---------------------------------------------------------------------------

function RevealPasswordModal({
  user,
  password,
  onClose,
  onEmail,
}: {
  user: AdminUser;
  password: string;
  onClose: () => void;
  onEmail: () => void;
}) {
  const [copied, setCopied] = useState(false);

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(password);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      toast.warn("No s'ha pogut copiar al porta-retalls");
    }
  };

  return (
    <Modal
      title="Contrasenya generada"
      subtitle={`Per ${user.nom} ${user.cognoms} (${user.dni})`}
      onClose={onClose}
      maxWidth={500}
      footer={
        <>
          <Button onClick={onClose}>Tancar</Button>
          <Button onClick={onEmail}>Enviar per email a l'usuari</Button>
          <Button variant="primary" onClick={copy}>
            {copied ? "Copiat ✓" : "Copiar al porta-retalls"}
          </Button>
        </>
      }
    >
      <p className={styles.warn}>
        Aquesta és l'única vegada que veuràs la contrasenya. Després de tancar aquesta
        finestra, només la podràs enviar per email durant els 5 minuts següents.
      </p>
      <div className={styles.passwordBox}>
        <code>{password}</code>
      </div>
      <p className={styles.hint}>
        L'usuari haurà de canviar-la en el primer accés. La pots compartir manualment o
        enviar-la directament al seu email institucional.
      </p>
    </Modal>
  );
}
