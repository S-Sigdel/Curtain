# Failure Modes

This document describes what currently happens when major parts of the system fail.

## Redis Unavailable

Impact:

- `POST /urls` cannot generate a new short code

Behavior:

- the app returns `503 Service Unavailable`
- response body is JSON:

```json
{
  "error": "Short URL generation is temporarily unavailable."
}
```

Notes:

- URL records that already exist in PostgreSQL remain readable
- no fallback random generator is used

## PostgreSQL Unavailable

Impact:

- URL creation, listing, reads, updates, event listing, and analytics cannot complete
- requests depending on database access will fail

Behavior:

- the app may return `500 Internal server error` for unhandled database failures
- no degraded read-only mode is implemented

Notes:

- PostgreSQL is the source of truth for URL mappings

## Unknown URL Resource

Impact:

- the requested URL record cannot be resolved

Behavior:

- the app returns `404`
- response body:

```json
{
  "error": "URL not found"
}
```

## Invalid Client Input

Examples:

- missing `original_url`
- malformed JSON body
- invalid foreign key such as a non-existent `user_id`

Behavior:

- the app returns `400`
- response body contains an `error` message

## App Process Crash

Behavior:

- Docker Compose is configured with `restart: unless-stopped` for the `app` service
- if the app container is killed, Docker will start it again automatically

Recommended demo:

```bash
docker compose exec app sh -lc 'kill -9 1'
docker ps --filter name=pe-hackathon-template-2026-app-1
curl http://localhost:5000/health
```

Expected outcome:

- Docker restarts the crashed `app` container automatically
- `/health` returns `200 OK`

## Operational Notes

- Redis is currently used for counter-based short-code generation
- PostgreSQL stores the durable URL records
