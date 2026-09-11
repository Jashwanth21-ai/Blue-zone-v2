# Deploy BlueZone on Render

The supplied chat logs show two related problems: `app` was missing from the uploaded repository, and `main:app` launched code that uses package-relative imports. Keep the package intact. Do not remove dots from Python imports.

## Upload the correct layout

Extract BlueZone-Render.zip. Upload the extracted contents to your GitHub repository, preserving the `app` folder. Do not upload the ZIP itself or flatten that folder. The repository root must contain:

```text
app/
  __init__.py
  main.py
  db.py
  ...
  static/
requirements.txt
render-start.sh
render.yaml
```

Do not upload `.env`, `.venv`, database files, or local accounts. The archive excludes these. Review existing repository changes before replacing files; old root-level Python copies are not used by the package startup command.

## Fix your existing Render service

In Blue-zone-v2, Settings:

| Setting | Value |
| --- | --- |
| Runtime | Python 3 |
| Branch | main |
| Root Directory | Leave empty |
| Build Command | `pip install -r requirements.txt` |
| Start Command | `sh render-start.sh` |
| Health Check Path | `/api/health` |

In Environment, set `PYTHON_VERSION=3.14.7`, `BLUEZONE_ENV=production`, and `BLUEZONE_MAX_USERS=100`. Remove a previously configured localhost `BLUEZONE_ORIGIN`; BlueZone now uses Render's own HTTPS URL automatically. Remove the unnecessary `PYTHONPATH` override from the previous advice. For a custom domain, set `BLUEZONE_ORIGIN` to its exact HTTPS origin without a path; use that domain for login.

Commit the corrected files, then deploy the latest commit. If the service's auto-deploy is enabled, the commit may already trigger deployment. The included blueprint is for creating a new free demonstration service; it does not automatically update an existing manually created service.

## Storage: choose before inviting learners

The free service is a demonstration. SQLite data, including accounts, progress and admin changes, can disappear after a restart, redeploy or spin-down. Never promise persistent progress on this configuration.

For the current SQLite architecture, select a paid web service and attach a persistent disk mounted at `/var/data`, then set `BLUEZONE_DB=/var/data/bluezone.db`. Keep one service instance and one worker. Confirm Render's current cost before purchasing. Back up the database regularly using `python -m app.backup` (see README). Adding a disk does not migrate data from a previous ephemeral instance. For a free service with durable external storage, a PostgreSQL migration and external database configuration remain separate work.

## Verify after deployment

1. Open the HTTPS URL shown in Render. The premium landing page should appear.
2. Open `/api/health`; expect `{"status":"ok","version":"1.0.0"}`.
3. Open `/app?mode=register`, register a test learner, sign out and sign back in.
4. Complete a beginner mission and confirm progress persists after signing back in.
5. For persistent hosting, repeat the check after a redeploy.

## Administrator on free Render

Open Render > Blue-zone-v2 > Environment. Privately add:

- `BLUEZONE_ADMIN_EMAIL`: your administrator email (use an address not already registered as a learner).
- `BLUEZONE_ADMIN_PASSWORD`: a unique passphrase of 12–128 characters.

Save and deploy. Startup creates the first administrator, stores only its Argon2 hash in the database, and records an audit event. Existing administrators are never overwritten. An existing learner is never silently promoted. Keep these values private; never put them in GitHub or chat. On the free demonstration, keeping them in Render recreates the administrator after an ephemeral database reset. Remove them after initial setup on persistent hosting. These settings are for initial provisioning, not password resets.

Sign in at `/app#admin`. Admin includes a cohort overview, mission-completion reports, account search and role/status filters, session counts and revocation, last sign-in times, content and path editing, and event-type filtering across the latest 100 audit events. Learners cannot access admin APIs. Session revocation does not remove progress or disable the account. Statistics label their counting rules; sessions do not imply online users.

The local `python -m app.manage create-admin --email YOUR_EMAIL` command remains available on hosts with shell access.

The built-in tutor works without an API key. Optional live AI requires `OPENAI_API_KEY` and `OPENAI_MODEL` as private Render environment variables. Do not commit keys.

## References

- https://render.com/docs/deploy-fastapi
- https://render.com/docs/environment-variables
- https://render.com/docs/free
- https://render.com/docs/disks

Deployment status: configuration prepared locally. A live deployment must be verified in the signed-in Render account; preparation alone does not publish the site.
