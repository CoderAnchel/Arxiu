/** Currículums page — full CRUD over cicles, mòduls and RAs.
 *
 * Layout: left list of cicles, right detail with mòduls grouped per curs. Each
 * level has a + button that opens a focused form modal. Admin-only operations
 * are guarded server-side; the UI shows them to everyone but the API rejects
 * non-admins with 403.
 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";

import { catalogApi, type Cicle, type Familia, type Modul, type Ra } from "@/api/catalog";
import type { ApiError } from "@/api/client";
import { exportsApi } from "@/api/exports";
import { Button } from "@/components/ui/Button";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import { Modal } from "@/components/ui/Modal";
import { FamiliaModal } from "@/features/admin/FamiliesTab";
import { useExport } from "@/hooks/useExport";
import { useAuthStore } from "@/stores/authStore";
import { toast } from "@/stores/toastStore";

import styles from "./CurriculumsPage.module.css";

type CicleForm = {
  codi: string;
  nom: string;
  familia_id: number | null;
  nivell: "mig" | "superior";
  durada: number;
  max_suspesos_recupera: number;
  pct_hores_no_promociona: string | null;
};

type ModulForm = {
  codi: string;
  nom: string;
  curs: number;
  hores: number;
  bloquejant: boolean;
};

type RaForm = {
  codi: string;
  descripcio: string;
  pes: string;
  ordre: number;
};

export function CurriculumsPage() {
  const qc = useQueryClient();
  const user = useAuthStore(s => s.user);
  const isAdmin = user?.role === "admin";
  const exporter = useExport();

  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [familiaFilter, setFamiliaFilter] = useState<number | "all">("all");
  const [search, setSearch] = useState("");

  const cicles = useQuery({ queryKey: ["cicles"], queryFn: () => catalogApi.listCicles() });
  const families = useQuery({ queryKey: ["families"], queryFn: () => catalogApi.listFamilies() });
  const cicle = useQuery({
    queryKey: ["cicle", selectedId],
    queryFn: () => catalogApi.getCicle(selectedId!),
    enabled: selectedId !== null,
  });

  // Auto-select first cicle once list loads
  if (selectedId === null && cicles.data && cicles.data.length > 0) {
    setSelectedId(cicles.data[0]!.id);
  }

  // --- Filtering --------------------------------------------------------
  const filteredCicles = useMemo(() => {
    if (!cicles.data) return [];
    return cicles.data.filter(c => {
      if (familiaFilter !== "all" && c.familia_id !== familiaFilter) return false;
      if (search.trim()) {
        const q = search.toLowerCase().trim();
        if (!c.nom.toLowerCase().includes(q) && !c.codi.toLowerCase().includes(q))
          return false;
      }
      return true;
    });
  }, [cicles.data, familiaFilter, search]);

  // --- Modal state ------------------------------------------------------
  const [cicleModal, setCicleModal] = useState<"new" | Cicle | null>(null);
  const [modulModal, setModulModal] = useState<"new" | Modul | null>(null);
  const [raModalForModul, setRaModalForModul] = useState<Modul | null>(null);
  const [raEditing, setRaEditing] = useState<Ra | null>(null);
  const [deleteCicle, setDeleteCicle] = useState<Cicle | null>(null);
  const [deleteModul, setDeleteModul] = useState<Modul | null>(null);
  const [deleteRa, setDeleteRa] = useState<Ra | null>(null);

  // --- Mutations --------------------------------------------------------
  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ["cicles"] });
    if (selectedId !== null) qc.invalidateQueries({ queryKey: ["cicle", selectedId] });
  };

  const onApiError = (defaultMsg: string) => (err: ApiError) =>
    toast.error(err.message || defaultMsg);

  const createCicleMut = useMutation({
    mutationFn: (body: CicleForm) => catalogApi.createCicle(body),
    onSuccess: c => {
      invalidate();
      setCicleModal(null);
      setSelectedId(c.id);
      toast.success(`Cicle ${c.codi} creat`);
    },
    onError: onApiError("Error en crear cicle"),
  });

  const updateCicleMut = useMutation({
    mutationFn: ({ id, body }: { id: number; body: Partial<CicleForm> }) =>
      catalogApi.updateCicle(id, body),
    onSuccess: () => {
      invalidate();
      setCicleModal(null);
      toast.success("Cicle actualitzat");
    },
    onError: onApiError("Error en actualitzar"),
  });

  const deleteCicleMut = useMutation({
    mutationFn: (id: number) => catalogApi.deleteCicle(id),
    onSuccess: () => {
      invalidate();
      setDeleteCicle(null);
      if (selectedId !== null && cicles.data && cicles.data.length > 1) {
        setSelectedId(cicles.data.find(c => c.id !== selectedId)?.id ?? null);
      } else {
        setSelectedId(null);
      }
      toast.success("Cicle eliminat");
    },
    onError: onApiError("Error en eliminar"),
  });

  const createModulMut = useMutation({
    mutationFn: (body: ModulForm & { cicle_id: number }) => catalogApi.createModul(body),
    onSuccess: () => {
      invalidate();
      setModulModal(null);
      toast.success("Mòdul creat");
    },
    onError: onApiError("Error en crear mòdul"),
  });

  const updateModulMut = useMutation({
    mutationFn: ({ id, body }: { id: number; body: Partial<ModulForm> }) =>
      catalogApi.updateModul(id, body),
    onSuccess: () => {
      invalidate();
      setModulModal(null);
      toast.success("Mòdul actualitzat");
    },
    onError: onApiError("Error en actualitzar"),
  });

  const deleteModulMut = useMutation({
    mutationFn: (id: number) => catalogApi.deleteModul(id),
    onSuccess: () => {
      invalidate();
      setDeleteModul(null);
      toast.success("Mòdul eliminat");
    },
    onError: onApiError("Error en eliminar"),
  });

  const createRaMut = useMutation({
    mutationFn: (body: { modul_id: number; ordre: number; codi: string; descripcio: string; pes: string }) =>
      catalogApi.createRa(body),
    onSuccess: () => {
      invalidate();
      setRaModalForModul(null);
      setRaEditing(null);
      toast.success("RA creat");
    },
    onError: onApiError("Error en crear RA"),
  });

  const updateRaMut = useMutation({
    mutationFn: ({ id, body }: { id: number; body: Partial<RaForm> }) =>
      catalogApi.updateRa(id, body),
    onSuccess: () => {
      invalidate();
      setRaEditing(null);
      toast.success("RA actualitzat");
    },
    onError: onApiError("Error en actualitzar"),
  });

  const deleteRaMut = useMutation({
    mutationFn: (id: number) => catalogApi.deleteRa(id),
    onSuccess: () => {
      invalidate();
      setDeleteRa(null);
      toast.success("RA eliminat");
    },
    onError: onApiError("Error en eliminar"),
  });

  return (
    <div className={styles.page}>
      <header className={styles.head}>
        <p className={styles.eyebrow}>Estructura acadèmica</p>
        <h1 className={styles.title}>Currículums</h1>
        <p className={styles.sub}>
          Cicles formatius, els seus mòduls (per curs) i els resultats d'aprenentatge
          associats. Edita pesos i ordres aquí.
        </p>
      </header>

      <div className={styles.toolbar}>
        <label className={styles.toolbarField}>
          <span>Família</span>
          <select
            value={familiaFilter}
            onChange={e =>
              setFamiliaFilter(e.target.value === "all" ? "all" : Number(e.target.value))
            }
          >
            <option value="all">Totes</option>
            {(families.data ?? []).map(f => (
              <option key={f.id} value={f.id}>
                {f.codi} · {f.nom}
              </option>
            ))}
          </select>
        </label>
        <label className={styles.toolbarField}>
          <span>Cerca</span>
          <input
            placeholder="codi o nom…"
            value={search}
            onChange={e => setSearch(e.target.value)}
          />
        </label>
        {isAdmin && (
          <Button variant="primary" onClick={() => setCicleModal("new")}>
            + Nou cicle
          </Button>
        )}
      </div>

      <div className={styles.layout}>
        <aside className={styles.list}>
          <div className={styles.listHead}>Cicles · {filteredCicles.length}</div>
          {cicles.isLoading && <div className={styles.muted}>Carregant…</div>}
          {cicles.isError && (
            <div className={styles.error}>No s'han pogut carregar els cicles</div>
          )}
          {filteredCicles.map(c => (
            <button
              key={c.id}
              type="button"
              className={`${styles.listItem} ${selectedId === c.id ? styles.listItemActive : ""}`}
              onClick={() => setSelectedId(c.id)}
            >
              <strong>{c.codi}</strong>
              <span>{c.nom}</span>
              <span className={styles.badge}>{c.nivell[0]}</span>
            </button>
          ))}
          {cicles.data?.length === 0 && (
            <div className={styles.muted}>
              Encara no hi ha cap cicle. Crea el primer amb "+ Nou cicle".
            </div>
          )}
        </aside>

        <section className={styles.detail}>
          {cicle.isLoading && <div className={styles.muted}>Carregant cicle…</div>}
          {cicle.data && (
            <>
              <div className={styles.detailHead}>
                <div>
                  <h2>{cicle.data.nom}</h2>
                  <p className={styles.eyebrow}>
                    Codi {cicle.data.codi} · {cicle.data.nivell} · {cicle.data.durada}{" "}
                    {cicle.data.durada === 1 ? "curs" : "cursos"}
                  </p>
                </div>
                <div className={styles.detailActions}>
                  <Button
                    size="sm"
                    disabled={exporter.exporting}
                    onClick={() =>
                      exporter.run(t => exportsApi.cicle(cicle.data!.id, t), "Cicle")
                    }
                  >
                    {exporter.exporting ? "Exportant…" : "⬇ Exportar"}
                  </Button>
                  {isAdmin && (
                    <>
                      <Button size="sm" onClick={() => setCicleModal(cicle.data!)}>
                        Editar cicle
                      </Button>
                      <Button size="sm" onClick={() => setModulModal("new")}>
                        + Nou mòdul
                      </Button>
                      <Button
                        size="sm"
                        variant="danger"
                        onClick={() => setDeleteCicle(cicle.data!)}
                      >
                        Eliminar
                      </Button>
                    </>
                  )}
                </div>
              </div>

              {[1, 2].map(curs => {
                if (curs > cicle.data!.durada) return null;
                const moduls = cicle.data!.moduls.filter(m => m.curs === curs);
                return (
                  <div key={curs} className={styles.cursSection}>
                    <h3>{curs}r curs</h3>
                    {moduls.length === 0 && (
                      <p className={styles.muted}>Cap mòdul a aquest curs encara.</p>
                    )}
                    {moduls.map(m => {
                      const totalPes = m.ras.reduce(
                        (acc, r) => acc + (Number.parseFloat(r.pes) || 0),
                        0,
                      );
                      const pesOk = Math.abs(totalPes - 100) < 0.01;
                      return (
                      <div key={m.id} className={styles.modulCard}>
                        <div className={styles.modulHead}>
                          <span className={styles.mono}>{m.codi}</span>
                          <span className={styles.modulName}>{m.nom}</span>
                          {m.bloquejant && (
                            <span
                              className={`${styles.badge} ${styles.badgeWarn}`}
                              title="Mòdul bloquejant: un suspès aquí força 'No promociona' a la junta"
                            >
                              ⚠ bloquejant
                            </span>
                          )}
                          <span className={styles.badge}>{m.hores} h</span>
                          <span className={styles.badge}>{m.ras.length} RA</span>
                          <span
                            className={`${styles.badge} ${pesOk ? styles.badgeOk : styles.badgeWarn}`}
                            title={
                              pesOk
                                ? "Pesos correctes (sumen 100%)"
                                : `Els pesos sumen ${totalPes.toFixed(2)}%, no 100%. ` +
                                  "El càlcul es normalitza, però revisa si és intencional."
                            }
                          >
                            Σ {totalPes.toFixed(2)}%
                          </span>
                          {isAdmin && (
                            <span className={styles.modulActions}>
                              <Button size="sm" onClick={() => setModulModal(m)}>
                                Editar
                              </Button>
                              <Button size="sm" onClick={() => setRaModalForModul(m)}>
                                + RA
                              </Button>
                              <Button
                                size="sm"
                                variant="danger"
                                onClick={() => setDeleteModul(m)}
                              >
                                ✕
                              </Button>
                            </span>
                          )}
                        </div>
                        <div className={styles.raGrid}>
                          {m.ras.map(r => (
                            <div key={r.id} className={styles.raCard}>
                              <div className={styles.raHead}>
                                <span className={styles.raCodi}>{r.codi}</span>
                                <span className={styles.raPes}>pes {r.pes}%</span>
                                {isAdmin && (
                                  <span className={styles.raActions}>
                                    <button
                                      type="button"
                                      className={styles.raIconBtn}
                                      onClick={() => setRaEditing(r)}
                                      title="Editar"
                                    >
                                      ✎
                                    </button>
                                    <button
                                      type="button"
                                      className={styles.raIconBtn}
                                      onClick={() => setDeleteRa(r)}
                                      title="Eliminar"
                                    >
                                      ✕
                                    </button>
                                  </span>
                                )}
                              </div>
                              <div className={styles.raDesc}>{r.descripcio}</div>
                            </div>
                          ))}
                        </div>
                      </div>
                      );
                    })}
                  </div>
                );
              })}
            </>
          )}
        </section>
      </div>

      {/* Modals */}
      {cicleModal && (
        <CicleFormModal
          cicle={cicleModal === "new" ? null : cicleModal}
          families={families.data ?? []}
          onClose={() => setCicleModal(null)}
          onSubmit={body => {
            if (cicleModal === "new") createCicleMut.mutate(body);
            else updateCicleMut.mutate({ id: cicleModal.id, body });
          }}
          submitting={createCicleMut.isPending || updateCicleMut.isPending}
        />
      )}
      {modulModal && cicle.data && (
        <ModulFormModal
          modul={modulModal === "new" ? null : modulModal}
          cicle={cicle.data}
          onClose={() => setModulModal(null)}
          onSubmit={body => {
            if (modulModal === "new")
              createModulMut.mutate({ ...body, cicle_id: cicle.data!.id });
            else updateModulMut.mutate({ id: modulModal.id, body });
          }}
          submitting={createModulMut.isPending || updateModulMut.isPending}
        />
      )}
      {(raModalForModul || raEditing) && (
        <RaFormModal
          ra={raEditing}
          modul={
            raEditing
              ? cicle.data?.moduls.find(m => m.id === raEditing.modul_id) ?? null
              : raModalForModul
          }
          onClose={() => {
            setRaModalForModul(null);
            setRaEditing(null);
          }}
          onSubmit={body => {
            if (raEditing) {
              updateRaMut.mutate({ id: raEditing.id, body });
            } else if (raModalForModul) {
              createRaMut.mutate({ ...body, modul_id: raModalForModul.id });
            }
          }}
          submitting={createRaMut.isPending || updateRaMut.isPending}
        />
      )}

      {deleteCicle && (
        <ConfirmDialog
          title={`Eliminar cicle ${deleteCicle.codi}?`}
          message="Esborrarà també mòduls i RAs associats (soft delete). Les notes ja introduïdes contra aquest cicle es conserven a l'arxiu."
          variant="danger"
          confirmLabel="Eliminar cicle"
          onConfirm={() => deleteCicleMut.mutate(deleteCicle.id)}
          onClose={() => setDeleteCicle(null)}
        />
      )}
      {deleteModul && (
        <ConfirmDialog
          title={`Eliminar mòdul ${deleteModul.codi}?`}
          message="Soft delete: les notes històriques contra aquest mòdul es conserven."
          variant="danger"
          confirmLabel="Eliminar"
          onConfirm={() => deleteModulMut.mutate(deleteModul.id)}
          onClose={() => setDeleteModul(null)}
        />
      )}
      {deleteRa && (
        <ConfirmDialog
          title={`Eliminar RA ${deleteRa.codi}?`}
          message="Soft delete: les notes ja introduïdes contra aquest RA es conserven a l'arxiu."
          variant="danger"
          confirmLabel="Eliminar"
          onConfirm={() => deleteRaMut.mutate(deleteRa.id)}
          onClose={() => setDeleteRa(null)}
        />
      )}
    </div>
  );
}

