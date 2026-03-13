include .env
export

.PHONY: migration-create migration-up migration-down

migration-create:
	@read -p "Enter migration message: " msg; \
	if [ -z "$$msg" ]; then \
		echo "Migration message cannot be empty."; \
		exit 1; \
	fi; \
	uv run alembic revision -m "$$msg"; \
	touch migrations/sql/up/"$$msg".sql; \
	touch migrations/sql/down/"$$msg".sql; \
	echo "Created empty SQL files:"; \
	echo "  migrations/sql/up/$$msg.sql"; \
	echo "  migrations/sql/down/$$msg.sql"

m-up:
	uv run alembic upgrade head
	docker exec -t multi_postgres pg_dump \
	-U $(POSTGRES_USER) \
	-d $(POSTGRES_DB) \
	-s \
	--no-owner --no-privileges --no-comments | \
	grep -vE '^\\(restrict|unrestrict)' > db/schema.sql

m-down:
	uv run alembic downgrade -1
	docker exec -t multi_postgres pg_dump \
	-U $(POSTGRES_USER) \
	-d $(POSTGRES_DB) \
	-s \
	--no-owner --no-privileges --no-comments | \
	grep -vE '^\\(restrict|unrestrict)' > db/schema.sql

gen:
	sqlc generate --file db/sqlc.yaml

get_db:
	psql -U $(POSTGRES_USER) -d $(POSTGRES_DB) -h localhost -p $(POSTGRES_PORT)

run-app:
	uv  run fastapi dev app/main.py 

lint:
	uv run ruff check .
check_type:
	uv run mypy .