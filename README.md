# Kai Konane

[![CI](https://github.com/naughlan-creator/kai-konane-2/actions/workflows/ci.yml/badge.svg)](https://github.com/naughlan-creator/kai-konane-2/actions/workflows/ci.yml)

A STEM learning platform for preschoolers, with separate experiences for
children, parents and teachers. Children work through illustrated activities and
stories; a per-child learning plan decides what they are shown; teachers and
parents follow progress and message each other about a specific learner.

![A child opening an activity and answering a question](docs/img/Kai-Konane-Child-Walkthrough.gif)

Built as a Flask monolith, then decomposed into four services behind an nginx
gateway and deployed to Azure Container Apps. **The deployment has since been
torn down** — it was running on trial credit, and leaving it up would cost around
£25/month to prove a point the screenshots already make. `docker compose up -d
--build` reproduces the whole stack locally in one command.

See [docs/architecture.md](docs/architecture.md) for the design and the full API
contract, and [docs/adr/](docs/adr/) for the decisions that were expensive to
reverse.

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
cd services/api && python -m pytest      # 159 tests
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

## Continuous integration

`.github/workflows/ci.yml` runs nine jobs on every pull request, in about two
and a half minutes.

| job | what it proves |
|---|---|
| `ruff` | lint, at the version pinned in `requirements-dev.txt` |
| `api tests (Postgres)` | 159 tests against a real Postgres service container |
| `web tests` | 128 tests, api stubbed |
| `terraform` | `fmt -check`, `init -backend=false`, `validate` |
| `helm` | lint and render, default and production values, plus one **negative** test |
| `manifests and alert rules` | `promtool check rules`, `kubeconform` |
| `image (api/web/gateway)` | all three Dockerfiles still build |

Six run in parallel; the three image builds are gated behind all six, because
there is no point building an image for code that does not lint, does not pass,
or renders a chart that will not apply.

### There is a second CI system, and that is the point

`azure-pipelines.yml` is kept, not dead. It is a complete three-stage pipeline —
lint, tests on Postgres, tag-gated publish to GHCR — and it works. It has one
structural problem:

```yaml
pool:
  name: nolan-agent-pool
```

A self-hosted agent. It runs when that machine is on, and its results live in
Azure DevOps rather than on the pull request. CI that requires a laptop to be
powered up is a build script with a scheduler attached — and the cost was
concrete: a test broken by the observability work went a full day unnoticed,
because nothing ran on the PR that broke it.

Linux runners also removed a category of workaround the Azure file still
carries: a manual `docker run` for Postgres, a `for /l` polling loop, and a
PowerShell step written because `script:` runs `cmd.exe`, which has no `sed`.
All three exist only because the agent is Windows.

### Validation the pipeline never had

Terraform, Helm and the Prometheus rules used to be checked by running commands
and remembering to. Three of these jobs check them on every PR instead.

The **negative** test in the `helm` job is the one worth singling out:

```yaml
      - name: the ai.apiKey guard must fire
        run: |
          if helm template kai-konane $CHART \
               --set ai.provider=azure \
               --set ai.endpoint=https://example.openai.azure.com \
               > /dev/null 2>&1; then
            echo "::error::the required guard is gone"
            exit 1
          fi
```

Every other step asserts that something works. This one asserts that something
**fails**. A `required` guard nobody has watched fire is a guess, and the two
guards confirmed by hand during the AI work stay confirmed only if something
keeps checking.

`promtool check rules` is the other addition with teeth. The alert rules live
inside a ConfigMap, so it lifts `alerts.yml` out of `.data` before checking it.
YAML parsing proves nothing about PromQL — Prometheus decides that at load time,
and when it rejects a rule file it logs the failure, **keeps the previously
loaded rules**, and carries on serving. The UI looks healthy either way.

### What it does not prove

`terraform validate` checks syntax, types and references without talking to
Azure. It would catch a reference to a resource that does not exist. It cannot
catch what actually broke the first `terraform apply`: an alert rule whose
query Azure rejected with a 400 at create time. That class of error needs a
`plan` against a real subscription, which needs credentials in CI, which is an
OIDC federation exercise this repository has not done. The green tick is
honest about its own boundary.

`deploy/k8s/01-secret.yaml` is gitignored, so CI validates eleven manifests
where a deployment applies twelve.

### The gate

`.github/ruleset-main.json` is branch protection as a versioned file, applied
with:

```bash
gh api --method PUT repos/naughlan-creator/kai-konane-2/rulesets/<id> \
  --input .github/ruleset-main.json
```

Protection configured by clicking is a setting nobody can review, diff or
restore. As a file it goes through the same pull request as the code it
protects.

It requires a pull request (with zero approvals — one contributor, so requiring
an approval you would give yourself is theatre), all nine checks, and
`strict_required_status_checks_policy: true`, which means a branch must be up to
date with `main` before it merges. That last one is the friction-bearing choice
and it is deliberate: green-on-my-branch is not green-after-merge, and the
regression described above passed on its own branch and broke `main`.

`bypass_actors` is empty. That includes the repository owner.

### Two things that cost real time

**1. The Actions cache scope defaults to the job name.** Matrix jobs are named
after every matrix value, so the check `images (api, services/api)` would have
broken the moment anyone renamed a build context. Fixing that with an explicit
`name: image (${{ matrix.name }})` also, silently, moved the cache — the default
scope had changed with the name.

The fix is to key the cache on what it caches:

```yaml
cache-from: type=gha,scope=${{ matrix.name }}
```

Note also what the default did *before* the rename: all three matrix legs shared
the job name `images`, so all three wrote to one cache scope concurrently,
overwriting each other.

**2. `mode=max` exports the builder stage too.** That is what it is for, and for
most images it is right. The api image is 827MB of numpy, scipy, pandas and
scikit-learn, and the export was measured at:

```
#22 exporting to GitHub Actions Cache
#22 writing layer sha256:60f9ff3f... 784.6s done
#22 DONE 913.0s
```

Fifteen minutes of cache export to save a **137-second** cold build. With a 10GB
per-repository cache limit and three images, `mode=max` would also have evicted
itself into permanent misses. `mode=min` brought the same step to 35.7s and the
job from 15m51s to 1m37s.

The general shape: a cache is only worth what it saves, and neither number is
knowable without measuring. The comment in the workflow records the measurement,
not just the conclusion.

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

[docs/adr/](docs/adr/) records the decisions that were expensive to reverse: the
service split, single database ownership, and tag-driven image publishing.

[docs/architecture.md](docs/architecture.md) carries the honest build status,
the ~45-endpoint contract with the embed depth of each response, and the four
serialization rules that exist because a template breaks silently without them.

## It was deployed, and here is the evidence

Four services on Azure Container Apps: the nginx gateway with external ingress,
`web` and `api` internal-only, and a Postgres Flexible Server. Secrets in Key
Vault, read at runtime by a user-assigned managed identity — no password in a
command, a YAML file, or `az containerapp show`.

| | |
|---|---|
| ![Container Apps](docs/img/aca-overview.png) | Three apps, one external ingress |
| ![Key Vault](docs/img/key-vault.png) | Secrets by name, never by value |
| ![Managed identity](docs/img/managed-identity.png) | Key Vault Secrets User, read-only |
| ![Pipeline](docs/img/pipeline-stages.png) | Lint → tests on Postgres → build → publish |
| ![Tests](docs/img/pipeline-tests.png) | 287 tests, both suites |
| ![Uptime](docs/img/uptime.png) | UptimeRobot on the gateway's health endpoint |

### One request, traced across both services

`web` mints a request id, forwards it as `X-Request-ID`, and `api` reuses it
rather than minting its own. One page view is therefore one id across every log
line:

![Log Analytics showing one request id across web and api](docs/img/log-analytics.png)

```
18:03:57.441  api  /api/users/4                200    8.3ms
18:03:57.441  api  /api/activities/10/submit     —      —     level prediction
18:03:57.441  api  /api/activities/10          200   15.5ms
18:03:57.441  api  /api/activities/10/submit   201  126.4ms
18:03:57.799  web  /activity/10/submit         302  178.9ms
```

A child submitting an activity: one form post to `web`, three api calls
underneath it, one shared id. `web`'s line comes **last** because it completes
last — its 179ms visibly contains the api work that ran inside it.

The row with no status is a line logged *during* the request rather than at the
end of it: the scikit-learn level prediction, which only has a request id and a
path because status and duration belong to the response.

That query is only possible because the logs are JSON objects rather than
sentences. `"Updated level for child 4"` is readable and unqueryable; the same
content as fields is both.

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
