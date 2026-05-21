# Rols i permisos — Arxiu de notes

Aquest document descriu què pot fer cada tipus d'usuari del sistema, organitzat per àrea funcional. Les regles són aplicades **tant al frontend (com a UX) com al backend (com a seguretat real)** — l'API rebutja amb un error 403 qualsevol acció no permesa, encara que algú intentés trucar-la des de fora de la interfície.

---

## 1. Els tres rols

El sistema té dos rols base i un rol contextual:

| Rol | Què és | Com s'assigna |
|---|---|---|
| **Admin** | Personal de direcció / cap d'estudis / coordinador d'FP. Té control total sobre l'estructura del centre i les dades acadèmiques. | El primer usuari es crea al desplegament (`seed`). Els admins poden crear-ne d'altres a la pestanya Docents. |
| **Professor** | Docent qualsevol. Per defecte només té accés en lectura. Per posar notes necessita una **assignació docent** explícita per (grup, mòdul, curs acadèmic). | Quan es crea l'usuari (rol "professor") + el cap d'estudis l'assigna a un o més mòduls des de Administració → Assignacions docents. |
| **Tutor del grup** | No és un rol separat, sinó una *qualitat contextual* d'un professor. Un professor és tutor del grup X si i només si `grup.tutor_user_id = user.id`. Pot ser tutor de diversos grups. | El cap d'estudis l'assigna des de Administració → Grups classe, en crear o editar el grup. |

> **Nota important**: Un mateix usuari pot ser professor d'un grup, tutor d'un altre i no tenir cap relació amb un tercer. Els permisos es calculen sempre **per grup i per mòdul**, mai globalment per al professor.

---

## 2. Què pot fer cada rol

### 2.1 Estructura acadèmica i administració

| Acció | Admin | Professor | Tutor |
|---|---|---|---|
| Crear / editar / eliminar **famílies professionals** | ✅ | ❌ | ❌ |
| Crear / editar / eliminar **cicles formatius** | ✅ | ❌ | ❌ |
| Crear / editar / eliminar **mòduls** i **resultats d'aprenentatge (RA)** | ✅ | ❌ | ❌ |
| Crear / editar / eliminar **cursos acadèmics** (2025-2026, 2026-2027…) | ✅ | ❌ | ❌ |
| Clonar l'estructura d'un curs anterior per al curs nou | ✅ | ❌ | ❌ |
| Crear / editar / eliminar **grups classe** | ✅ | ❌ | ❌ |
| Crear / editar / eliminar **matrícules d'alumnes** | ✅ | ❌ | ❌ |
| Crear / editar / eliminar **assignacions docents** (qui dóna quin mòdul a quin grup) | ✅ | ❌ | ❌ |
| **Veure** tota l'estructura (cicles, mòduls, RAs, cursos) | ✅ | ✅ | ✅ |

### 2.2 Gestió d'usuaris i comptes

| Acció | Admin | Professor | Tutor |
|---|---|---|---|
| Crear comptes de docent (amb contrasenya reveal-once) | ✅ | ❌ | ❌ |
| Editar comptes (nom, departament, rol, activar/desactivar) | ✅ | ❌ | ❌ |
| Regenerar contrasenya d'un docent | ✅ | ❌ | ❌ |
| Regeneració massiva de contrasenyes amb CSV | ✅ | ❌ | ❌ |
| Enviar contrasenya per email (finestra de 5 min) | ✅ | ❌ | ❌ |
| **Veure** llistat de docents amb les seves assignacions | ✅ | ✅ | ✅ |
| Canviar la **pròpia** contrasenya | ✅ | ✅ | ✅ |

### 2.3 Avaluacions: estats i transicions

L'estat d'una avaluació recorre quatre fases — `oberta → docent → junta → tancada`. La transició és sempre cap a l'estat adjacent (no es pot saltar).

