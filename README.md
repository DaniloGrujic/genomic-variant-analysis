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

```bash
poetry install

docker compose up -d db

poetry run uvicorn app.main:app --reload
```

## Run tests

```bash
poetry run pytest
```

## Project Structure

<details>
<summary>📁 variant-api</summary>

```text
variant-api/
├──.github/workflows
│   └──ci.yml
├── app/
│   ├── routes/
│   ├── services/
│   ├── models/
│   ├── schemas/
│   └── db/
├── alembic/
├── tests/
├── Dockerfile
├── .env.example
├── .gitignore
├── .pre-commit-config.yaml
├── alembic.ini
├── poetry.lock
├── docker-compose.yml
├── pyproject.toml
└── README.md
