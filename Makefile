SHELL := /bin/zsh

BACKEND_DIR := backend
FRONTEND_DIR := frontend

.PHONY: up down logs backend frontend migrate seed test lint format demo kafka-topics metrics run-all scoring-eval

up:
	docker compose up --build

down:
	docker compose down -v

logs:
	docker compose logs -f --tail=150

backend:
	cd $(BACKEND_DIR) && python3 -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

frontend:
	cd $(FRONTEND_DIR) && npm install && npm run dev

migrate:
	cd $(BACKEND_DIR) && python3 -m alembic upgrade head

seed:
	cd $(BACKEND_DIR) && python3 seed.py

test:
	cd $(BACKEND_DIR) && python3 -m pytest
	cd $(FRONTEND_DIR) && npm install && npm run lint

lint:
	cd $(BACKEND_DIR) && python3 -m compileall app
	cd $(FRONTEND_DIR) && npm install && npm run lint

format:
	cd $(FRONTEND_DIR) && npm install && npm run lint -- --fix

demo:
	@echo "1. Copy .env.example to .env"
	@echo "2. Run: make up"
	@echo "3. Open http://localhost:3000"
	@echo "4. Login with recruiter1@hireos.ai / Demo@123"

kafka-topics:
	bash infra/kafka/create-topics.sh

metrics:
	@echo "Prometheus: http://localhost:9090"
	@echo "Grafana: http://localhost:3001"

run-all:
	bash scripts/run_everything.sh

scoring-eval:
	python3 scripts/run_scoring_eval.py
