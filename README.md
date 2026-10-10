# Variant API

A REST API for managing genomic variant analysis projects, uploading VCF and ClinVar annotation files, and analyzing genetic variants.

## Tech Stack

- **Python** — Backend development
- **FastAPI** — REST API and interactive Swagger documentation
- **PostgreSQL** — Relational database
- **SQLAlchemy** — Asynchronous database operations
- **Alembic** — Database migrations
- **Poetry** — Dependency management
- **Docker Compose** — Containerized application and database
- **Pytest** — Automated testing
- **Ruff** — Linting and formatting

## Getting Started

### Option 1: Docker Compose (Recommended)

**Prerequisites:** Docker Desktop with Docker Compose.

1. Clone the repository:

   ```bash
   git clone https://github.com/DaniloGrujic/genomic-variant-analysis.git
   cd genomic-variant-analysis
   ```

2. Create the environment file:

   ```powershell
   Copy-Item .env.example .env
   ```

3. Build and start the application:

   ```bash
   docker compose up -d --build
   ```

   Docker Compose starts PostgreSQL, waits for the database to become healthy, applies pending Alembic migrations, and starts FastAPI.

4. Open the API documentation:

   **http://127.0.0.1:8000/docs**

To stop the application:

```bash
docker compose down
```

This preserves the PostgreSQL database volume.

### Option 2: Run Locally with Poetry

**Prerequisites:** Python, Poetry, and Docker Desktop.

1. Install dependencies:

   ```bash
   poetry install
   ```

2. Create `.env` from `.env.example` if it does not exist.

3. Start PostgreSQL:

   ```bash
   docker compose up -d db
   ```

4. Apply database migrations:

   ```bash
   poetry run alembic upgrade head
   ```

5. Start FastAPI:

   ```bash
   poetry run uvicorn app.main:app --reload
   ```

6. Open Swagger UI:

   **http://127.0.0.1:8000/docs**

**Note:** Don't run the Docker API container and local Uvicorn simultaneously on port 8000.

## API Endpoints

### Projects

| Method | Endpoint | Description |
|---|---|---|
| POST | `/projects/` | Create a project |
| GET | `/projects/` | List projects |
| DELETE | `/projects/{project_id}/` | Delete a project |

### VCF Files

| Method | Endpoint | Description |
|---|---|---|
| POST | `/projects/{project_id}/vcf/` | Upload a VCF file |
| GET | `/projects/{project_id}/vcf/` | List uploaded VCF files |
| GET | `/projects/{project_id}/vcf/{vcf_id}` | Retrieve VCF metadata and variants |
| DELETE | `/projects/{project_id}/vcf/{vcf_id}` | Delete a VCF file |

### Annotation Files

| Method | Endpoint | Description |
|---|---|---|
| POST | `/projects/{project_id}/annotation/` | Upload a ClinVar annotation file |
| GET | `/projects/{project_id}/annotation/` | List annotation files |
| DELETE | `/projects/{project_id}/annotation/{annotation_id}` | Delete an annotation file |

### Variant Analysis

| Method | Endpoint | Description |
|---|---|---|
| POST | `/analysis/{vcf_id}/annotate` | Annotate variants using ClinVar data |
| GET | `/analysis/{vcf_id}/variants` | Filter and paginate variants |
| GET | `/analysis/{vcf_id}/summary` | Generate variant statistics |
| GET | `/analysis/{vcf_id}/high-risk-variants` | Retrieve variants meeting high-risk criteria |

### Health

| Method | Endpoint | Description |
|---|---|---|
| GET | `/health` | Check API availability |

## Testing and Code Quality

Run automated tests:

```bash
poetry run pytest
```

Run linting:

```bash
poetry run ruff check .
```

Check formatting:

```bash
poetry run ruff format --check .
```

## Project Structure

```text
variant-api/
├── .github/
│   └── workflows/
├── alembic/
│   └── versions/
├── app/
│   ├── api/
│   │   └── routes/
│   │       ├── analysis.py
│   │       └── projects.py
│   ├── core/
│   ├── db/
│   ├── models/
│   ├── schemas/
│   └── services/
├── tests/
│   ├── test_projects.py
│   ├── test_vcf.py
│   ├── test_annotations.py
│   └── test_analysis.py
├── .env.example
├── .gitignore
├── .pre-commit-config.yaml
├── alembic.ini
├── docker-compose.yml
├── Dockerfile
├── poetry.lock
├── pyproject.toml
└── README.md
```

## Development Notes

- FastAPI uses the asynchronous `asyncpg` PostgreSQL driver.
- Alembic uses the synchronous `psycopg2` driver for database migrations.
- Docker Compose uses the `db` service hostname for database connections.
- Local development connects to PostgreSQL through `localhost:5432`.
- The `.env` file should remain untracked by Git.
