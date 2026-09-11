# BlueZone V1

A locally runnable cybersecurity learning platform with a FastAPI backend, SQLite persistence, and a responsive black/blue interface. Start with networks, Linux, and web trust boundaries; progress through defensive analysis to **Operation Blue Horizon**, the advanced incident capstone.

## Start on Windows

Requires Python 3.11 or newer and internet access for the first dependency installation. Tested on Windows with Python 3.14.7. No Node build step or external database is required.

Open PowerShell in this folder and run:

```powershell
./start.ps1
```

Open **http://127.0.0.1:8000** for the BlueZone landing page. Choose **Start learning** to create an account or **Log in** to open the workspace at `/app`. There are no seeded administrator credentials. Keep the terminal running; Ctrl+C stops the server. If port 8000 is occupied, use `./start.ps1 -Port 8001` and open the matching port.

### Use other devices on the same network

Connect the phone, tablet, or second computer to the same Wi-Fi or wired network as the BlueZone computer. Find the BlueZone computer's IPv4 address with:

```powershell
ipconfig
```

Look under the connected Wi-Fi or Ethernet adapter for `IPv4 Address` (for example, `10.50.89.132`). Start BlueZone using that address:

```powershell
./start.ps1 -LanAddress 10.50.89.132
```

Replace the example address with the address shown on your computer. BlueZone will print the exact URL to open, such as `http://10.50.89.132:8000`. On the other device, open that URL in a browser. Use the same URL while signing in and using the app; do not switch between `localhost` and the LAN address in one session.

If Windows Firewall asks whether Python may communicate, allow it on **Private networks** only. If no prompt appears, open **Windows Security → Firewall & network protection → Allow an app through firewall**, enable the Python app for Private networks, and retry. Microsoft documents this as the place to add a firewall exception; keep the network profile Private and do not expose the training server on a public network. If the network uses client isolation or a guest Wi-Fi, devices may be unable to reach one another even when they have internet access.

The current computer address in this session is `10.50.89.132`; it may change after reconnecting to Wi-Fi, so check `ipconfig` again when needed. The LAN mode is for a trusted local network and development/testing. Use HTTPS and a proper reverse proxy before exposing BlueZone beyond the local network.

If local policy prevents running PowerShell scripts, run these commands individually; no policy change is required:

```powershell
python -m venv .venv
./.venv/Scripts/python.exe -m pip install -r requirements.txt
./.venv/Scripts/python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

For subsequent runs, the last command is sufficient. The data directory is created automatically, the versioned schema is initialized, and original curriculum is seeded without overwriting edits.

## Start on macOS or Linux

```sh
sh start.sh
```

Or create a virtual environment, install requirements, and run `python -m uvicorn app.main:app --host 127.0.0.1 --port 8000`. Native execution was tested on Windows; Unix startup is provided but was not executed in this environment.

## Create an administrator

Run this in the project folder on the server you control:

```powershell
./.venv/Scripts/python.exe -m app.manage create-admin --email admin@example.com --name "Administrator"
```

Replace the example address with your administrator address. The command privately prompts for a new passphrase twice. Sign in using that account to access Administration. Administrator creation is intentionally local; a web registration can only create a learner. An existing account is not silently promoted by this command.

Administration supports:

- User list with completion counts; suspension/restoration and role changes. Changes revoke affected sessions. You cannot change your own role or suspend yourself through this interface.
- Path creation and metadata editing.
- Mission creation, revision-aware editing, publishing and unpublishing. Lesson text, tasks, evidence, and simulated command responses use a structured JSON content editor.
- The latest 100 account and administrative audit events. The full audit remains in the database.

New missions append to the global prerequisite order. Published earlier incomplete missions block later new work. Existing completions and earned XP remain intact after edits or unpublishing; this preserves the learner's historical record. There is no destructive delete action in the admin interface.

## Learner journey

The public home (`/`) introduces the learning experience, previews the three paths and capstone, and includes a small interactive permissions exercise. The preview is a public teaching example and does not submit assessments or award XP. Learner registration and sign-in lead into `/app`; all real learning APIs retain their authentication and assessment rules. Previous root hash links such as `/#admin` and `/#unit/network-basics` redirect to their corresponding `/app` route.

