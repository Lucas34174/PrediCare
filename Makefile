.PHONY: install lint format test run
install:
	pip install -r requirements-dev.txt
lint:
	ruff check . && ruff format --check .
format:
	ruff check --fix . && ruff format .
test:
	pytest --cov=predicare
run:
	uvicorn predicare.api.main:app --reload
migrate:
	docker compose run --rm --build api alembic upgrade head
