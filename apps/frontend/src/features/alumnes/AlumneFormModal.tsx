/** Form modal for creating or editing an alumne. */
import { useState } from "react";

import type { ApiError } from "@/api/client";
import { peopleApi, type Alumne, type AlumneCreate } from "@/api/people";
import { Button } from "@/components/ui/Button";
import { Modal } from "@/components/ui/Modal";
import { toast } from "@/stores/toastStore";

import styles from "./AlumneFormModal.module.css";

type Props = {
  alumne?: Alumne | null;     // null → create; else → edit
  onClose: () => void;
  onSaved: () => void;        // called after successful save (refetch list)
};

export function AlumneFormModal({ alumne, onClose, onSaved }: Props) {
  const isEdit = !!alumne;
  const [form, setForm] = useState<AlumneCreate>({
    dni: alumne?.dni ?? "",
    ralc: alumne?.ralc ?? "",
    nom: alumne?.nom ?? "",
    cognoms: alumne?.cognoms ?? "",
    email: alumne?.email ?? "",
    telefon: alumne?.telefon ?? "",
    data_naixement: alumne?.data_naixement ?? "",
    tutors_legals:
      alumne?.tutors_legals.map(t => ({
        nom: t.nom,
        email: t.email ?? "",
        telefon: t.telefon ?? "",
      })) ?? [],
  });
  const [busy, setBusy] = useState(false);

  const set = <K extends keyof AlumneCreate>(k: K, v: AlumneCreate[K]) =>
    setForm(f => ({ ...f, [k]: v }));

  const handleSave = async () => {
    setBusy(true);
    try {
      // Strip empty strings to null
      const payload: AlumneCreate = {
        ...form,
        dni: form.dni?.trim() || null,
        email: form.email?.trim() || null,
        telefon: form.telefon?.trim() || null,
        data_naixement: form.data_naixement?.trim() || null,
        tutors_legals: (form.tutors_legals ?? [])
          .filter(t => t.nom.trim())
          .map(t => ({
            nom: t.nom.trim(),
            email: t.email?.trim() || null,
            telefon: t.telefon?.trim() || null,
          })),
      };

      if (isEdit && alumne) {
        // Update — backend currently doesn't accept tutors_legals on PATCH; strip them
        const { tutors_legals: _, ...patch } = payload;
        await peopleApi.updateAlumne(alumne.id, patch);
        toast.success(`${alumne.nom} ${alumne.cognoms} actualitzat`);
      } else {
        const created = await peopleApi.createAlumne(payload);
        toast.success(`${created.nom} ${created.cognoms} creat`);
      }
      onSaved();
      onClose();
    } catch (err) {
      const e = err as ApiError;
      toast.error(
        e.code === "conflict"
          ? "Ja existeix un alumne amb aquest RALC"
          : e.message || "Error en desar l'alumne",
      );
    } finally {
      setBusy(false);
    }
  };

  const addTutor = () =>
    setForm(f => ({
      ...f,
      tutors_legals: [...(f.tutors_legals ?? []), { nom: "", email: "", telefon: "" }],
    }));

  const removeTutor = (i: number) =>
    setForm(f => ({
      ...f,
      tutors_legals: (f.tutors_legals ?? []).filter((_, idx) => idx !== i),
    }));

  const setTutor = (i: number, k: "nom" | "email" | "telefon", v: string) =>
    setForm(f => ({
      ...f,
      tutors_legals: (f.tutors_legals ?? []).map((t, idx) =>
        idx === i ? { ...t, [k]: v } : t,
      ),
    }));

  return (
    <Modal
      title={isEdit ? "Editar alumne" : "Nou alumne"}
      subtitle={
        isEdit && alumne ? `${alumne.cognoms}, ${alumne.nom} · DNI ${alumne.dni ?? "—"}` : undefined
      }
      onClose={onClose}
      maxWidth={680}
      footer={
        <>
          <Button onClick={onClose}>Cancel·lar</Button>
          <Button
            variant="primary"
            disabled={busy || !form.ralc.trim() || !form.nom.trim() || !form.cognoms.trim()}
            onClick={handleSave}
          >
            {busy ? "Desant…" : isEdit ? "Guardar canvis" : "Crear alumne"}
          </Button>
        </>
      }
    >
      <div className={styles.grid}>
        <Field label="RALC / NIA *" mono>
          <input value={form.ralc} onChange={e => set("ralc", e.target.value)} autoFocus />
        </Field>
        <Field label="DNI / NIE" mono>
          <input
            value={form.dni ?? ""}
            onChange={e => set("dni", e.target.value.toUpperCase())}
            placeholder="12345678Z"
          />
        </Field>
        <Field label="Nom *">
          <input value={form.nom} onChange={e => set("nom", e.target.value)} />
        </Field>
        <Field label="Cognoms *">
          <input value={form.cognoms} onChange={e => set("cognoms", e.target.value)} />
        </Field>
        <Field label="Email">
          <input type="email" value={form.email ?? ""} onChange={e => set("email", e.target.value)} />
        </Field>
        <Field label="Telèfon" mono>
          <input
            value={form.telefon ?? ""}
            onChange={e => set("telefon", e.target.value)}
            placeholder="6XXXXXXXX"
          />
        </Field>
        <Field label="Data de naixement">
          <input
            type="date"
            value={form.data_naixement ?? ""}
            onChange={e => set("data_naixement", e.target.value)}
          />
        </Field>
      </div>

      {!isEdit && (
        <div className={styles.tutorsSection}>
          <div className={styles.tutorsHead}>
            <span>Tutors legals</span>
            <Button size="sm" onClick={addTutor}>
              + Afegir tutor
            </Button>
          </div>
          {(form.tutors_legals ?? []).map((t, i) => (
            <div key={i} className={styles.tutorRow}>
              <input
                value={t.nom}
                onChange={e => setTutor(i, "nom", e.target.value)}
                placeholder="Nom complet"
              />
              <input
                type="email"
                value={t.email ?? ""}
                onChange={e => setTutor(i, "email", e.target.value)}
                placeholder="email@exemple.cat"
              />
              <input
                value={t.telefon ?? ""}
                onChange={e => setTutor(i, "telefon", e.target.value)}
                placeholder="Telèfon"
                className={styles.mono}
              />
              <button
                type="button"
                onClick={() => removeTutor(i)}
                className={styles.removeBtn}
                aria-label="Eliminar tutor"
              >
                ×
              </button>
            </div>
          ))}
          {(form.tutors_legals ?? []).length === 0 && (
            <p className={styles.muted}>Cap tutor legal afegit. Pots fer-ho ara o més tard.</p>
          )}
        </div>
      )}

      {isEdit && (
        <p className={styles.editHint}>
          Per editar els tutors legals d'un alumne existent, fes-ho des de l'API o crea
          una nova versió de la fitxa (Phase 2 follow-up afegirà aquest CRUD a la UI).
        </p>
      )}
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
