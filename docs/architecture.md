# Architecture of Kai Konane
## Structure
|   Service    | Responsibilities    |   Tech |   Talks to   |
|---|---|---|---|
| `gateway` | Reverse proxy and single public entrypoint. Routes `/api/*` to api, everything else to web. TLS in production. | nginx 1.27 (alpine) | web, api |
| `web` | UI only: templates, sessions, forms. Holds zero business logic and imports no ORM — every read and write goes to api over HTTP. | Flask + gunicorn | api |
| `api` | The domain: auth, activities, stories, learning plans, progress, results, rewards, feedback, preschools. Sole owner of the database and all migrations. | Flask + SQLAlchemy + gunicorn | db |
| `db` | Persistence | PostgreSQL 16 (alpine) | — |

## Build status

The split is being done in stages so the app stays runnable at every commit.
This table is the honest picture of what exists today.

| Piece | State |
|---|---|
| `services/api` package, `create_app()` factory | **built** (#6) |
| `/healthz`, `/readyz` | **built** (#6) |
| JSON serializers implementing the four rules | **built** (#7) |
| JSON content endpoints — activities, stories | **built** (#7) |
| JSON endpoints — auth, users, plans, progress, feedback, preschools | **built** (#7) |
| Contract tests over every endpoint (`test_api_content.py`, `test_api_domain.py`) | **built** (#7) |
| Rewards over JSON | deferred — write-only for now, see below |
| Bearer-token auth between `web` and `api` | **built** (#8) |
| `services/web` calling `api` over HTTP | **built** (#9) |
| Per-object authorisation in the api (`app/api/authz.py`) | **built** (#9) |
| `gateway`, Dockerfiles, compose | **built** (#10) |

The split is complete. `api` serves JSON and nothing else -- no templates, no
sessions, no Flask-Login. `web` renders HTML and holds no ORM. A test in each
service asserts the boundary rather than trusting it: `test_the_api_serves_no_html`
checks that the only non-`/api` routes are `/healthz` and `/readyz`, and web's
suite runs with the api stubbed out entirely, which it could not do if it
reached into the database.

## Repository layout

```
kai-konane/
├── docs/                       architecture, ADRs, images
├── gateway/                    nginx config + Dockerfile        (#10)
└── services/
    ├── api/
    │   ├── app/                the importable package
    │   │   ├── __init__.py     create_app() factory
    │   │   ├── config.py       settings + unbound extensions
    │   │   ├── models/         SQLAlchemy models — the only ORM in the repo
    │   │   ├── services/       domain logic
    │   │   ├── api/            the JSON endpoints, serializers and authz
    │   │   ├── routes/         health only -- the HTML blueprints left in #9
    │   │   ├── seeds/          idempotent seed data
    │   │   ├── cli.py          flask seed / check / init-db
    │   │   ├── level_predictor.py
    │   │   └── utils.py
    │   ├── static/images/      content images authors upload (api owns these)
    │   ├── migrations/         alembic — owned by api alone
    │   ├── tests/
    │   ├── ml_model.py         trains level_prediction_model.joblib
    │   └── requirements.txt
    └── web/
        ├── app/
        │   ├── api_client.py   the only place web makes an HTTP call
        │   ├── identity.py     SessionUser + the user_loader
        │   ├── roles.py        web's own Role enum
        │   ├── filters.py      |datetime and content_image()
        │   └── routes/         the eleven HTML blueprints
        ├── templates/
        ├── static/             web's own css, js, logo -- not content images
        ├── tests/              runs with the api stubbed out
        └── requirements.txt    four packages, no ORM
```

Two placement rules worth stating, because both caused failures during #6:

- **`static/` sits beside the package, not inside it**, so the factory passes
  the path to `Flask()` explicitly. Without that, Flask looks under `app/`.
- **`config.basedir` is the *service* directory** (`services/api`), not the
  package directory. `services/media.py` derives the upload path from it and
  `level_predictor.py` finds the `.joblib` through it.

### Content images belong to the api

Authors upload cover pictures and story pages through the api, which stores them
beside itself and serves them at `GET /api/media/<filename>`. `web`'s templates
call `content_image(filename)` rather than `url_for('static', ...)`.

That distinction matters more than it looks. Both services shipped a copy of the
same 69 images during the transition, so pointing at web's `/static` appeared to
work — and would have kept appearing to work until the first image uploaded
after the split, which would exist only beside the api and 404 in web. A broken
image is not an error any test catches. web's `static/` now holds its own assets
only: css, js and the logo.

The media endpoint is deliberately unauthenticated: a browser fetching
`<img src>` sends no Authorization header, so requiring a token there would blank
every cover on the site.

## Design rules

**Only `api` opens a database connection.** The acceptance test is a grep that
returns nothing:

```bash
grep -rn "sqlalchemy\|from models" services/web/
```

### Application factory

`api` is built by `create_app(overrides=None)` rather than a module-level app
object. Three consequences that are easy to get wrong:

- **Extensions are created unbound** in `config.py` (`db = SQLAlchemy()`,
  `migrate`, `login_manager`) and attached inside the factory with
  `init_app(app)`. Binding them at import time is what makes a factory
  impossible.
- **Blueprints are imported inside the factory**, never at module scope.
  `routes` imports `models`, `models` imports `config`; a top-level chain
  closes that loop and raises on startup.
- **CLI commands are plain `@click.command` + `@with_appcontext`**, registered
  by `register_cli(app)`. `@app.cli.command` needs a concrete app and cannot
  survive a factory.

`overrides` is how tests inject `TESTING` and a throwaway database URI without
touching the environment.

### Serialization

`web` renders templates from JSON, not from ORM objects. Four rules make that survivable, each one derived from a template that breaks silently without it.

| Type | Wire format | Why |
|---|---|---|
| Datetime | ISO 8601 string | JSON has no datetime. `web` registers one `\|datetime` Jinja filter; five `.strftime()` call sites depend on it. |
| Enum | `{"name": "BEGINNER", "value": "BEGINNER", "rank": 0}` | ~20 templates read `.name` or `.value`; `rank` carries sort order that `.value` cannot (alphabetically ADVANCED sorts before BEGINNER). |
| Relations | Embedded per the Embeds column, never id-only | Templates traverse two levels: `result.activity.stem_code`, `progress.learning_content.type`. |
| Money/score | Plain number | No formatting decisions in the api. |

**Enum comparison rule.** In Jinja, a Python enum compared to a dict is always
`False` and raises nothing — the dropdown simply stops preselecting. Every
identity comparison compares `.name` to `.name`:

```jinja
{% if level.name == user.education_level.name %}selected{% endif %}
```


### Authentication

1. `web` serves `GET/POST /users/login` as an HTML form. It never sees a password hash.
2. It posts credentials to `POST /auth/login`. `api` verifies and returns the user payload plus a signed token (`itsdangerous`).
3. `web` stores the user id and token in its Flask session cookie.
4. `web`'s `user_loader` calls `GET /users/{id}` with the token and builds a `SessionUser(UserMixin)` — not an ORM object. The result is cached in `flask.g` so it fires once per request, not once per `current_user` reference.
5. `web` defines its own four-member `Role` enum. Duplicating a protocol constant across a service boundary is correct; sharing a code module would not be.
6. Every endpoint marked **Token** requires `Authorization: Bearer`. The gateway exposes `/api/*` publicly, so network-level trust is not sufficient.

**Known consequence:** one internal hop per request to rehydrate the session user. Redis-backed sessions would remove it — see the roadmap.

## API contract

`api` serves all of these under `/api/*` via the gateway. **Auth** = requires a
`Authorization: Bearer` token. **Embeds** = related objects that must be nested
in the response, derived from the deepest attribute chain in the consuming
template.

### The `/api` prefix is not stripped

The api mounts its JSON blueprint at `/api` **internally**, and the gateway
forwards without stripping the prefix:

```nginx
location /api/ {
  proxy_pass http://api:5000;   # no trailing slash -- keeps /api
}
```

A trailing slash on `proxy_pass` would strip it, so the api would receive
`/activities`. That is unusable during the transition, because the HTML routes
still own `/activities` and `/stories` until #9 and the two would collide. It is
also simply easier to reason about: a path is identical whether you curl the api
directly or go through the gateway.

### Error shape

Every error is `{"error": "<message safe to show a user>"}` with the status
carried by the `ServiceError` subclass — `ValidationError` 400, `NotFound` 404,
`Conflict` 409. Routes raise; a blueprint error handler converts. No route needs
a try/except.

Routing failures (404, 405) are handled **app-wide** with a path check, not on
the blueprint. URL matching happens before Flask knows which blueprint owns a
path, so `@api_bp.errorhandler(404)` never fires for an unmatched `/api` path
and the client would get Flask's HTML error page.

### Tokens

`app/api/auth_seam.py` holds the whole of it: `issue_token`, `read_token` and
the `@token_required` decorator. Every endpoint the contract marks **Token**
carries the decorator, and a missing one is caught by the parametrised list in
`tests/test_api_auth.py`.

**Signed, not encrypted.** The token is an `itsdangerous` payload carrying
`{uid, role}`. The signature proves the api issued it and that nobody edited it;
it does **not** hide the contents, which are trivially readable by anyone
holding the token. Nothing may go in the claims that the bearer should not see.

**Not a JWT.** A JWT would add a dependency and a header of algorithm
negotiation to solve a problem this system does not have: there is one issuer,
one verifier and a shared secret. `itsdangerous` is already a Flask dependency,
and the part that matters — `max_age` enforced at load time, so an old token
cannot be replayed — is built in.

**`API_TOKEN_SECRET` is separate from `SECRET_KEY`.** `SECRET_KEY` signs `web`'s
session cookie; `API_TOKEN_SECRET` signs api tokens. Different trust boundaries,
so rotating one must not force rotating the other, and a leak of the cookie key
must not let anyone mint api tokens. Only `api` ever holds it — `web` replays a
token it was given and never signs one. Both are required in production; in
development the token secret falls back to `SECRET_KEY`.

Signatures are also salted (`kai-konane-api-token`), so a token minted for some
other purpose under the same secret cannot be replayed against the api.

**Tokens expire after `API_TOKEN_TTL_S`** (default 12 hours). `web` must treat a
401 as *log in again*, never as *retry* — an expired token plus a retry loop is
an infinite loop.

**What this is not.** `token_required` proves *who is calling*, not *what they
may touch*. That second question is answered by `app/api/authz.py` — see below.

### Authorisation

`token_required` establishes identity; `app/api/authz.py` decides what that
identity may touch. Both are needed, and having only the first is what made the
following possible before #9:

```
PARENT token (uid 3) → PATCH /api/users/1 {"password": "..."} → 200
                     → log in as admin with that password     → succeeds
```

Any signed-in user could rewrite any account, read any family's progress, and
rewrite the whole content library. Every endpoint was authenticated; none was
authorised.

Two rules the module is built on:

**Deny by default.** An unrecognised role gets nothing. The check this replaced
compared `role.name` to a lowercase string, never matched, and so allowed
everyone — a check that fails open is worse than no check at all, because it
reads like protection.

**Identity comes from the token, never the request.** `?parent_id=3` is a claim
by the caller; `g.current_user_id` is a claim the api signed. Only the second is
evidence. Scoping filters against the query string rather than the token is what
turns a listing endpoint into a data leak.

| Rule | Applies to |
|---|---|
| Admin only | `GET /users`, `DELETE /users/{id}`, all content authoring, media upload, preschool writes |
| Self or admin | `PATCH /users/{id}`, `PATCH /parents/{id}`, `PATCH /teachers/{id}` |
| Own learner | anything naming a `child_id` — progress, results, plans, stem-levels, submissions |
| Own mail | feedback listing, reading, and sending as yourself |
| Correspondent | `GET /users/{id}` for someone you share a learner with |

`tests/test_api_authz.py` covers these from the attacker's side — every test
describes something that worked before the module existed — plus two that assert
the checks are not blanket, because the failure mode of a security patch is
locking out the people it was meant to protect.

### Unauthenticated by necessity

Four endpoints stay open, and have to be:

| Endpoint | Why |
|---|---|
| `POST /auth/login` | Issues the token; requiring one is circular |
| `GET /users/availability` | The signup wizard runs before an account exists |
| `POST /parents`, `POST /teachers` | Registration — same reason |
| `GET /preschools` | The wizard offers a preschool at step 3 |

These are the only unauthenticated writes in the api. The exposure is the same
as any public signup form, but it is a deliberate decision rather than an
oversight, so it is recorded here.

### Exposed answer keys

`GET /api/activities/{id}` includes `answers[].is_correct`, because
`activity_page.html` uses it to play the right sound on selection. Scoring is
server-side, so this does not let a child forge a score — but it does let anyone
reading the payload see the answers. Fixing it properly means checking answers
one at a time server-side. Recorded here rather than fixed; it predates the
split.

### Auth and registration

| Method | Path | Purpose | Auth | Embeds | Called by (web) |
|---|---|---|---|---|---|
| POST | `/auth/login` | Verify credentials, issue token | — | role, type, profile fields | `user.login` |
| GET | `/users/availability` | Is this username/email free? | — | — | `user.parent_signup_2`, `user.teacher_signup_2` |
| POST | `/parents` | Create parent + N children + N plans, one transaction | — | children[] | `user.parent_signup_4` |
| POST | `/teachers` | Create teacher | — | — | `user.teacher_signup_3` |

### Users

| Method | Path | Purpose | Auth | Embeds | Called by (web) |
|---|---|---|---|---|---|
| GET | `/users/{id}` | Rehydrate the session user | Token | role, children[] or students[] | `user.load_user` |
| GET | `/users` | List all users (account fields only) | Admin | — | `admin.view_user_data` |
| PATCH | `/users/{id}` | Update username, email or password | Token | — | `admin.edit_user`, `profile.update_profile` |
| DELETE | `/users/{id}` | Delete a user | Admin | — | `admin.delete_user` |
| GET | `/parents/{id}/children` | A parent's children | Token | profile fields | `user.view_children`, `profile.profile` |
| PATCH | `/parents/{id}` | Update a parent's profile | Token | — | `profile.update_profile` |
| GET | `/teachers` | List teachers, to pick one per child at signup | Token | — | `user.parent_signup_3` |
| GET | `/teachers/{id}/students` | A teacher's learners | Token | profile fields | `user.view_learners`, `learning_plan.manage_learning_plans` |
| PATCH | `/teachers/{id}` | Update a teacher's profile | Token | — | `profile.update_profile` |
| GET | `/children` | List, filtered by `?parent_id=` or `?teacher_id=` | Token | profile fields | `user.view_children`, `user.view_learners` |
| GET | `/children/{id}` | One child | Token | profile fields | `profile.child_profile` |
| PATCH | `/children/{id}` | Update a child's profile | Token | — | `profile.update_child_profile` |

A child's learning plan is **not** embedded in these payloads even though several
templates show a plan next to a name. Embedding it would make every list view
carry five enums per child that most callers ignore, and a plan changes on a
different schedule to a profile. `GET /learning-plans/child/{id}` is a separate
call for that reason.

### Preschools

| Method | Path | Purpose | Auth | Embeds | Called by (web) |
|---|---|---|---|---|---|
| GET | `/preschools` | List (also used during signup) | — | — | `user.parent_signup_3`, `user.teacher_signup_1`, `preschool.view_preschools` |
| POST | `/preschools` | Create | Admin | — | `preschool.add_preschool` |
| GET | `/preschools/{id}` | Detail | Admin | students[], teachers[] | `preschool.view_preschool` |
| PATCH | `/preschools/{id}` | Rename | Admin | — | `preschool.edit_preschool` |
| DELETE | `/preschools/{id}` | Delete (rejects if occupied) | Admin | — | `preschool.delete_preschool` |

### Activities

| Method | Path | Purpose | Auth | Embeds | Called by (web) |
|---|---|---|---|---|---|
| GET | `/activities?child_id=` | List, filtered by the child's per-strand levels | Token | level, stem_code, progress | `activity.activity_home` |
| GET | `/activities/{id}` | Detail | Token | questions[].answers[] | `activity.activity_detail`, `activity.start_activity`, `admin.update_activity` |
| POST | `/activities` | Create | Admin | — | `admin.add_activity` |
| PATCH | `/activities/{id}` | Update, syncing questions and answers | Admin | questions[].answers[] | `admin.update_activity` |
| DELETE | `/activities/{id}` | Delete (cascades) | Admin | — | `admin.delete_activity` |
| POST | `/activities/{id}/submit` | Mark attempt, log result, nudge the plan | Token | — | `activity.submit_activity` |
| POST | `/activities/{id}/progress` | Save partial progress | Token | — | `activity.save_progress` |

### Stories

| Method | Path | Purpose | Auth | Embeds | Called by (web) |
|---|---|---|---|---|---|
| GET | `/stories?child_id=` | List, filtered by story level | Token | level, progress | `story.stories` |
| GET | `/stories/{id}` | Detail | Token | pages[] | `story.story_detail`, `admin.update_story` |
| POST | `/stories` | Create | Admin | — | `admin.add_story` |
| PATCH | `/stories/{id}` | Update, syncing and renumbering pages | Admin | pages[] | `admin.update_story` |
| DELETE | `/stories/{id}` | Delete (cascades) | Admin | — | `admin.delete_story` |
| POST | `/stories/{id}/progress` | Save page position | Token | — | `story.save_progress` |
| POST | `/stories/{id}/complete` | Mark complete, issue reward once | Token | — | `story.complete_story` |

### Learning plans

| Method | Path | Purpose | Auth | Embeds | Called by (web) |
|---|---|---|---|---|---|
| GET | `/learning-plans/child/{id}` | The plan | Token | 5 level enums | `learning_plan.view_learning_plan` |
| PUT | `/learning-plans/child/{id}` | Create or replace (one per child) | Teacher | — | `learning_plan.create_learning_plan`, `learning_plan.update_learning_plan` |
| GET | `/learning-plans/child/{id}/recommendations` | Content at or below each strand level | Token | level | `learning_plan.view_learning_plan` |

### Progress and results

| Method | Path | Purpose | Auth | Embeds | Called by (web) |
|---|---|---|---|---|---|
| GET | `/children/{id}/progress` | One child's progress | Token | learning_content{title, type} | `progress.parent_progress` |
| GET | `/progress?teacher_id=` | All a teacher's learners | Teacher | + child{firstname, lastname} | `progress.teacher_progress` |
| GET | `/children/{id}/results` | One child's attempts | Token | activity{title, stem_code} | `progress.parent_results` |
| GET | `/results?teacher_id=` | All a teacher's learners | Teacher | + child{firstname, lastname} | `progress.teacher_results` |
| GET | `/children/{id}/stem-levels` | Mean score per STEM strand | Token | — | `static/js/stem_graph.js` |

### Feedback

| Method | Path | Purpose | Auth | Embeds | Called by (web) |
|---|---|---|---|---|---|
| POST | `/feedback` | Send a message | Token | — | `feedback.submit_feedback` |
| GET | `/feedback?recipient_id=&unread=true` | Inbox | Token | sender{firstname, lastname} | `feedback.view_feedback` |
| GET | `/feedback?participant_id=` | Full history, sent and received | Token | sender{firstname, lastname} | `feedback.past_feedback` |
| GET | `/feedback/{id}` | Read one | Token | sender{firstname, lastname} | `feedback.read_feedback` |
| POST | `/feedback/{id}/read` | Mark as read | Token | — | `feedback.read_feedback` |

### Health

| Method | Path | Purpose | Auth | Embeds | Called by |
|---|---|---|---|---|---|
| GET | `/healthz` | Liveness — process is up. Never touches the database, so a slow query cannot look like a dead process and get the container killed. Returns `status`, `version`, `uptime_s`. | — | — | compose healthcheck, UptimeRobot |
| GET | `/readyz` | Readiness — the database answers. `503` when it does not. This is what compose `depends_on` waits for. | — | — | compose healthcheck |

### Registering a family

`POST /parents` is the one endpoint that creates several rows at once. The
four-step wizard lives entirely in `web`: steps 1–3 accumulate session state and
write nothing; step 4 posts the whole aggregate.

```json
POST /parents        →  201 Created
{
  "username": "pania", "email": "p@x.com", "password": "...",
  "firstname": "Pania", "lastname": "Rewi",
  "education_level": "BACHELORS_DEGREE",
  "preschool_id": 1,
  "children": [
    { "firstname": "Ari", "age": 5, "gender": "Female",
      "username": "ari", "password": "...",
      "race_ethnicity": "group B", "lunch_type": "STANDARD",
      "teacher_id": 3 }
  ]
}
```

Either the whole family is created or none of it is. A half-registered family
would leave children with no learning plan, and a child with no plan can see no
content at all — the app would appear to work and show an empty library. Every
child spec is validated before the first `INSERT`, so a bad second child does not
leave the parent and the first child behind.

Uniqueness is checked twice on purpose. `GET /users/availability` is **advisory**
— it exists so a four-screen wizard can fail on screen two instead of screen
four — and `RegistrationService` re-checks inside the transaction and raises
`Conflict` (409). Treating the advisory check as authoritative is a race.

### Rewards stay write-only

Rewards are issued by `POST /stories/{id}/complete` and never read back. There is
no `GET /rewards` in the contract because nothing displays them yet: whether
they surface as badges on the child's home screen is an open product decision. A
read endpoint added now would be a guess at the shape that screen needs, and a
wrong guess in the contract is more expensive than a missing one.

### Failure responses

Every endpoint fails through the same three mappings, so `web` needs one error
path, not thirty:

| Status | Raised by | Example |
|---|---|---|
| 400 | `ValidationError` | `{"error": "teacher_id must be a number"}` |
| 401 | `POST /auth/login` only | `{"error": "Invalid username or password"}` |
| 404 | `NotFound`, or no such route | `{"error": "No such user"}` |
| 409 | `Conflict` | `{"error": "Username 'parent' is already taken"}` |

The 401 message is deliberately identical for an unknown username and a wrong
password. Distinguishing them turns the login form into a username oracle.

## Running it

```bash
docker compose up -d --build
docker compose exec api flask --app app:create_app db upgrade
docker compose exec api flask --app app:create_app seed --password <password>
```

The gateway is the only service that publishes a port (8080). `web` and `api`
are reachable only from inside the compose network, which is what makes the
gateway an entrypoint rather than a convenience.

### Base images differ per service, on purpose

| Service | Base | Size | Why |
|---|---|---|---|
| `api` | `python:3.12-slim` | 799 MB / 193 MB transferred | scipy and scikit-learn ship manylinux wheels. On musl, pip falls back to compiling scipy from source -- twenty minutes, and a *larger* image |
| `web` | `python:3.12-alpine` | 116 MB / 33 MB transferred | Four pure-python dependencies. Nothing to compile, so musl costs nothing and the base is ~120 MB smaller |
| `gateway` | `nginx:1.27-alpine` | ~50 MB | Config file over a stock image |

The rule is not "alpine is smaller". It is **alpine wins when you have no
compiled dependencies and loses when you do** -- two services in one repo,
opposite answers.

The api's 440 MB of scientific stack is not removable: `level_predictor.py`
unpickles a `.joblib` model, and deserialising a scikit-learn Pipeline requires
scikit-learn, which pulls in numpy and scipy. Only `ml_model.py` imports sklearn
by name, so it looks droppable. Exporting the model to ONNX and using
`onnxruntime` (~15 MB) would cut the api to roughly 250 MB -- recorded as a known
tradeoff, not done.

`.dockerignore` lives in each service directory, not the repo root. Docker reads
`<build-context>/.dockerignore`, and the contexts are `services/api` and
`services/web`, so a root file is never consulted. A root one existed briefly and
did nothing -- during which the api image shipped the development database,
including real password hashes. **A file that looks like it is protecting you but
is not is worse than no file.** The per-service files cut the context from 587 MB
to 29 MB.

### Healthchecks say less than they appear to

Every service has one, and dependents wait on `condition: service_healthy` rather
than plain `depends_on` -- which waits for a container to *start*, not to be
usable. Postgres accepts a socket seconds before it will answer a query.

The endpoints differ on purpose:

| Service | Checks | Why |
|---|---|---|
| `db` | `pg_isready -U kai` | Without `-U` the check runs as root, which is not a role in this database, and fails forever |
| `api` | `/readyz` | The api is only useful if the database answers, so readiness includes it |
| `web` | `/healthz` | web has no database and **must stay up when the api is down** -- it renders the error page. Checking the api here would turn one failure into two |
| `gateway` | `wget http://127.0.0.1/healthz` | The literal address, not `localhost`: `listen 80` binds IPv4 only, and `localhost` resolves to `::1` first inside the container |

`start_period` is not a longer interval -- failures inside it do not count toward
`retries`, which is what lets Postgres initialise a fresh data directory without
exhausting them.

**Healthy does not mean working.** During this build three services reported
healthy while `/` returned 404 and `/api/preschools` returned 500: the gateway
was proxying to the wrong upstream and the database had no tables. `/readyz`
checks that Postgres *answers*, not that any table exists. The acceptance test is
therefore a request through the gateway to each service, not `docker compose ps`.

### Uploads need a volume

Content images land in `/app/static/images` inside the api. Containers are
disposable, so without the `media` volume every rebuild silently deletes
everything an author uploaded -- and the pages still render, with broken
pictures.

## Mermaid diagram
```mermaid
flowchart LR
    U[Browser] --> G[gateway<br/>nginx 1.27 :80]
    G -- "/" --> W[web<br/>Flask UI + sessions :5000]
    G -- "/api/*" --> A[api<br/>Flask REST :5000]
    W -- "internal HTTP<br/>Bearer token" --> A
    A --> D[(PostgreSQL 16)]
    A -. "owns schema<br/>+ migrations" .-> D
```
## Web routes
`web` keeps all 70 HTML routes. This table is the completeness check: every
blueprint either calls api endpoints from the contract above, or renders a
static page. A blueprint that needs data with no matching endpoint means the
contract is incomplete.
| Blueprint | Routes | Calls |
|---|---|---|
| `user` | 20 | `POST /auth/login`, `GET /users/availability`, `POST /parents`, `POST /teachers`, `GET /users/{id}`, `GET /preschools`, `GET /teachers/{id}/students` |
| `admin` | 13 | activities and stories CRUD, `GET /users`, `PATCH /users/{id}`, `DELETE /users/{id}` |
| `feedback` | 7 | the five `/feedback` endpoints, `GET /parents/{id}/children` |
| `preschool` | 5 | the five `/preschools` endpoints |
| `activity` | 5 | `GET /activities`, `GET /activities/{id}`, `POST /activities/{id}/submit`, `POST /activities/{id}/progress` |
| `progress` | 5 | the four progress/results endpoints, `GET /children/{id}/stem-levels` |
| `story` | 4 | `GET /stories`, `GET /stories/{id}`, `POST /stories/{id}/progress`, `POST /stories/{id}/complete` |
| `learning_plan` | 4 | the three `/learning-plans` endpoints, `GET /teachers/{id}/students` |
| `profile` | 3 | `PATCH /users/{id}`, `PATCH /children/{id}`, `GET /parents/{id}/children` |
| `learning_content` | 1 | none — static menu page |
| `index` / `healthz` | 2 | none |

## Migration notes

### `/api/child_stem_levels` must move

`web` currently serves `GET /api/child_stem_levels/<child_id>`. Once the gateway
is in front, nginx matches the `/api/` prefix and forwards it to `api`, which
has no such route — the parent and teacher progress charts 404 from a service
that was never touched.

It already returns JSON, so it moves nearly verbatim to
`GET /children/{id}/stem-levels`. `static/js/stem_graph.js` must change with it:

```js
fetch(`/api/children/${childId}/stem-levels`)
```

### Case-sensitive template paths

Container filesystems are case-sensitive; Windows is not. Verify every
`render_template()` string matches the file on disk exactly before building
images. `view_learning_Plan.html` was caught this way — it worked on NTFS and
would have been a `TemplateNotFound` inside the container.

### What broke during #6, and will again during #9

The api move surfaced four failures that `git mv` cannot warn about. #9 moves
`routes/`, `templates/` and `static/` into `services/web`, so expect the same
shapes:

| Symptom | Cause |
|---|---|
| `ImportError: cannot import name 'app'` | Modules bound to a module-level `app` at import time — `login_manager.init_app(app)`, `@app.cli.command`. Both had to move into the factory. |
| Every `render_template` 500s | `Flask(__name__)` looks for `templates/` inside the package. Pass `template_folder` and `static_folder` explicitly. |
| A feature silently degrades | `level_predictor.py` resolved the `.joblib` beside itself. After the move the file was gone, prediction returned `None`, and every child silently fell back to `BEGINNER`. Seeding still reported success — **the exit code was zero**. Path-dependent assets must resolve through `config.basedir`, not `__file__`. |
| `NameError: name 'routes' is not defined` | A sed-based import rewrite turned `import routes` into `import app.routes`, which binds `app`, not `routes`. `from X import Y` rewrites safely; `import X` plus `X.attr` does not. |

The third is the one to watch for. A move that breaks an import fails loudly; a
move that breaks a *path* returns a default and keeps going. After #9, verify
behaviour, not just exit codes.