| Path | Missions |
|---|---|
| Security foundations | Follow a packet; A file open to everyone; Know your trust boundaries; The unusual sign-in |
| The practical defender | Protect the session; Find the unexpected destination; Close the access gap; Contain, preserve, recover |
| Security operations | Model the failure before it happens; Build the incident timeline; A release worth defending; Operation Blue Horizon |

12 missions: 5 lessons, 3 guided labs, 3 CTF-style challenges, and 1 capstone. Assessments contain 27 findings in total. The initial curriculum awards 2,600 XP. Estimated times are guidance for reading, practice, and reflection, not tracked time-on-task.

Complete each assessment to unlock the next mission. Incorrect findings are marked with hints. Repeating a successful assessment does not duplicate XP. Progress includes completed missions, awarded XP, attempts, path achievements, the capstone badge, and a printable learning record.

Lab commands return approved fictional snapshots. They never execute shell commands, access arbitrary files, contact targets, or launch vulnerable containers. This is an intentionally contained V1 practice model.

## Optional AI tutor

The tutor works immediately as a clearly labeled **built-in lesson guide**, retrieving explanations and hints from the current lesson. It does not pretend to be AI.

To enable generated responses, set both server environment variables before starting:

```powershell
$env:OPENAI_API_KEY = "your-api-key"
$env:OPENAI_MODEL = "your-enabled-responses-model-id"
./.venv/Scripts/python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Choose a Responses-compatible model enabled in your API project. Never put the real key into source code or commit it. The app does not automatically load `.env`; `.env.example` documents the variables and can be used by Docker Compose.

Learners explicitly opt in for each AI question. Only the current public lesson text, their question, and up to ten recent messages from that mission are sent to OpenAI. Answer keys, session tokens, and email addresses are not added to the request. `store=false` is requested; this is not a guarantee of zero provider retention. Do not enter secrets or private investigation evidence. The last 40 messages per learner and mission are stored locally and can be cleared.

The adapter has a 25-second timeout, a bounded response, no executable tools, and a transparent built-in fallback for provider failures. Limits are eight requests per minute and 100 per day per learner. The tutor cannot award progress. Live provider access was not tested because no key/model was supplied; contract and failure handling were tested with a fake provider.

Reference: [OpenAI Responses API](https://developers.openai.com/api/reference/python/resources/responses/methods/create).

## Architecture

```text
Responsive HTML/CSS/JavaScript browser app
             | same-origin JSON + HttpOnly session cookie + CSRF header
             v
FastAPI routes and validated request models (app/main.py, models.py)
       |                 |                    |
 security.py         learning.py          tutor.py
 sessions/Argon2     prerequisites        built-in guide
 rate limits         grading / XP        optional Responses adapter
       |                 |                    |
       +----------- db.py --------------------+
              SQLite, WAL, foreign keys
              schema version 1 / short transactions
