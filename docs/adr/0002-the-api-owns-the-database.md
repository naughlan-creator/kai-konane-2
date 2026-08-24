# ADR-002: The api owns the database, exclusively

**Status:** Accepted
**Date:** 2026-08-20
**Depends on:** [ADR-001](0001-split-the-monolith-into-services.md)

## Context

Once the services were separate, `web` still needed data. Two ways to give it
any:

**A shared database.** Both services connect to Postgres; each reads what it
needs. Simple, fast, no serialization layer, no HTTP hop.

**A single owner.** Only `api` connects. `web` asks over HTTP.

A shared database is genuinely tempting at this size. It is also how a
distributed monolith is built: two deployables that cannot be changed
independently, because a column rename breaks a service that never mentioned it.
The coupling is invisible in the code and total in practice.

## Decision

`api` is the only service that opens a database connection. It owns the models,
the schema and the alembic migrations. `web` holds no ORM and no connection
string.

The acceptance test is a grep that must return nothing:

```bash
grep -rn "sqlalchemy\|from app.models\|from app.services" services/web/
```

Four serialization rules make JSON a workable substitute for ORM objects in
templates, each derived from something that broke silently without it:

- **Datetimes as ISO 8601 with an explicit offset.** A JSON string has no
  `.strftime`, and Jinja renders a failed attribute as empty rather than
  raising, so five templates would have quietly lost their dates.
- **Enums as `{name, value, rank}`.** Templates read `.name` for logic and
  `.value` for display; `rank` carries the ordering `.value` cannot, because
  alphabetically ADVANCED sorts before BEGINNER.
- **Relations embedded to the depth the template traverses**, never id-only.
- **Nothing pre-formatted.** `web` owns presentation.

## Consequences

**Good.** The schema can change without touching `web`, as long as the JSON
contract holds. The contract is tested from both sides: the api's tests assert
payload shape, and `web`'s fixtures consume that shape with no database present.

**Costly.** Every read is an HTTP call. Rendering one page can mean three.
`api_client.py` exists solely to make that survivable — one place for timeouts,
error translation and the bearer token.

**The failure mode it created.** `current_user` is no longer an ORM object but a
`SessionUser` wrapping JSON. Attribute access falls through to the payload, so
templates were unchanged — except `role`, which must be coerced to a real enum,
because every route guard compares `current_user.role == Role.PARENT` and a dict
never equals an enum. That comparison fails silently and locks out every user.

**What it did not solve.** Owning the database is not the same as protecting it.
Every endpoint was authenticated long before any was authorised, and for a while
a parent's token could change an administrator's password. Single ownership
concentrates the data behind one service; it does not decide who may read what.
That needed `app/api/authz.py` and 27 tests written from the attacker's side.
