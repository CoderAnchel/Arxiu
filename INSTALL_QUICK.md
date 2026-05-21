# Instal·lació ràpida — Windows Server

**Temps estimat: 15-20 minuts** (la primera vegada, la majoria del temps és Docker baixant imatges).

## ✋ Prerequisits (un sol cop)

Abans de res, al Windows Server cal:

1. **Docker Desktop per Windows** instal·lat i en marxa.
   - Descarrega de: https://www.docker.com/products/docker-desktop/
   - Després d'instal·lar, **inicia Docker Desktop** i espera que aparegui "Engine running" verd a la safata
2. **PowerShell 5.1 o superior** (ja ve amb Windows)
3. **Internet** durant la instal·lació (per baixar les imatges)

**Confirma que Docker va**:
```powershell
docker version
```
Has de veure tant "Client" com "Server". Si només surt el Client, Docker Desktop no està en marxa.

---

## 🚀 Instal·lació (3 passos)

### 1. Copia el codi al servidor

Opció A — via Git (recomanat si tens accés):
```powershell
cd C:\
git clone <URL_DEL_REPO> arxiu
cd C:\arxiu
```

Opció B — sense Git: copia la carpeta `arxiu-prod` sencera a `C:\arxiu` per xarxa, USB o el que sigui.

### 2. Permet executar scripts (només per a aquesta sessió)

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

### 3. Llança el bootstrap

```powershell
cd C:\arxiu
.\infra\windows-server\bootstrap.ps1
```

> Si el port 80 ja l'usa una altra app, fes-ho amb un altre port (ex: 8080):
> ```powershell
> .\infra\windows-server\bootstrap.ps1 -Port 8080
> ```

L'script et farà tot automàticament: construir imatges, aixecar la stack, migrar la base de dades, carregar dades demo, i al final t'imprimirà la URL i la contrasenya inicial d'administrador.

---

## ✅ Verifica que funciona

Quan el script acabi, hauràs de veure quelcom com:

```
  Arxiu de notes està en marxa!

  Accessible a:
    http://localhost:8080
    http://192.168.1.42:8080      (des d'altres equips de la xarxa)

  Credencials d'administrador inicial:
    DNI/usuari:   00000000T
    Contrasenya:  Xyz9-K3pQ-mP2w-aB7r
```

Obre el navegador, ves a aquesta URL i fes login amb les credencials que t'ha imprès. **El sistema et demanarà canviar la contrasenya** al primer accés — fes-ho i guarda-la bé.

---

## 🎓 Què hi haurà preparat per testejar

Després del bootstrap, l'aplicació ja té dades demo carregades:

- **3 cursos acadèmics** (2024-2025, **2025-2026 actiu**, 2026-2027)
- **4 famílies professionals** (Informàtica, Administració, Sanitat, Hostaleria)
- **2 cicles** (DAM — Desenvolupament d'Aplicacions Multiplataforma, SMX — Sistemes Microinformàtics)
- **Tots els seus mòduls i RAs** amb pesos correctes
- **5 docents** d'exemple (les seves contrasenyes inicials estan al fitxer `secrets\seed_credentials.csv`)
- **2 grups classe** (DAM1A, SMX1A) amb tutor assignat
- **8 alumnes** matriculats
- **3 avaluacions** del curs actual, amb la primera ja tancada amb notes

Així el cap d'estudis pot **entrar amb l'admin, mirar i tocar tot** sense haver de configurar res primer.

---

## 🛠 Manteniment diari

Tot des de PowerShell, dins de `C:\arxiu`:

```powershell
# Veure si tot està en marxa
docker compose -f infra\compose\docker-compose.yml -f infra\compose\docker-compose.prod.yml ps

# Veure logs del backend (Ctrl+C per sortir)
docker compose -f infra\compose\docker-compose.yml -f infra\compose\docker-compose.prod.yml logs -f backend

# Aturar tot
docker compose -f infra\compose\docker-compose.yml -f infra\compose\docker-compose.prod.yml down

# Tornar a aixecar (sense reconstruir)
docker compose -f infra\compose\docker-compose.yml -f infra\compose\docker-compose.prod.yml up -d

# Backup manual de la base de dades
.\infra\windows-server\backup.ps1

# Tornar a aplicar canvis després d'un git pull
.\infra\windows-server\bootstrap.ps1
```

> El bootstrap és **idempotent**: el pots executar tantes vegades com vulguis. Si tot ja està fet, només verifica i continua. No esborra res.

---

## 🆘 Si alguna cosa no va

### Docker Desktop no s'inicia

- Comprova que tens **Windows Server 2019 o 2022** amb actualitzacions recents
- Activa **WSL2** o **Hyper-V** segons el missatge de Docker
- Si Docker Desktop no és viable, alternativa: **Mirantis Docker Engine** (de pagament però oficial)

### El port 80/8080 està ocupat

- Tria un altre port: `bootstrap.ps1 -Port 9000`
- O comprova què l'ocupa: `Get-NetTCPConnection -LocalPort 80`

### "Cannot connect to MySQL"

Aquest error sovint és transitori. Espera 1-2 minuts i prova de tornar:
```powershell
.\infra\windows-server\bootstrap.ps1 -SkipBuild
```

Si persisteix, mira els logs:
```powershell
docker compose -f infra\compose\docker-compose.yml -f infra\compose\docker-compose.prod.yml logs mysql
```

### Vull recomençar des de zero

```powershell
# CUIDADO: això esborra TOTES les dades.
docker compose -f infra\compose\docker-compose.yml -f infra\compose\docker-compose.prod.yml down -v
Remove-Item C:\arxiu\secrets\* -Force
Remove-Item C:\arxiu\.env.production -Force
.\infra\windows-server\bootstrap.ps1
```

---

## 📞 Per a la reunió amb el centre

Si tot funciona, el que has de **donar al cap d'estudis** és aquesta informació en un correu:

```
Bones,

L'Arxiu de notes ja està instal·lat al servidor del centre.

  URL:           http://<ip-del-servidor>:8080
  Usuari admin:  00000000T
  Contrasenya:   <la que ha generat el bootstrap>

Quan entris per primer cop et demanarà canviar la contrasenya — guarda-la
bé, és la d'administrador del sistema.

Hi ha dades demo carregades per a què pugueu provar lliurement sense por
de trencar res (cicles DAM i SMX, 2 grups, 8 alumnes). Quan vulgueu començar
amb les dades reals, els podem netejar i començar de zero o partir d'aquí.

Adjunto el document `rols-i-permisos.md` perquè vegis què pot fer cada
tipus d'usuari (admin / professor / tutor).

Qualsevol problema o pregunta, dimes.
```
