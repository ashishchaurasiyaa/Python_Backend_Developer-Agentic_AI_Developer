# Convenience targets. Run `make help` to list.
.PHONY: help up down logs run install fmt

help:
	@grep -E "^[a-zA-Z_-]+:.*?## .*$$" $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*?## "}{printf "  %-10s %s\n", $$1, $$2}'

up: ## start postgres + redis (needs Docker Desktop)
	docker compose up -d

down: ## stop infra
	docker compose down

logs: ## tail infra logs
	docker compose logs -f

install: ## create venv + install deps
	python3 -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt

run: ## run the API (reload)
	uvicorn app.main:app --reload

fmt: ## format (needs ruff)
	ruff format app
