# Railway

PaaS used to host the API container and the PostgreSQL/PgVector database.

## Auth & CLI

- Install [`railway`](https://docs.railway.com/develop/cli) and run `railway login`.
- Each project has a `railway.json` at the repo root that controls the build & deploy.

## Common tasks

```sh
railway login                       # one-time browser auth
railway init                        # bind the current dir to a Railway project
nox -s deploy                       # provision DB + API + domain (orchestrated)
railway variables --set NAME=value  # set an env var on the active service
railway logs                        # tail logs
railway domain                      # get the public URL
```

## Architecture

- **Service `pgvector`** — PostgreSQL with pgvector extension. Connection vars: `PGHOST`, `PGUSER`, `PGPASSWORD`, `PGDATABASE`, `PGPORT`.
- **Service `api`** — Dockerfile-built FastAPI image. Reads `DB_*` env vars from the pgvector service.
- The two services share a Railway environment so internal hostnames work.

## Pitfalls

- Free tier sleeps after inactivity; first request after sleep is slow.
- Secrets must be set on both `pgvector` (Postgres password) and `api` (app secrets).
- `nox -s deploy` is idempotent — safe to re-run.
