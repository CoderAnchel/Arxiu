# Arxiu de notes

Production grade-management platform for Catalan FP (*Formació Professional*) cycles.
Built as a permanent academic archive — historical data is first-class, not an afterthought.

[![CI](https://github.com/CoderAnchel/Arxiu/actions/workflows/ci.yml/badge.svg)](https://github.com/CoderAnchel/Arxiu/actions/workflows/ci.yml)
[![Security](https://github.com/CoderAnchel/Arxiu/actions/workflows/security.yml/badge.svg)](https://github.com/CoderAnchel/Arxiu/actions/workflows/security.yml)
[![codecov](https://codecov.io/gh/CoderAnchel/Arxiu/branch/main/graph/badge.svg)](https://codecov.io/gh/CoderAnchel/Arxiu)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/)
[![Node](https://img.shields.io/badge/node-20+-43853d.svg)](https://nodejs.org/)

---

## Què fa

Gestiona el cicle complet d'avaluació d'un institut d'FP:

- **Alumnes, grups, matrícules, docents** amb permisos contextuals (admin / professor amb assignació / tutor de grup)
- **Introducció de notes per RA** amb mitjana ponderada automàtica i sobreescriptura manual
- **Estats d'avaluació** (`oberta` → `docent` → `junta` → `tancada`) amb permisos diferenciats per fase
- **Generació de butlletins en PDF** i enviament per email a famílies
- **Acta de Junta d'Avaluació** automatitzada amb política configurable per cicle (mòduls bloquejants, llindar de recuperació, % d'hores)
- **Importacions** d'alumnes i notes des d'Excel/CSV amb validació per fila
- **Exportacions** XLSX/CSV de tot (alumne, grup, mòdul, curs, cicle, docent, auditoria)
- **Arxiu permanent**: soft delete a tot arreu, paperera amb restauració, log d'auditoria append-only

## Captures

| Qualificacions | Acta de Junta | Expedient |
|---|---|---|
| ![Qualificacions](docs/screenshots/qualificacions.png) | ![Acta](docs/screenshots/acta.png) | ![Expedient](docs/screenshots/expedient.png) |

## Stack

| Capa | Tecnologia |
|---|---|
| Frontend | React 18 + TypeScript + Vite, TanStack Query, Zustand, React Hook Form + Zod |
| Backend | FastAPI 0.115 + Pydantic v2 + SQLAlchemy 2.0 (async) + Alembic |
| Base de dades | MySQL 8.0 (InnoDB, utf8mb4) |
| Background jobs | ARQ + Redis |
| PDF / email | WeasyPrint + aiosmtplib + Jinja2 |
| Auth | DNI/email + bcrypt + JWT RS256, refresh cookie SameSite=Strict |
| Container | Docker Compose (dev / test / prod overlays) |
| Desplegament | Windows Server amb NSSM, nginx + Let's Encrypt |

Veure [`ARCHITECTURE.md`](./ARCHITECTURE.md) per al disseny detallat del sistema i [`SECURITY.md`](./SECURITY.md) per al model de seguretat.

## Quick start

```bash
# 1. Clonar, copiar env d'exemple, generar claus JWT, construir imatges
make bootstrap

# 2. Arrencar el stack de desenvolupament
make dev

# 3. En un altre terminal: migracions + dades demo
make migrate
make seed
```

Després obre:
- Frontend — http://localhost:5173
- API docs (OpenAPI) — http://localhost:8000/api/v1/docs
- MailHog (correu intern) — http://localhost:8025

Crida `make help` per veure tots els objectius disponibles.

## Estructura del repositori

```
arxiu-prod/
├── apps/
│   ├── frontend/                # React + Vite + TS
│   └── backend/                 # FastAPI + SQLAlchemy
├── packages/
│   └── api-types/               # Tipus TS generats des d'OpenAPI
├── infra/
│   ├── compose/                 # Stacks Docker Compose (dev / test / prod)
│   ├── nginx/                   # Reverse proxy + headers de seguretat
│   └── windows-server/          # Bootstrap PowerShell + backup + admin guide
├── docs/                        # Documentació, diagrames, captures
├── scripts/                     # Smoke test, pre-publish check, backup
├── .github/workflows/           # CI / Security / E2E
└── Makefile                     # Orquestració de comandes
```

## Documentació

- [`ARCHITECTURE.md`](./ARCHITECTURE.md) — disseny del sistema
- [`SECURITY.md`](./SECURITY.md) — model d'autenticació i hardening
- [`DEPLOYMENT.md`](./DEPLOYMENT.md) — runbook de producció (Windows Server)
- [`INSTALL_QUICK.md`](./INSTALL_QUICK.md) — instal·lació ràpida en 3 passos
- [`docs/rols-i-permisos.md`](./docs/rols-i-permisos.md) — matriu de permisos per rol
- [`docs/install-day-checklist.md`](./docs/install-day-checklist.md) — checklist del dia d'instal·lació
- [`CHANGELOG.md`](./CHANGELOG.md) — versions i canvis

## Tests i qualitat

```bash
make test            # backend (pytest) + frontend (vitest)
make test-backend    # pytest amb cobertura (objectiu ≥85%)
make test-frontend   # vitest amb cobertura (objectiu ≥70%)
make lint            # ruff (backend) + eslint (frontend)
make typecheck       # mypy (backend) + tsc (frontend)
make e2e             # Playwright contra el stack complet
```

Tot el pipeline anterior s'executa automàticament a cada push i pull request via GitHub Actions. Cap PR es pot fusionar amb el CI vermell.

## Desplegament

Producció corre sobre Windows Server via Docker Compose. Veure [`DEPLOYMENT.md`](./DEPLOYMENT.md) per al runbook complet i [`INSTALL_QUICK.md`](./INSTALL_QUICK.md) per a la instal·lació en 3 passos a través del script `bootstrap.ps1`.

## Estat del projecte

Implementació per fases — veure [`ARCHITECTURE.md`](ARCHITECTURE.md) per al disseny i [`DEPLOYMENT.md`](DEPLOYMENT.md) per a la guia de desplegament.

| Fase | Abast | Estat |
|---|---|---|
| 0 | Scaffold del monorepo | ✅ complet |
| 1 | Auth & users | ✅ complet (Google OAuth diferit) |
| 2 | Catàleg i people CRUD | ✅ complet |
| 3 | Avaluacions i qualificacions | ✅ complet |
| 4 | Outputs (PDF + email) | ✅ complet |
| 5 | Imports i auditoria | ✅ complet |
| 6 | Hardening | ✅ complet (security headers, rate limiting, observability, backups, E2E smoke) |
| 7 | Desplegament Windows Server | ✅ complet (`install.ps1`, runbook, admin guide) |

## Llicència

[MIT](./LICENSE) — Anchel Ascaso Castro, 2026.

Projecte fet com a entrega de l'assignatura **Desplegament** del cicle DAW a l'Institut la Ferreria.
