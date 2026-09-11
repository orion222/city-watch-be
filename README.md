# city-watch-be

Backend API for City Watch, built with FastAPI, SQLModel, and Postgres.

## Prerequisites

- Python 3.14 (see `.python-version`)
- Docker + Docker Compose (Postgres and MinIO run as containers)

## Local setup

**1. Create your env file**

```bash
cp .env.example .env
```

Fill in `GEMINI_API_KEY` and `GEOAPIFY_API_KEY`; the rest of the defaults work as-is for local development.

**2. Install dependencies**

```bash
python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt
```

**3. Start the backing services**

Brings up Postgres on `:5432` and MinIO on `:9000` (console on `:9001`), and creates the report bucket.

```bash
docker compose up -d
```

**4. Apply migrations and seed data**

`alembic upgrade head` is idempotent — a database already at head does nothing. The app does not create tables itself, so this must run before the first boot.

```bash
alembic upgrade head
python -m db.seed
```

Pass `--force` to `db.seed` to wipe existing markers and addresses before reloading fixtures.

## Running the server

```bash
uvicorn main:app --reload --port 8000
```

The API is then at `http://localhost:8000`, with interactive docs at `http://localhost:8000/docs` and a health check at `http://localhost:8000/health`.

`python main.py` also works, but runs without auto-reload.

## Endpoints

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` `POST` `PUT` | `/marker`, `/marker/{id}` | Incident markers |
| `GET` `POST` `PUT` `DELETE` | `/address`, `/address/{id}` | Addresses attached to markers |
| `POST` | `/submit-report-gemini` | Text report parsed by Gemini |
| `POST` | `/submit-report-gemini-multimodal` | Image report parsed by Gemini |

## Database migrations

After changing a model in `db/models.py`:

```bash
alembic revision --autogenerate -m "describe the change"
alembic upgrade head
```

## Linting

Ruff is enforced in CI, and pre-commit runs it on staged files.

```bash
pre-commit install
ruff check . && ruff format --check .
```

Use `ruff check --fix .` and `ruff format .` to apply fixes.

## Environment variables

See `.env.example`:

- `GEMINI_API_KEY` — API key for Gemini.
- `GEOAPIFY_API_KEY` — API key for Geoapify geocoding.
- `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` — Docker database config.
- `DATABASE_URL` — SQLAlchemy connection string used by the app and by Alembic.
- `REDIS_URL` — rate-limit storage. Optional; without it slowapi keeps counters in process memory.
- `MINIO_ROOT_USER`, `MINIO_ROOT_PASSWORD` — credentials for the local MinIO container.
- `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION`, `AWS_BUCKET_NAME`, `AWS_ENDPOINT_URL`, `AWS_PUBLIC_URL_BASE` — boto3 storage config, pointed at MinIO locally.
