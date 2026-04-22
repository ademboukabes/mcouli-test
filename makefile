# Detect OS
ifeq ($(OS),Windows_NT)
    SHELL := powershell.exe
    .SHELLFLAGS := -NoProfile -Command
    RM = Remove-Item -Force
    TOUCH = New-Item -ItemType File -Force
else
    SHELL := /bin/sh
    RM = rm -f
    TOUCH = touch
endif

# Load environment variables from .env
ifneq ("$(wildcard .env)","")
    include .env
    export
endif

.PHONY: migration-create m-up m-down gen get_db run-app run-workers lint staging-check-up staging-check-logs staging-check-down

# Helper variable to call your new cleaning script
CLEAN_SCHEMA = uv run python scripts/clean_schema.py db/schema.sql

migration-create:
ifeq ($(OS),Windows_NT)
	@$$msg = Read-Host "Enter migration message"; \
	if ([string]::IsNullOrWhiteSpace($$msg)) { Write-Host 'Migration message cannot be empty.' -ForegroundColor Red; exit 1 }; \
	uv run alembic revision -m "$$msg"; \
	$(TOUCH) "migrations/sql/up/$$msg.sql" | Out-Null; \
	$(TOUCH) "migrations/sql/down/$$msg.sql" | Out-Null; \
	Write-Host "Created empty SQL files"
else
	@read -p "Enter migration message: " msg; \
	if [ -z "$$msg" ]; then echo "Migration message cannot be empty."; exit 1; fi; \
	uv run alembic revision -m "$$msg"; \
	touch migrations/sql/up/"$$msg".sql; \
	touch migrations/sql/down/"$$msg".sql; \
	echo "Created empty SQL files"
endif

m-up:
	uv run alembic upgrade head
	docker exec multi_postgres pg_dump -U $(POSTGRES_USER) -d $(POSTGRES_DB) -s --no-owner --no-privileges --no-comments > db/schema.sql
	$(CLEAN_SCHEMA)

m-down:
	uv run alembic downgrade -1
	docker exec multi_postgres pg_dump -U $(POSTGRES_USER) -d $(POSTGRES_DB) -s --no-owner --no-privileges --no-comments > db/schema.sql
	$(CLEAN_SCHEMA)

gen:
	sqlc generate --file db/sqlc.yaml

get_db:
	psql -U $(POSTGRES_USER) -d $(POSTGRES_DB) -h localhost -p $(POSTGRES_PORT)

run-app:
	uv run uvicorn app.main:app --reload

run-workers:
	@trap 'kill 0; exit' INT TERM; \
	uv run python -m app.worker.audit.main & \
	uv run python -m app.worker.notification.main & \
	uv run python -m app.worker.upload_group_worker.main & \
	uv run python -m app.worker.photo_worker.main & \
	uv run python -m app.worker.storage_cleaner.main & \
	wait

lint:
	uv run ruff check .

check_type:
	uv run mypy .

staging-check-up:
	docker compose -f docker-compose.staging.yml -f docker-compose.staging.local.yml up --build -d

staging-check-logs:
	docker compose -f docker-compose.staging.yml -f docker-compose.staging.local.yml logs -f fastapi

staging-check-down:
	docker compose -f docker-compose.staging.yml -f docker-compose.staging.local.yml down
