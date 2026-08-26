.PHONY: backend-up backend-down backend-migrate backend-superuser backend-test domain-test backend-check backend-quality backend-verify

backend-up:
	docker compose up --build backend

backend-down:
	docker compose down

backend-migrate:
	docker compose run --rm backend python manage.py migrate

backend-superuser:
	docker compose run --rm backend python manage.py createsuperuser

backend-test:
	docker compose run --rm --no-deps -e DJANGO_SETTINGS_MODULE=config.settings.test backend pytest tests

domain-test:
	docker compose run --rm --no-deps -v ./tests:/app/tests:ro -w /app -e DJANGO_SETTINGS_MODULE= backend python -m unittest discover -s tests -v

backend-check:
	docker compose run --rm backend python manage.py check

backend-quality:
	docker compose run --rm --no-deps -w /app -e DJANGO_SETTINGS_MODULE=config.settings.test -e PYTHONPATH=/app/backend:/app backend sh -c "ruff check . && mypy backend finanzr"

backend-verify: domain-test
	docker compose run --rm --no-deps -w /app -e DJANGO_SETTINGS_MODULE=config.settings.test -e PYTHONPATH=/app/backend:/app backend sh -c "python backend/manage.py check && python backend/manage.py makemigrations --check --dry-run && pytest backend/tests && ruff check . && ruff format --check . && mypy backend finanzr"
