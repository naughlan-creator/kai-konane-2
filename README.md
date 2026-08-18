# Kai Konane

A STEM learning platform for preschoolers, with separate experiences for
children, parents and teachers. Children work through illustrated activities and
stories; a per-child learning plan decides what they are shown; teachers and
parents follow progress and message each other about a specific learner.

Built as a Flask monolith, now being decomposed into services. See
[docs/architecture.md](docs/architecture.md) for the design and the full API
contract.

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

## Quickstart

Requires **Python 3.10+** (developed on 3.12). No database server needed — it
falls back to a local SQLite file.

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
cd services/api && python -m pytest
```

304 tests. They run against a temporary SQLite database seeded once per session,
so no setup is required and nothing touches your development data.

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
services/api/            the service that owns the domain and the database
  app/
    api/                 JSON endpoints and serializers
    models/              SQLAlchemy models
    routes/              HTML routes (moving to services/web)
    services/            domain logic — the only place that writes
    seeds/               idempotent seed data
    cli.py               seed, check, create-admin, import-content
  tests/
gateway/                 nginx config for the service split
```

The rule that shapes the code: **routes never touch the database.** A route
parses the request, calls one service method, and renders. Every write goes
through `app/services/`, which is what made extracting a JSON API on top of the
same logic possible without duplicating it.

## Architecture

Mid-decomposition from a monolith into four services:

| Service | Responsibility |
|---|---|
| `gateway` | nginx. Routes `/api/*` to api, everything else to web |
| `web` | UI only — templates, sessions, forms. No ORM |
| `api` | The domain. Sole owner of the database and migrations |
| `db` | PostgreSQL 16 |

Today `api` holds the domain, the database and the full JSON API, and still
serves the HTML routes. `web` does not exist yet as a separate service — the
presentation layer moves there next, at which point it will talk to `api` over
HTTP and hold no database access at all.

[docs/architecture.md](docs/architecture.md) carries the honest build status,
the ~45-endpoint contract with the embed depth of each response, and the four
serialization rules that exist because a template breaks silently without them.

## Known gaps

Recorded rather than hidden:

- **Authentication between services is a documented no-op.** `token_required`
  marks every endpoint that will need a token, so switching it on is a one-file
  change. It must be real before the gateway is exposed.
- `GET /api/activities/{id}` includes `answers[].is_correct`, because the
  activity page uses it to play the right sound. Scoring is server-side, so a
  child cannot forge a score, but anyone reading the payload can see the
  answers.
- `Procfile` still names a module layout that predates the service split.
  Deployment configuration is rebuilt with the containers.

## License

MIT — see [LICENSE](LICENSE).
