# Changelog

Tots els canvis notables d'aquest projecte queden documentats aquí.

El format segueix [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) i el
projecte adopta [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Pending decisions

- Integració amb el format d'export d'Esfera (formats de la Generalitat)
- Vista família amb magic link
- 2FA TOTP per a comptes d'admin (model ja preparat, UI pendent)

---

## [0.1.0] — 2026-05-21

Primera entrega. Sistema complet de gestió de notes per a un cicle d'FP.

### Added

#### Estructura acadèmica
- CRUD complet de **famílies professionals**, **cicles**, **mòduls** i **RAs**
- Editor de currículums amb pesos per RA i sumatori en viu (alerta si ≠ 100%)
- **Política de junta configurable per cicle**: mòduls bloquejants, llindar de
  suspesos per a "Recupera", % d'hores que força "No promociona"

#### Persones i organització
- Alumnes amb dades de contacte i tutors legals
- **Cursos acadèmics** amb activació; assistent **"Clonar curs"** per inicialitzar
  un curs nou a partir de l'estructura del previ
- **Grups classe** amb tutor; matrícules; assignacions docents
- Importació d'alumnes des d'Excel/CSV amb validació per fila

#### Avaluacions i qualificacions
- Màquina d'estats `oberta → docent → junta → tancada` amb rollback admin
- **Matriu de notes per RA** amb mitjana ponderada automàtica
- **Sobreescriptura manual de la nota final** del mòdul amb traça "M"
- **Comentaris per RA i per mòdul** des de la pròpia graella
- **Bulk paste des d'Excel** a la graella (Cmd+V des d'una columna)
- Permisos contextuals: admin sempre / professor amb assignació en `docent` /
  tutor del grup en `junta`

#### Sortides
- **Butlletins en PDF** generats amb WeasyPrint i enviats per email a famílies
- **Acta de Junta d'Avaluació** en PDF amb:
  - Taula resum per a la signatura ràpida
  - Detall per alumne amb el desglossament per RA dins de cada mòdul
  - Proposta automàtica de decisió (Apte / Recupera / No promociona / Pendent)
    amb motiu explícit
  - Signatures de tutor, cap d'estudis i director
- **Exportacions XLSX/CSV** per a totes les entitats (alumne, grup, mòdul,
  curs, cicle, docent, log d'auditoria)

#### Administració
- Pestanya **Administració** amb 6 tabs (Cursos, Famílies, Grups, Matrícules,
  Assignacions, **Email**)
- **Configuració SMTP des de la UI**: form amb prova abans de guardar, guia
  pas a pas per Gmail App Password, contrasenya encriptada al servidor
- **Paperera** per a restaurar elements soft-deleted (cicles, alumnes,
  matrícules, etc.)
- **Log d'auditoria** append-only de cada acció sensible amb actor + before/after
- Gestió de contrasenyes: reveal-once, regeneració individual i en bloc CSV

#### Arxiu (consulta històrica)
- Expedient d'alumne a través de tots els cursos acadèmics
- Expedient de grup històric
- Cerca transversal per DNI, RALC, nom, codi de grup
- Tree search inline a l'overview per filtrar cicles/grups

#### Estadístiques
- Panell d'estadístiques per (grup × mòdul × avaluació) amb histograma SVG,
  mediana, % aprovats i breakdown per RA

#### Seguretat
- JWT RS256 amb refresh rotation en cookie HttpOnly SameSite=Strict
- Bcrypt cost 12 per a contrasenyes
- Headers de seguretat (HSTS, CSP, X-Frame-Options) via nginx
- Rate limiting (5/min a login, 60/min a writes)
- Validació estructural: matrícula.curs == modul.curs aplicada arreu

#### Desplegament i operacions
- Docker Compose amb overlays dev / test / prod
- Bootstrap script PowerShell per a Windows Server (un sol comandament)
- Backup nightly amb mysqldump comprimit
- Smoke test (`make smoke`) per validar un stack en marxa
- CI a GitHub Actions amb lint, typecheck, tests + cobertura, build, audit
- Workflow de seguretat setmanal (pip-audit, pnpm audit, Trivy)
- Workflow E2E amb Playwright diari a `main`

### Documentation

- README, ARCHITECTURE, SECURITY, DEPLOYMENT, INSTALL_QUICK
- Matriu de permisos per rol (`docs/rols-i-permisos.md`)
- Diagrames model de dades, flux de creació d'usuari, estats d'avaluació
- Checklist del dia d'instal·lació

---

[Unreleased]: https://github.com/CoderAnchel/Arxiu/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/CoderAnchel/Arxiu/releases/tag/v0.1.0
