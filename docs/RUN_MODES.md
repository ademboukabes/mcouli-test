# Run Modes Guide

There are three ways to run the backend. Pick the one that matches what you are trying to do.

## 1) Backend Dev Mode (Hot Reload)

Use this for normal backend development.

What runs:

- Infrastructure containers only: Postgres, Redis, NATS, MinIO, pgAdmin
- FastAPI runs on your host machine with reload (`uvicorn --reload`)

Commands:

```powershell
docker compose -f docker-compose.yml up -d
make run-app
```

Optional workers:

```powershell
make run-workers
```

Best for:

- Fast local iteration
- Debugging backend code with auto-reload

---

## 2) Staging Mode (Frontend / Shared Image-Based)

Use this when the frontend team (or anyone else) needs a stable backend running from the published image.

What runs:

- Infrastructure containers
- `fastapi` and `migrate` from `ghcr.io/microclub-usthb/multai-back:latest`

Commands:

```powershell
docker compose -f docker-compose.staging.yml up -d
```

Check status and logs:

```powershell
docker compose -f docker-compose.staging.yml ps
docker compose -f docker-compose.staging.yml logs -f fastapi
```

Health check:

```powershell
curl -I http://localhost:8000/docs
```

Note:

- The first startup can take a while because model files are downloaded during app initialization.

---

## 3) Backend Staging-Check Mode (Current Local Code in Containers)

Use this before pushing or opening a PR to verify your current local code works in the same containerized setup as staging.

What runs:

- Base staging services from `docker-compose.staging.yml`
- Local overrides from `docker-compose.staging.local.yml`:
  - build from the local `Dockerfile`
  - `pull_policy: never`
  - source code mounted into `/app`

Commands (recommended via Makefile):

```powershell
make staging-check-up
make staging-check-logs
make staging-check-down
```

Equivalent raw compose commands:

```powershell
docker compose -f docker-compose.staging.yml -f docker-compose.staging.local.yml up --build -d
docker compose -f docker-compose.staging.yml -f docker-compose.staging.local.yml logs -f fastapi
docker compose -f docker-compose.staging.yml -f docker-compose.staging.local.yml down
```

Best for:

- Validating migrations and API startup in containers
- Catching container/runtime issues before sharing changes

---

