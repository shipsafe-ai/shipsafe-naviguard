.PHONY: setup run run-api run-adk test seed help

help:
	@echo "Targets:"
	@echo "  make setup    - uv sync + remind to copy .env"
	@echo "  make run      - one-shot NaviGuard pipeline (SCENARIO=hormuz)"
	@echo "  make run-api  - start FastAPI server"
	@echo "  make run-adk  - ADK dev loop"
	@echo "  make test     - pytest with coverage"
	@echo "  make seed     - seed Phoenix with Hormuz crisis fixtures"

setup:
	uv sync --extra dev
	@test -f .env || (cp .env.example .env && echo "Tip: fill in .env with your keys.")

run:
	uv run python -m agent.main $(if $(SCENARIO),--scenario $(SCENARIO),)

run-api:
	uv run uvicorn api.main:app --host 0.0.0.0 --port ${PORT:-8080} --reload

run-adk:
	cd agent && uv run adk run naviguard

test:
	uv run pytest --cov=agent --cov=api --cov-fail-under=85 tests/

seed:
	uv run python fixtures/seed_phoenix.py

dashboard-dev:
	cd dashboard && npm run dev

dashboard-install:
	cd dashboard && npm install
