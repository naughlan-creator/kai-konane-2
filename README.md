# Kai Konane

[![Build Status](https://dev.azure.com/nolantheledi/kai-konane/_apis/build/status%2Fkai-konane-ci?branchName=main)](https://dev.azure.com/nolantheledi/kai-konane/_build/latest?definitionId=1&branchName=main)

A STEM learning platform for preschoolers, with separate experiences for
children, parents and teachers. Children work through illustrated activities and
stories; a per-child learning plan decides what they are shown; teachers and
parents follow progress and message each other about a specific learner.

Built as a Flask monolith, now decomposed into four services behind an nginx
gateway. See [docs/architecture.md](docs/architecture.md) for the design and the
full API contract.

![Architecture](docs/img/architecture.png)

## What it does

**For children** — an activity library filtered to their level, multiple-choice
questions with audio feedback, and page-by-page stories that remember where they
stopped.

**For teachers** — a roster of learners, per-strand learning plans, progress and
attempt history across the class, and a message thread with each parent.

**For parents** — their children's progress and results, a STEM radar chart, and
the same message thread from the other side.

**Under the hood** — five independent levels per child (science, technology,
engineering, math, and a separate story level), each moving as the child
completes work. A scikit-learn model predicts a starting level at registration
from demographic features, falling back to beginner when the model is
unavailable.

## Run it with Docker

The whole stack -- gateway, web, api and Postgres -- in one command. Copy
`.env.example` to `.env` first and set `POSTGRES_PASSWORD`, `SECRET_KEY`,
`API_TOKEN_SECRET` and `WEB_SECRET_KEY`; compose refuses to start without them
rather than defaulting to something guessable.

```bash
docker compose up -d --build
```

Then create the schema and seed it:

```bash
docker compose exec api flask --app app:create_app db upgrade
docker compose exec api flask --app app:create_app seed --password demo1234
```

Open http://localhost:8080. The gateway is the only published port: `web` and
`api` are reachable only from inside the compose network.

```bash
docker compose ps          # all four should read healthy
docker compose logs -f api
docker compose down        # add -v to drop the database and uploaded images
```

## Quickstart

Prefer to run it directly, without Docker? Requires **Python 3.10+**
(developed on 3.12). No database server needed — it falls back to a local SQLite
file. You will need two terminals, one per service.

```bash
git clone https://github.com/naughlan-creator/kai-konane-2.git
cd kai-konane-2
python -m venv venv
```

Activate it — `venv\Scripts\activate` on Windows, `source venv/bin/activate`
elsewhere — then:

```bash
pip install -r services/api/requirements.txt
```

Copy the example environment file and set a secret key:

```bash
cp .env.example .env
```

Everything in `.env` is optional in development; leaving `SECRET_KEY` blank just
means a new one per run, so you get logged out on restart. Then, from
`services/api`:

```bash
cd services/api && flask --app app:create_app seed --password demo1234
```

That creates the admin, a demo teacher, a demo parent, two children, and 12
activities and 7 stories spread across the levels. It is safe to run more than
once — anything already present is left alone, and existing passwords are never
changed.

```bash
flask --app app:create_app check
```

`check` walks the relationship graph the app depends on and reports anything
that would render an empty page or crash at runtime — a child with no learning
plan, an activity with no questions, a question with no correct answer. Run it
after any change to seed data.

```bash
flask --app app:create_app run
```

Then open http://127.0.0.1:5000.

### Demo accounts

All use the password you passed to `seed` (`demo1234` above; omit `--password`
and one is generated and printed once).

| Username | Role | Sees |
|---|---|---|
| `teacher` | Teacher | Both children, their plans and progress |
| `parent` | Parent | Both children, progress, results, messages |
| `child` | Child (age 5) | Activities and stories at their level |
| `child2` | Child (age 6) | A different level to `child` |
| `admin` | Admin | User management, activity and story authoring |

The admin password comes from `ADMIN_PASSWORD` in `.env`; leave it blank and
`seed` generates one and prints it once.

## Tests

```bash
pip install -r services/api/requirements-dev.txt
cd services/api && python -m pytest      # 140 tests
cd services/web && python -m pytest      # 128 tests
```

By default the api suite runs against a throwaway SQLite file, so a fresh clone
needs no database server. Point it at Postgres — the engine production uses — to
run it the way CI does:

```bash
docker run -d --name kai-pg -e POSTGRES_PASSWORD=testpw -e POSTGRES_USER=kai   -e POSTGRES_DB=kai_test -p 55432:5432 postgres:16-alpine
TEST_DATABASE_URL=postgresql://kai:testpw@127.0.0.1:55432/kai_test python -m pytest
```

SQLite is forgiving about things Postgres is not — type coercion, enum handling,
transactional DDL — so a green SQLite run is evidence, not proof.

Coverage sits at 80% of `services/api/app`:

```bash
python -m pytest --cov=app --cov-report=term-missing
```

web's suite runs with the api **stubbed out entirely** — no database, no
network, no second process. A service that needs the rest of the stack in order
to be tested is not really separate, so that constraint is deliberate.

The API tests assert on the **contract** — the keys and types a client will
depend on — not just on status codes. A response that returns the right status
with the wrong shape is the failure mode that costs a day during the service
split, so `test_api_content.py` and `test_api_domain.py` check payload shape,
embed depth, and the invariants that matter: that a password hash never appears
in a user payload under any key, that a rejected family registration writes
nothing at all, and that timestamps carry an explicit UTC offset.

## Layout

```
docs/architecture.md     design rules, the full API contract, migration notes
compose.yaml             the whole stack: gateway, web, api, db
gateway/                 nginx — the single public entrypoint
services/api/            the domain and the database, JSON only
  app/
    api/                 endpoints, serializers, authz
    models/              SQLAlchemy models — the only ORM in the repo
    services/            domain logic — the only place that writes
    seeds/               idempotent seed data
    cli.py               seed, check, create-admin, import-content
services/web/            the UI — templates, sessions, forms
  app/
    api_client.py        the only place web makes an HTTP call
    identity.py          SessionUser, rebuilt from JSON not the ORM
    routes/              eleven HTML blueprints
```

The rule that shapes the code: **routes never touch the database.** A route
parses the request, calls one service method, and renders. Every write goes
through `app/services/`, which is what made extracting a JSON API on top of the
same logic possible without duplicating it.

## Architecture

Four services behind a single public entrypoint:

| Service | Responsibility |
|---|---|
| `gateway` | nginx. Routes `/api/*` to api, everything else to web |
| `web` | UI only — templates, sessions, forms. No ORM |
| `api` | The domain. Sole owner of the database and migrations |
| `db` | PostgreSQL 16 |

`web` imports no ORM and opens no database connection — every read and write is
an HTTP call to `api`, which owns the schema and all migrations. The acceptance
test for that boundary is a grep that returns nothing:

```bash
grep -rn "sqlalchemy\|from app.models" services/web/
```

[docs/architecture.md](docs/architecture.md) carries the honest build status,
the ~45-endpoint contract with the embed depth of each response, and the four
serialization rules that exist because a template breaks silently without them.

## Known gaps

Recorded rather than hidden:

- `GET /api/activities/{id}` includes `answers[].is_correct`, because the
  activity page uses it to play the right sound. Scoring is server-side, so a
  child cannot forge a score, but anyone reading the payload can see the
  answers. Fixing it properly means checking answers one at a time server-side.
- **The api image is 799 MB**, of which ~440 MB is scikit-learn and its
  dependencies — needed only to unpickle a saved model. Exporting it to ONNX
  would cut the image to roughly 250 MB.
- The gateway serves plain HTTP. TLS terminates there when this is deployed.

## License

MIT — see [LICENSE](LICENSE).