// --- Form modals ---------------------------------------------------------

function CicleFormModal({
  cicle,
  families,
  onClose,
  onSubmit,
  submitting,
}: {
  cicle: Cicle | null;
  families: Familia[];
  onClose: () => void;
  onSubmit: (body: CicleForm) => void;
  submitting: boolean;
}) {
  const qc = useQueryClient();
  const [form, setForm] = useState<CicleForm>({
    codi: cicle?.codi ?? "",
    nom: cicle?.nom ?? "",
    familia_id: cicle?.familia_id ?? null,
    nivell: cicle?.nivell ?? "superior",
    durada: cicle?.durada ?? 2,
    max_suspesos_recupera: cicle?.max_suspesos_recupera ?? 2,
    pct_hores_no_promociona: cicle?.pct_hores_no_promociona ?? null,
  });
  const [newFamiliaOpen, setNewFamiliaOpen] = useState(false);
  const newFamMut = useMutation({
    mutationFn: (body: { codi: string; nom: string }) => catalogApi.createFamilia(body),
    onSuccess: f => {
      qc.invalidateQueries({ queryKey: ["families"] });
      setForm(prev => ({ ...prev, familia_id: f.id }));
      setNewFamiliaOpen(false);
      toast.success(`Família ${f.codi} creada`);
    },
    onError: (err: ApiError) => toast.error(err.message || "Error en crear família"),
  });
  const valid = form.codi.trim().length > 0 && form.nom.trim().length > 0;
  return (
    <Modal
      title={cicle ? "Editar cicle" : "Nou cicle formatiu"}
      onClose={onClose}
      maxWidth={520}
      footer={
        <>
          <Button onClick={onClose}>Cancel·lar</Button>
          <Button variant="primary" disabled={!valid || submitting} onClick={() => onSubmit(form)}>
            {submitting ? "Desant…" : cicle ? "Guardar" : "Crear"}
          </Button>
        </>
      }
    >
      <div className={styles.formGrid}>
        <label className={styles.field}>
          <span>Codi *</span>
          <input
            value={form.codi}
            onChange={e => setForm(f => ({ ...f, codi: e.target.value.toUpperCase() }))}
            placeholder="DAM"
            autoFocus
          />
        </label>
        <label className={styles.field}>
          <span>Nivell</span>
          <select
            value={form.nivell}
            onChange={e => setForm(f => ({ ...f, nivell: e.target.value as "mig" | "superior" }))}
          >
            <option value="mig">Mig</option>
            <option value="superior">Superior</option>
          </select>
        </label>
        <label className={`${styles.field} ${styles.full}`}>
          <span>Nom *</span>
          <input
            value={form.nom}
            onChange={e => setForm(f => ({ ...f, nom: e.target.value }))}
            placeholder="Desenvolupament d'Aplicacions Multiplataforma"
          />
        </label>
        <label className={styles.field}>
          <span>Família</span>
          <div style={{ display: "flex", gap: 6 }}>
            <select
              value={form.familia_id ?? ""}
              onChange={e =>
                setForm(f => ({
                  ...f,
                  familia_id: e.target.value ? Number(e.target.value) : null,
                }))
              }
              style={{ flex: 1 }}
            >
              <option value="">—</option>
              {families.map(f => (
                <option key={f.id} value={f.id}>
                  {f.codi} · {f.nom}
                </option>
              ))}
            </select>
            <button
              type="button"
              onClick={() => setNewFamiliaOpen(true)}
              title="Crear una nova família sense sortir d'aquí"
              style={{
                background: "var(--bg-2)",
                border: "1px solid var(--line)",
                borderRadius: "var(--r)",
                padding: "0 10px",
                cursor: "pointer",
                fontSize: 14,
                color: "var(--accent)",
              }}
            >
              + Nova
            </button>
          </div>
        </label>
        <label className={styles.field}>
          <span>Durada (cursos)</span>
          <select
            value={form.durada}
            onChange={e => setForm(f => ({ ...f, durada: Number(e.target.value) }))}
          >
            <option value={1}>1 curs</option>
            <option value={2}>2 cursos</option>
          </select>
        </label>
        <div className={`${styles.field} ${styles.full}`} style={{ gap: 4 }}>
          <span>Política de junta</span>
          <small style={{ color: "var(--ink-3)", fontSize: 11.5, fontFamily: "var(--sans)", letterSpacing: 0, textTransform: "none" }}>
            Regles que el sistema aplicarà per proposar Apte / Recupera / No promociona a l'acta.
          </small>
        </div>
        <label className={styles.field}>
          <span>Suspesos màx. per "Recupera"</span>
          <input
            type="number"
            min={0}
            max={20}
            value={form.max_suspesos_recupera}
            onChange={e =>
              setForm(f => ({ ...f, max_suspesos_recupera: Number(e.target.value) }))
            }
          />
          <small style={{ color: "var(--ink-3)", fontSize: 11, marginTop: 2 }}>
            A partir d'aquí, "No promociona". Per defecte 2.
          </small>
        </label>
        <label className={styles.field}>
          <span>% hores → No promociona (opcional)</span>
          <input
            type="number"
            min={0}
            max={100}
            step={0.5}
            placeholder="ex: 30"
            value={form.pct_hores_no_promociona ?? ""}
            onChange={e =>
              setForm(f => ({
                ...f,
                pct_hores_no_promociona: e.target.value === "" ? null : e.target.value,
              }))
            }
          />
          <small style={{ color: "var(--ink-3)", fontSize: 11, marginTop: 2 }}>
            Si el % d'hores suspeses supera aquest llindar, "No promociona". Buit = desactivat.
          </small>
        </label>
      </div>
      {newFamiliaOpen && (
        <FamiliaModal
          familia={null}
          onClose={() => setNewFamiliaOpen(false)}
          onSubmit={body => newFamMut.mutate(body)}
          submitting={newFamMut.isPending}
        />
      )}
    </Modal>
  );
}

