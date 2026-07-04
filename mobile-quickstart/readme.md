# multAI — Mobile Dev Quickstart

This folder contains everything you need to run the multAI backend locally. You do not need to clone the repo or install Python.

---

## Requirements

* **Docker Desktop** ([Download here](https://www.docker.com/products/docker-desktop))
* That is all!

---

## Folder contents

* `docker-compose.mobile.yml` — defines all backend services
* `.env.mobile` — environment variables (copy from `.env.mobile.example`)
* `seed.py` — database seed script
* `.mypy_cache/` — local Python type-check cache (safe to ignore/delete)
* `README.md` — this file

---

## First time setup

### 1. Copy the env file

```bash
cp .env.mobile.example .env.mobile
```

### 2. Start all services

```bash
docker compose -f docker-compose.mobile.yml up -d
```

This pulls and starts the following containers:

* **postgres** — the database
* **redis** — caching and session storage
* **minio** — photo file storage
* **nats** — message broker for background jobs
* **migrate** — runs database migrations once then exits
* **fastapi** — the API server

### 3. Copy the seed script into the container

```bash
docker cp seed.py multai-mobile-test-fastapi-1:/app/seed.py
```

> **Note:** Wait for all containers to show as running before doing this.

### 4. Seed the database

```bash
docker compose -f docker-compose.mobile.yml exec fastapi uv run python seed.py
```

This creates all the test data you need: users, events, photos, and notifications.

---

## Background workers

In addition to `postgres`, `redis`, `minio`, `nats`, `migrate`, and `fastapi`, the stack also starts these background workers by default:

* **email-worker** — sends transactional emails (OTP codes, notifications)
* **photo-worker** — processes uploaded photos and face recognition
* **audit-worker** — records audit log events
* **upload-group-worker** — manages grouped photo upload requests
* **storage-cleaner** — periodically cleans up orphaned files in MinIO

You don't need to do anything special for these — they start automatically with `docker compose up -d` and don't require any extra configuration.

## Notification worker (optional)

`notification-worker` is different — it needs a real Firebase service account file to run, so it's **off by default**. The rest of the backend (including all workers above) works fine without it.

If you need push notifications working locally:

1. Get `firebase-credentials.json` from the backend team.
2. Place it at the **project root** (one level above `mobile-quickstart/`), not inside this folder.
3. Start with the profile enabled:
```bash
docker compose -f docker-compose.mobile.yml --profile firebase up -d
```

If you forget the `--profile firebase` flag, `notification-worker` simply won't appear in `docker compose ps` — that's expected, not an error.

---

## Credentials

After seeding, the summary printed in the terminal shows all credentials. The default ones are:

### Mobile users
*(Use these to log in on the app)*

* `alice@example.com` / `Alice123!`
* `bob@example.com` / `Bob1234!`

### Staff users
*(For testing staff endpoints)*

* `admin@multai.dev` / `Admin1234!` (role: `admin`)
* `lead@multai.dev` / `Lead1234!` (role: `multi_team_lead`)
* `multi@multai.dev` / `Multi1234!` (role: `multi`)

### Events

* **Tech Conference 2025** — Join code: `TECH2025`
* **Annual Gala** — Join code: `GALA2025`

---

## Useful URLs

* **API docs:** http://localhost:8000/docs
---

## What the seed creates

* 2 mobile users with devices and active sessions
* 3 staff users
* 2 events with both users already joined
* 8 approved public photos uploaded to MinIO (4 per event)
* Face matches and photo approvals so gallery endpoints return results immediately
* Welcome notifications for each user
* Completed processing jobs so pipeline status endpoints look healthy
* Upload request groups for staff review endpoints

---

## Daily workflow

**Start the backend:**

```bash
docker compose -f docker-compose.mobile.yml up -d
```

**Stop the backend:**

```bash
docker compose -f docker-compose.mobile.yml down
```

---

## Reset everything
If you want a completely clean state with the latest image:
```bash
docker compose -f docker-compose.mobile.yml down -v
docker compose -f docker-compose.mobile.yml pull
docker compose -f docker-compose.mobile.yml up -d
docker compose -f docker-compose.mobile.yml ps
docker cp seed.py multai-mobile-test-fastapi-1:/app/seed.py
docker compose -f docker-compose.mobile.yml exec fastapi uv run python seed.py
```
> `down -v` removes all volumes. `pull` grabs the latest backend image before recreating containers. Check the `ps` output shows all containers as `Up`/`Healthy` before running the seed step — copying the seed script too early (before the fastapi container is ready) will fail.

---

## Update to the latest backend
When the backend team pushes a new version:
```bash
docker compose -f docker-compose.mobile.yml pull
docker compose -f docker-compose.mobile.yml up -d
docker compose -f docker-compose.mobile.yml ps
docker cp seed.py multai-mobile-test-fastapi-1:/app/seed.py
docker compose -f docker-compose.mobile.yml exec fastapi uv run python seed.py
```
> Re-copy the seed script after updating since the container is recreated. Run `ps` first to confirm the new container is actually up before copying/seeding.