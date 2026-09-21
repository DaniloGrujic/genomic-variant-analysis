# Variant API

Backend API for managing genomic variant analysis projects.

## Tech Stack

- FastAPI
- PostgreSQL
- SQLAlchemy
- Poetry
- Docker
- Pytest
- Ruff

## Run locally

poetry install

docker compose up -d db

poetry run uvicorn app.main:app --reload

## Run tests

poetry run pytest