function ModulFormModal({
  modul,
  cicle,
  onClose,
  onSubmit,
  submitting,
}: {
  modul: Modul | null;
  cicle: Cicle;
  onClose: () => void;
  onSubmit: (body: ModulForm) => void;
  submitting: boolean;
}) {
  const [form, setForm] = useState<ModulForm>({
    codi: modul?.codi ?? "",
    nom: modul?.nom ?? "",
    curs: modul?.curs ?? 1,
    hores: modul?.hores ?? 99,
    bloquejant: modul?.bloquejant ?? false,
  });
  const valid = form.codi.trim().length > 0 && form.nom.trim().length > 0;
  return (
    <Modal
      title={modul ? `Editar mòdul · ${cicle.codi}` : `Nou mòdul · ${cicle.codi}`}
      onClose={onClose}
      maxWidth={520}
      footer={
        <>
          <Button onClick={onClose}>Cancel·lar</Button>
          <Button variant="primary" disabled={!valid || submitting} onClick={() => onSubmit(form)}>
            {submitting ? "Desant…" : modul ? "Guardar" : "Crear"}
          </Button>
        </>
      }
    >
      <div className={styles.formGrid}>
        <label className={styles.field}>
          <span>Codi *</span>
          <input
            value={form.codi}
            onChange={e => setForm(f => ({ ...f, codi: e.target.value.toUpperCase() }))}
            placeholder="M03"
            autoFocus
          />
        </label>
        <label className={styles.field}>
          <span>Curs</span>
          <select
            value={form.curs}
            onChange={e => setForm(f => ({ ...f, curs: Number(e.target.value) }))}
          >
            {Array.from({ length: cicle.durada }, (_, i) => i + 1).map(c => (
              <option key={c} value={c}>
                {c}r curs
              </option>
            ))}
          </select>
        </label>
        <label className={`${styles.field} ${styles.full}`}>
          <span>Nom *</span>
          <input
            value={form.nom}
            onChange={e => setForm(f => ({ ...f, nom: e.target.value }))}
            placeholder="Programació"
          />
        </label>
        <label className={styles.field}>
          <span>Hores</span>
          <input
            type="number"
            min={0}
            value={form.hores}
            onChange={e => setForm(f => ({ ...f, hores: Number(e.target.value) }))}
          />
        </label>
        <label
          className={`${styles.field} ${styles.full}`}
          style={{ flexDirection: "row", alignItems: "center", gap: 8 }}
        >
          <input
            type="checkbox"
            checked={form.bloquejant}
            onChange={e => setForm(f => ({ ...f, bloquejant: e.target.checked }))}
          />
          <span style={{ textTransform: "none", letterSpacing: 0, fontSize: 13 }}>
            <strong>Mòdul bloquejant</strong> — un suspès aquí força "No promociona"
            (típic per a FCT, projecte final, etc.)
          </span>
        </label>
      </div>
    </Modal>
  );
}