| Acció | Admin | Professor | Tutor |
|---|---|---|---|
| Crear una nova avaluació en un curs acadèmic | ✅ | ❌ | ❌ |
| Avançar avaluació `oberta → docent` | ✅ | ❌ | ❌ |
| Avançar avaluació `docent → junta` | ✅ | ❌ | ❌ |
| Avançar avaluació `junta → tancada` | ✅ | ❌ | ❌ |
| Tornar enrere una avaluació (rollback a l'estat anterior) | ✅ | ❌ | ❌ |
| **Veure** l'estat actual de cada avaluació | ✅ | ✅ | ✅ |

### 2.4 Notes i qualificacions — la part més delicada

Aquí entra en joc l'**estat de l'avaluació**. Les regles es resumeixen així:

#### Què pot **editar notes**

| Estat de l'avaluació | Admin | Professor amb assignació al (grup, mòdul) | Tutor del grup (sense assignació en aquest mòdul) | Professor sense res |
|---|---|---|---|---|
| `oberta` | ✅ | ❌ | ❌ | ❌ |
| `docent` | ✅ | ✅ **(període d'introducció de notes)** | ❌ | ❌ |
| `junta` | ✅ | ❌ | ✅ **(retocs finals en sessió de junta)** | ❌ |
| `tancada` | ❌ (cal rollback abans) | ❌ | ❌ | ❌ |

> **Per què aquesta separació?** L'estat `docent` és el període normal d'introducció: cada profe posa notes als seus mòduls. L'estat `junta` és la sessió on, després que els profes hagin tancat la seva part, el tutor del grup pot fer els retocs consensuats per l'equip docent — sobreescriure notes finals, posar observacions, etc. Un professor sense assignació al mòdul mai pot tocar notes en aquest mòdul, fins i tot si és tutor del grup d'un altre mòdul.

#### Què pot **veure**

| Acció | Admin | Professor | Tutor |
|---|---|---|---|
| Veure la graella de notes d'un grup × mòdul × avaluació | ✅ Tot | ✅ Només els seus (grup, mòdul) assignats | ✅ Tots els mòduls del seu grup tutoritzat |
| Veure l'expedient d'un alumne (totes les notes, tots els cursos) | ✅ Sempre | ✅ Només si té un (grup, mòdul) assignat on l'alumne està matriculat o si és tutor d'algun dels seus grups | igual |
| Veure el llistat d'un grup (alumnes matriculats) | ✅ Sempre | ✅ Només si té relació docent amb el grup o n'és tutor | igual |
| Veure l'estructura acadèmica (cicles/mòduls/RAs) | ✅ | ✅ | ✅ |

#### Sobre la nota final del mòdul

Cada cel·la de la columna **FINAL** del spreadsheet pot tenir dos valors:

- **Auto**: mitjana ponderada de les notes per RA, segons el pes de cada RA dins el mòdul. Es calcula al vol.
- **Manual**: el docent (o tutor en estat junta) escriu una nota final que sobreescriu el càlcul automàtic. Queda marcada com "M" a l'acta perquè quedi traça.

A l'auditoria queda registrat qui ha posat o canviat cada nota i quan.

### 2.5 Sortides: butlletins, actes, exports

| Acció | Admin | Professor | Tutor |
|---|---|---|---|
| Generar butlletí PDF d'un alumne | ✅ | ✅ (alumne ha d'estar al seu àmbit) | ✅ (alumne ha d'estar al grup que tutoritza) |
| Enviar butlletins per email a famílies | ✅ | ❌ | ✅ (només dels seus grups tutoritzats) |
| Generar **Acta de Junta d'Avaluació** en PDF | ✅ Sempre | ✅ Si està assignat al grup | ✅ Si tutoritza el grup |
| Reenviar / consultar enviaments fallits | ✅ | ❌ | ✅ (només els del seu grup) |
| **Exportar XLSX** d'expedient d'alumne | ✅ Sempre | ✅ Si és al seu àmbit | igual |
| **Exportar XLSX** de grup complet | ✅ Sempre | ✅ Si està assignat o és tutor | igual |
| **Exportar XLSX** d'una graella de notes (grup × mòdul) | ✅ Sempre | ✅ Si està assignat al mòdul + grup, o és tutor | igual |
| **Exportar XLSX** d'un curs sencer (totes les dades) | ✅ | ❌ | ❌ |
| **Exportar XLSX** estructura de cicle | ✅ | ✅ | ✅ |
| **Exportar XLSX** de la pròpia fitxa de docent | ✅ Sempre | ✅ (pròpia) | igual |
| **Exportar XLSX** de la fitxa d'un altre docent | ✅ | ❌ | ❌ |
| **Exportar CSV** del log d'auditoria | ✅ | ❌ | ❌ |

### 2.6 Estadístiques pedagògiques

| Acció | Admin | Professor | Tutor |
|---|---|---|---|
| Veure el panell d'estadístiques d'un (grup, mòdul, avaluació) | ✅ | ✅ Si està assignat al (grup, mòdul) | ✅ Si tutoritza el grup |

### 2.7 Imports

| Acció | Admin | Professor | Tutor |
|---|---|---|---|
| Importar alumnes des d'Excel/CSV | ✅ | ❌ | ❌ |
| Importar notes des d'Excel/CSV per (grup, mòdul, avaluació) | ✅ | ❌ (per ara — es pot habilitar per assignació si interessa) | ❌ |
| Descarregar plantilles CSV | ✅ | ✅ | ✅ |
| Veure l'historial d'imports | ✅ | ❌ | ❌ |

### 2.8 Administració i operació

| Acció | Admin | Professor | Tutor |
|---|---|---|---|
| Accés a la pestanya **Configuració** (`/administracio`) | ✅ | ❌ | ❌ |
| Accés a la **Paperera** (`/paperera`) — veure i restaurar elements soft-deleted | ✅ | ❌ | ❌ |
| Accés a **Auditoria** (`/audit`) — consultar tots els canvis | ✅ | ❌ | ❌ |

---

## 3. Resum visual — qui fa què a cada fase

```
            OBERTA      ─────►     DOCENT      ─────►      JUNTA       ─────►     TANCADA
   ┌──────────────────┐  ┌────────────────────────┐  ┌─────────────────────┐  ┌─────────────────┐
   │ Admin: configura │  │ Admin: tot              │  │ Admin: tot           │  │ Lectura per a    │
   │  estructura,     │  │ Profe assignat: edita   │  │ Tutor del grup:      │  │  tothom.         │
   │  no s'editen     │  │  notes RA del seu mòdul │  │  edita RA + nota     │  │ Generació de     │
   │  notes.          │  │ Tutor: només lectura    │  │  final manual        │  │  butlletins i    │
   │ Profes: lectura. │  │  (els seus grups)       │  │ Profe sense          │  │  actes.          │
   │                  │  │                         │  │  assignacio: lectura │  │ Per editar cal   │
   │                  │  │                         │  │                      │  │  rollback admin. │
   └──────────────────┘  └────────────────────────┘  └─────────────────────┘  └─────────────────┘
```

---

## 4. Defensa en profunditat — com s'aplica al codi

Per cada acció sensible hi ha **tres capes** de protecció:

1. **Frontend amaga la UI** — els botons d'editar només surten si l'usuari té el rol/permís adequat.
2. **API valida abans d'executar** — la dependency `AdminUser` o un check explícit de `permissions.can_edit_qualif_ra(...)` bloqueja la petició.
3. **El servei torna a verificar** — per defensa addicional contra bugs al routing.

A més:
- Cada acció sensible (canvi de nota, transició d'estat, regeneració de contrasenya…) deixa una entrada al **log d'auditoria** amb `who / when / before / after`. El log és append-only i mai s'esborra.
- Les contrasenyes són hash bcrypt cost 12.
- Els tokens JWT estan signats amb RS256, expiren als 15 minuts i es renoven via cookie HttpOnly Secure SameSite=Strict.

---

## 5. Casos límit que conviden a notar

- **Un professor pot ser tutor sense impartir mòduls al seu grup** (per exemple, el tutor de DAM1A imparteix Filosofia, no un mòdul DAM): pot veure totes les notes del grup i editar-les en fase `junta`, però durant la fase `docent` no toca cap nota (cada profe edita les seves).
- **Quan un alumne canvia de grup a mig curs**, la matrícula s'edita per admin i les notes ja introduïdes es queden lligades a la matrícula (no es perden ni es duplicen).
- **Quan un cicle es dóna de baixa**, les notes històriques associades es conserven (soft delete). Es poden recuperar des de la paperera.
- **L'admin no pot donar-se de baixa a si mateix** (protecció contra quedar-se sense administradors).
- **Quan una avaluació s'avança a `tancada`**, ningú no pot editar fins que l'admin faci rollback explícit. La transició a `tancada` registra `data_tancament`; el rollback la neteja.

---

*Document generat sobre el codi a `apps/backend/app/core/permissions.py` i `apps/backend/app/api/v1/*`. La matriu és la mateixa que el sistema aplica realment, en temps d'execució.*
