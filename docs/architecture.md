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
| JSON endpoints — auth, users, plans, progress, feedback, preschools | in progress (#7) |
| Bearer-token auth between `web` and `api` | planned (#8) |
| `services/web` calling `api` over HTTP | planned (#9) |
| `gateway`, Dockerfiles, compose | planned (#10) |

Until #9 lands, `api` also serves the HTML routes and owns `templates/` and
`static/`. That is deliberate: `services/web` cannot import `services/api`'s
models across the directory boundary, so splitting them before the HTTP layer
exists would leave the app broken for the whole middle of the branch. The
presentation assets move to `services/web` as part of #9.

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
    │   │   ├── routes/         blueprints (HTML today, JSON from #7)
    │   │   ├── seeds/          idempotent seed data
    │   │   ├── cli.py          flask seed / check / init-db
    │   │   ├── level_predictor.py
    │   │   └── utils.py
    │   ├── templates/          moves to services/web in #9
    │   ├── static/             moves to services/web in #9
    │   ├── migrations/         alembic — owned by api alone
    │   ├── tests/
    │   ├── ml_model.py         trains level_prediction_model.joblib
    │   └── requirements.txt
    └── web/                    UI service                        (#9)
```

Two placement rules worth stating, because both caused failures during #6:

- **`templates/` and `static/` sit beside the package, not inside it.** They
  belong to `web` and are only lodging with `api` until #9, so the factory
  passes both paths to `Flask()` explicitly. Without that, Flask looks under
  `app/` and every `render_template` fails.
- **`config.basedir` is the *service* directory** (`services/api`), not the
  package directory. `services/media.py` derives the upload path from it and
  `level_predictor.py` finds the `.joblib` through it.

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

### Authentication is a seam, not yet a wall

`app/api/auth_seam.py` defines `@token_required`, currently a **no-op**. It
marks every endpoint the contract lists as `Token` so #8 becomes a one-file
change rather than an audit. This is safe only because nothing routes to
`/api/*` from outside until the gateway arrives in #10, and #8 lands first.

> **#8 must replace the body of `token_required` before #10 merges.** An
> unauthenticated `/api/*` behind a public gateway is a writable database.

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
| GET | `/users` | List all users | Admin | — | `admin.view_user_data` |
| PATCH | `/users/{id}` | Update username/email/password/role | Token | — | `admin.edit_user`, `profile.update_profile` |
| DELETE | `/users/{id}` | Delete a user | Admin | — | `admin.delete_user` |
| GET | `/parents/{id}/children` | A parent's children | Token | learning_plan | `user.view_children`, `profile.profile` |
| GET | `/teachers/{id}/students` | A teacher's learners | Token | learning_plan | `user.view_learners`, `learning_plan.manage_learning_plans` |
| PATCH | `/children/{id}` | Update a child's profile | Token | — | `profile.update_child_profile` |

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