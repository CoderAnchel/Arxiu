# Guia ràpida per a l'administrador

Aquesta és la guia per al **Sergi** (i futurs admins) — accions del dia a dia
des del navegador. No requereix tocar la consola.

## 1. Entrar

Navega a **https://arxiu.inslaferreria.cat** i entra amb el teu **DNI** i la
contrasenya. La primera vegada se't demanarà canviar-la per una de pròpia.

> **Has oblidat la contrasenya?** Cap altre admin pot reiniciar-la des de
> *Docents → tu mateix → Regenerar contrasenya* (necessita un altre admin amb
> sessió activa). Si ets l'únic admin, contacta amb el TIC del centre per
> executar el procediment de recuperació.

## 2. Configuració d'inici de curs

L'ordre típic per posar a punt un curs nou:

1. **Currículums** — repassa que els cicles, mòduls i RAs estiguin actualitzats
2. **Avaluacions → Nova avaluació** — crea les 3 avaluacions del curs
3. **Importacions → Alumnes** — puja l'Excel d'alumnes nous (Phase 5 wired)
4. **Docents** — crea comptes de professor, comparteix les contrasenyes
5. **Grups** (per API per ara — UI al follow-up) — crea els grups classe i
   assigna tutor a cadascun
6. **Assignacions docents** (per API per ara) — qui dóna quin mòdul a quin grup

## 3. Cicle d'avaluació

Aquest és el flux més habitual:

| Estat | Qui pot què |
|---|---|
| **oberta** | Configuració. Ningú no introdueix notes encara. |
| **docent** | Cada professor entra notes per RA dels seus mòduls. |
| **junta** | El tutor del grup pot revisar i modificar qualsevol nota. |
| **tancada** | Tot bloquejat. Es generen butlletins i s'envien per email. |

Per avançar d'estat: **Avaluacions → triar avaluació → Avançar a [següent]**.
Si necessites tornar enrere (correccions de darrera hora), pots fer "Tornar a
[anterior]". Tot queda registrat al log d'auditoria.

## 4. Butlletins + emails

Un cop l'avaluació és **tancada**:

1. Vés a **Butlletins**
2. Tria curs · grup · avaluació
3. Selecciona els alumnes (o "Tots")
4. Configura les opcions del PDF (detall RA, signatura, etc.)
5. **Generar PDFs** → descarrega un ZIP per imprimir o desar
6. **Enviar emails** → envia el PDF a l'alumne i als tutors legals

Per veure què s'ha enviat, vés a **Enviaments**. Filtra per `rebotat` o
`error` per veure els que han fallat. **Reenviar** des del modal de detall.

## 5. Importacions

**Importacions → Alumnes** accepta CSV o Excel (.xlsx). Format mínim:

| RALC | Nom | Cognoms | DNI | Email | Email tutor |
|---|---|---|---|---|---|
| 12345678 | Aleix | Vilanova | 12345678Z | aleix@... | tutor@... |

El sistema valida cada fila abans de confirmar. Si una fila té errors, es marca
en vermell i no s'importa — la resta sí. Pots tornar a pujar el fitxer després
de corregir els errors.

## 6. Auditoria

Tot queda registrat: qui ha entrat, qui ha canviat quina nota, qui ha enviat
quin email, qui ha pujat quin fitxer. Consulta el log a:

- API: `GET /api/v1/audit-logs` (admin-only)
- (UI dedicada arriba al follow-up; per ara via API o consultes SQL directes)

## 7. Backups

S'executen automàticament cada nit a les 03:00 i es guarden 30 dies. Si
necessites un backup ara mateix (per exemple abans de fer una restauració),
demana al TIC que executi `backup.ps1`. La restauració és exclusiva del TIC
i requereix doble confirmació.

## 8. En cas d'emergència

- **No puc entrar** — borra la cookie i torna-ho a provar; comprova majúscules
  al DNI; si segueix fallant, demana a un altre admin que regeneri la
  contrasenya
- **Un email no surt** — vés a *Enviaments*, filtra per `error`, llegeix el
  missatge d'error; els més comuns són tipus `mailbox unavailable` (l'adreça
  no existeix) o errors temporals de l'SMTP
- **Una nota incorrecta enviada al butlletí** — *Avaluacions → Tornar a
  junta*, corregeix la nota a *Qualificacions*, torna a *tancada*, regenera
  els butlletins afectats

## 9. Contacte

- **TIC del centre** — operacions del servidor, restauracions, incidències
  greus
- **Coordinació pedagògica** — preguntes de procediment (què és una avaluació
  *junta*, quan tancar, com gestionar repetidors, etc.)
