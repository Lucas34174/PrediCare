.PHONY: install lint format test run
install:
	pip install -r requirements-dev.txt
lint:
	ruff check . && ruff format --check .
format:
	ruff check --fix . && ruff format .
test:
	pytest --cov=predicare -m "not llm"
run:
	uvicorn predicare.api.main:app --reload
migrate: ## migration de base de donnée
	docker compose run --rm --build api alembic upgrade head
backup: ## Exécute la sauvegarde PostgreSQL
	@bash scripts/backup.sh
restore: ## Restaure la dernière sauvegarde ou un fichier spécifié
	@bash scripts/restore.sh $(FILE)
test-cov: ## Exécute les tests avec rapport de couverture de code
	pytest --cov=predicare --cov-report=term-missing -m "not llm"
ingest: ## Nettoie et prépare les tables dans data/processed
	PYTHONPATH=src python -m predicare.db.ingest
features: ## Construit le jeu de features pour le ML
	PYTHONPATH=src python -m predicare.ml.features
features-sample: ## Construit un échantillon du jeu de features pour le ML
	PYTHONPATH=src python -m predicare.ml.features --sample 500 --seed 42
baseline: ## Entraîne et évalue les baselines LR et RF
	PYTHONPATH=src python -m predicare.ml.baseline
tune: ## Optimise XGBoost et LightGBM avec Optuna
	PYTHONPATH=src python -m predicare.ml.tuning --n-trials 20



	
