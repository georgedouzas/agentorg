# Fixtures

Each fixture (`investment-team/`, `eng-team/`) is a frozen snapshot of what `agentorg`
generates from the corresponding `agentorg.json`. The committed `output/example.env`
is the contract — tested against the rendered Jinja template.

## Running a fixture locally

Secrets are managed centrally in `tests/fixtures/.env` (gitignored). To run a
fixture, generate its `.env` from the central file, then `docker compose up`:

```sh
# One-time: create tests/fixtures/.env with your real secrets
cp tests/fixtures/investment-team/output/example.env tests/fixtures/.env
$EDITOR tests/fixtures/.env

# Each time you want to (re)render a fixture's .env
nox -s fixture_env -- investment-team   # or `eng-team`, or `all`

# Then run it
cd tests/fixtures/investment-team/output && docker compose up -d --build
```

The central `tests/fixtures/.env` is the union of every fixture's keys. `fixture_env`
takes the keys listed in each fixture's `output/example.env` and fills values from
the central file; missing keys log a warning but the file still renders.

Both `tests/fixtures/.env` and `tests/fixtures/*/output/.env` are gitignored.
