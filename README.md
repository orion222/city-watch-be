# city-watch-be

Backend API for City Watch, built with FastAPI, SQLModel, and Postgres.

## Local setup

```
docker compose up -d
alembic upgrade head        # apply migrations — idempotent, a DB already at head does nothing
python -m db.seed           # seed fixture data
```

`alembic upgrade head` runs before the app boots — the app no longer creates tables itself.

### Environment variables

See `.env.example`:

- `GEMINI_API_KEY` — API key for Gemini.
- `GEOAPIFY_API_KEY` — API key for Geoapify geocoding.
- `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` — Docker database config.
- `DATABASE_URL` — SQLAlchemy connection string used by the app and by Alembic.
