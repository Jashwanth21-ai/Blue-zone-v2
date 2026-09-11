# BlueZone V1 — final handover

Built from scratch on 10 September 2026 after confirming that the referenced conversation did not include a codebase.

## Completed milestones

| Milestone | Result |
|---|---|
| Backend and persistence | FastAPI, validated models, SQLite repository, schema versioning, WAL, consistent backup utility |
| Authentication | Registration, Argon2id passwords, server sessions, CSRF/origin checks, rate limits, logout and password changes |
| Curriculum | Three ordered paths; 12 assessed missions from foundations through the advanced capstone |
| Hands-on practice | Three contained labs, three evidence/CTF challenges, five lessons, one five-finding capstone |
| Progress | Server-enforced unlocks, idempotent XP, achievements, history, printable learning record |
| Tutor | Lesson-aware built-in guide; configurable OpenAI adapter with opt-in, history, limits, timeout, and fallback |
| Administration | Cohort management, roles, suspension, paths, revision-aware content publishing, audit trail |
| Interface | Responsive black/blue dashboard, curriculum, labs, assessments, tutor, progress, account and admin views |
| Public landing page | Premium dark/blue home, keyboard-accessible three-step mission preview, learning paths, capstone, FAQs, and working registration/sign-in links |
| Delivery | Source archive, Windows/Unix startup scripts, pinned dependencies, API schema, backup tool, container configuration, runbook |

## Validation

- **20 automated tests passed** on Windows/Python 3.14.7 in the 11 September update. Includes completing every mission and the capstone; admin API mutations; 100 isolated learner sessions; concurrent completion without duplicate XP; LAN origin handling; and public landing/workspace separation.
- JavaScript syntax and Python compilation passed.
- The running local app returned HTTP 200 and its database health check succeeded.
- Previously browser verified: registration, dashboard, first assessment and unlock, Linux simulated command, lab submission, tutor hint, persistence after reload, desktop layout at 1440px, and mobile layout at 390px. No browser console errors were observed during those checked flows. The new landing page was checked through HTTP responses, local asset and link validation, and JavaScript syntax checks; it was not visually browser-tested in this update.
- Starlette's test helper emitted two dependency deprecation warnings (httpx integration and the AnyIO BlockingPortal alias). These did not fail tests; review the test-helper dependencies during future upgrades.

## Architecture and operation

Browser interface → same-origin FastAPI routes → security/learning/tutor services → SQLite repository. The optional AI adapter calls the OpenAI Responses API; no client receives the API key.

Run `./start.ps1` from this folder, then open http://127.0.0.1:8000. To share a trusted LAN session, run `./start.ps1 -LanAddress YOUR_IPV4` and open the printed `http://YOUR_IPV4:8000` URL on each device. Use `python -m app.manage create-admin --email YOUR_EMAIL` within the installed environment to create a named administrator. See README.md for exact commands, configuration, backups, LAN/firewall notes, and production preparation.

The root now serves the public landing page. The learner/admin workspace is at `/app`; registration is `/app?mode=register`. Previous root hash routes redirect into the workspace. The application again uses a single configured origin and its matching host for production.

The source archive excludes runtime databases, test accounts, sessions, caches, virtual environments, and secrets. A separate local preview database contains the learner account used for browser QA; do not reuse that preview database for production. Create your own account to start with fresh progress.

## Known limitations and verification gaps

- **AI configuration required:** No live API key/model was provided. Provider success/failure contracts were tested with a fake provider; the built-in guide was tested live in the browser.
- **Contained simulations:** Commands retrieve fixed fictional evidence. No real virtual machine, packet capture engine, or arbitrary shell is provided.
- **Compact curriculum:** 12 missions and a capstone constitute the focused V1. This is not comprehensive advanced cybersecurity certification.
- **Admin browser check blocked:** Automatic approval review rejected a proposed persistent promotion of the preview learner for admin UI testing. No promotion occurred. Admin APIs and permissions passed isolated automated tests; admin screens were not exercised in the browser.
- **Authoring:** Mission bodies and assessment definitions use a structured JSON editor, not a rich-text CMS. Missions append to a single prerequisite sequence. Existing completion awards are not invalidated by curriculum edits.
- **Operations:** Local SQLite deployment; no multi-host failover, formal load benchmark, third-party penetration test, email verification, MFA, or automated email recovery. Password recovery is operator-assisted.
- **Container/Unix:** Files supplied, but Docker and Unix startup were not executed here.

Production needs HTTPS, durable storage, secrets, trusted proxy configuration, backup/restore drills, operational monitoring, representative load testing, an independent security review, educator review, and real AI validation if enabled. No public deployment was performed.