function RaFormModal({
  ra,
  modul,
  onClose,
  onSubmit,
  submitting,
}: {
  ra: Ra | null;
  modul: Modul | null;
  onClose: () => void;
  onSubmit: (body: { ordre: number; codi: string; descripcio: string; pes: string }) => void;
  submitting: boolean;
}) {
  const nextOrdre = (modul?.ras.length ?? 0) + 1;
  const [form, setForm] = useState<RaForm>({
    codi: ra?.codi ?? `RA${nextOrdre}`,
    descripcio: ra?.descripcio ?? "",
    pes: ra?.pes ?? "25.00",
    ordre: ra?.ordre ?? nextOrdre,
  });
  const valid = form.codi.trim().length > 0 && form.descripcio.trim().length > 0;
  return (
    <Modal
      title={
        ra
          ? `Editar RA · ${modul?.codi ?? ""}`
          : `Nou resultat d'aprenentatge · ${modul?.codi ?? ""}`
      }
      onClose={onClose}
      maxWidth={520}
      footer={
        <>
          <Button onClick={onClose}>Cancel·lar</Button>
          <Button variant="primary" disabled={!valid || submitting} onClick={() => onSubmit(form)}>
            {submitting ? "Desant…" : ra ? "Guardar" : "Crear"}
          </Button>
        </>
      }
    >
      <div className={styles.formGrid}>
        <label className={styles.field}>
          <span>Codi *</span>
          <input
            value={form.codi}
            onChange={e => setForm(f => ({ ...f, codi: e.target.value.toUpperCase() }))}
            placeholder="RA1"
            autoFocus
          />
        </label>
        <label className={styles.field}>
          <span>Ordre</span>
          <input
            type="number"
            min={1}
            value={form.ordre}
            onChange={e => setForm(f => ({ ...f, ordre: Number(e.target.value) }))}
          />
        </label>
        <label className={`${styles.field} ${styles.full}`}>
          <span>Descripció *</span>
          <textarea
            rows={3}
            value={form.descripcio}
            onChange={e => setForm(f => ({ ...f, descripcio: e.target.value }))}
            placeholder="Identifica els elements del llenguatge."
          />
        </label>
        <label className={styles.field}>
          <span>Pes (%) *</span>
          <input
            type="number"
            min={0}
            max={100}
            step={0.01}
            value={form.pes}
            onChange={e => setForm(f => ({ ...f, pes: e.target.value }))}
          />
        </label>
      </div>
    </Modal>
  );
}