```

The browser never decides authorization, answer correctness, XP, or unlock status. The database is the source of truth. Unique completion keys plus transactional writes prevent duplicate awards during concurrent requests. SQL uses bound parameters.

Database entities: users, sessions, paths, units, completions, attempts, chats, audit, and limits. `PRAGMA user_version` tracks schema version. Future releases should add ordered migrations to `initialize()` and take a backup before changes. A newer schema causes this release to fail closed.

Security controls include Argon2id password hashes, 256-bit random session tokens stored as hashes, 12-hour session expiry, logout revocation, password-change revocation, active-account checks, administrator role checks, Origin validation, session-bound CSRF tokens, SameSite cookies, request limits, bounded inputs, a strict CSP, and escaped text rendering. Secure cookies and HSTS activate in production mode. Authentication is a server-session design rather than JWT. Password hashing follows the approach described in the [FastAPI security documentation](https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/).

## API and tests

`GET /openapi.json` exposes the complete machine-readable API contract; no remote Swagger assets are required. Main route groups:

| Routes | Purpose |
|---|---|
| `/api/auth/register`, `/login`, `/me`, `/logout`, `/password` | Account and session lifecycle |
| `/api/catalog`, `/api/units/{id}` | Paths and unlocked mission content |
| `/api/units/{id}/command`, `/submit` | Simulated evidence and assessment |
| `/api/progress` | Personal completion record and achievements |
| `/api/tutor`, `/api/tutor/{id}` | Guide, optional AI, and personal history |
| `/api/admin/overview`, `/users/{id}`, `/paths/{id}`, `/units/{id}` | Restricted management |
| `/api/health` | Database-backed health check |

All writes require an allowed `Origin`. Authenticated writes also require `X-CSRF-Token`, returned on sign-in and `/api/auth/me`. Cookies carry authentication; there is no localStorage token. Example API clients must send the Origin explicitly, even when they are not browsers.

```powershell
./.venv/Scripts/python.exe -m pip install -r requirements-dev.txt
./.venv/Scripts/python.exe -m pytest -q
```

`requirements-dev.lock` records every exact installed package version from validation. Install it for the fully pinned tested environment. The normal requirements pin direct dependencies.

20 tests passed in the latest validation. Tests use isolated temporary databases and cover the entire curriculum, cross-account isolation, hashed credentials, expiry/revocation, CSRF/origin/host enforcement, capacity, throttling, admin APIs, content revisions, unsupported lab commands, AI fallback, concurrent awards, LAN origins, public landing/workspace separation, and 100 independent learner sessions with 10 concurrent readers. The latter is a functional concurrency check, not a production load benchmark. Two upstream TestClient deprecation warnings are documented in STATUS.md.

## Backup and recovery

Default data file: `data/bluezone.db`. Override with an absolute `BLUEZONE_DB` path. Use SQLite's online backup API, which includes committed WAL data:

```powershell
./.venv/Scripts/python.exe -m app.backup C:/Backups/bluezone-2026-09-10.db
```

Choose a new filename each time. Protect backups as user data. To restore, stop all app processes, preserve the current database and its WAL/SHM files together in a separate recovery folder, then place the verified backup at the configured database path. Do not copy only a live `.db` file while ignoring its WAL. Start the app and verify health, sign-in, and progress.

Forgotten passwords use an operator-assisted reset in this V1:

```powershell
./.venv/Scripts/python.exe -m app.manage reset-password --email learner@example.com
```

Verify the person's identity out of band first. The command prompts privately and revokes every session. Email verification and self-service email recovery are not implemented.

## Optional container packaging

`Dockerfile` and `compose.yaml` are supplied. Docker was unavailable here, so this path is **not runtime-verified**.

```sh
docker compose up --build -d
docker compose exec bluezone python -m app.manage create-admin --email admin@example.com
```

Compose binds the app to localhost and keeps the database in a named volume. Do not remove that volume without a verified backup.

## Before production

This release is a tested local V1, not a claim of production certification. For a real cohort:

1. Deploy on a maintained Python host with a persistent local disk and adequate memory for Argon2 work. Start with one application process and measure representative sign-in and write workloads before choosing capacity. SQLite on a local disk fits this simple architecture; multi-host operation requires a shared database redesign, such as PostgreSQL, and tested migrations.
2. Configure HTTPS and `BLUEZONE_ENV=production`, `BLUEZONE_ORIGIN=https://your-domain`. Configure the health probe to send the allowed hostname. Review reverse-proxy trusted IP settings and edge limits so rate limiting uses trustworthy client addresses. Never expose development mode publicly.
3. Create named administrators, set restrictive filesystem and backup permissions, configure secrets through the host's secret store, and verify restore procedures.
4. Add operational monitoring, dependency vulnerability scanning, log retention, incident response ownership, and a review of authentication abuse/availability under load. Arrange an independent security review.
5. Configure and validate the chosen AI model with spending limits. Review data handling and learner notices. Expand email identity verification/recovery or use an approved identity provider if required by your deployment.
6. Have a cybersecurity educator review and pilot the curriculum. The advanced label describes the final level within this compact curriculum; it does not imply exhaustive professional training or accredited certification.

No payments, social network, native mobile apps, competitive leaderboard, external target scanning, or VM orchestration are included. These remain outside this V1.
