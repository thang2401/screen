.PHONY: install run-server run-client run-server-pro clean test

# Installation
install:
	pip install -r requirements.txt

install-dev:
	pip install -r requirements-dev.txt

# Run
run-server:
	python server/main.py

run-server-pro:
	python server/main_pro.py

run-client:
	python client/main.py $(HOST) $(PORT)

# Development
dev-server:
	uvicorn server.api.routes:app --reload --host 0.0.0.0 --port 8000

# Testing
test:
	python -m pytest tests/

test-coverage:
	python -m pytest tests/ --cov=. --cov-report=html

# Database
db-init:
	alembic init migrations

db-migrate:
	alembic revision --autogenerate -m "$(msg)"

db-upgrade:
	alembic upgrade head

# Docker
docker-build:
	docker-compose build

docker-up:
	docker-compose up -d

docker-down:
	docker-compose down

# Cleanup
clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	rm -rf .pytest_cache
	rm -rf htmlcov
	rm -rf *.egg-info

clean-data:
	rm -rf data/screenshots/*
	rm -rf data/recordings/*
	rm -rf data/logs/*
	rm -rf data/cache/*

clean-all: clean clean-data

# Benchmark
benchmark:
	python scripts/benchmark.py

# Deploy
deploy-server:
	bash scripts/deploy_server.sh

deploy-client:
	powershell -File scripts/deploy_client.ps1