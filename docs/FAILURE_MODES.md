# Failure Modes

This document describes what happens when Curtain receives bad input, loses dependencies, or crashes. It is organized in the same order a caller encounters the app: global behavior first, then each endpoint.

## Global Behavior

### Error Shapes

Curtain does not use one single error envelope for every route.

- Most routes return JSON shaped like:

```json
{
  "error": "message here"
}
```

- `/users` validation errors return JSON shaped like:

```json
{
  "errors": {
    "field_name": "message here"
  }
}
```

### Unknown Routes

If the client calls a route that does not exist, Flask's global `404` handler returns:

```json
{
  "error": "Not found"
}
```

with status `404`.

### Unhandled Exceptions

If a route raises an exception that is not caught locally, Flask's global `500` handler logs the failure and returns:

```json
{
  "error": "Internal server error"
}
```

with status `500`.

### Dependency Outages

- PostgreSQL is the source of truth for users, URLs, and events.
- Redis at `REDIS_URL` is used for short-code counters.
- Redis at `CACHE_REDIS_URL` is used for cache reads and writes.

PostgreSQL failures are not wrapped in a degraded mode. Requests that need the database will generally fail with `500`.

Redis counter failures during URL creation are handled gracefully. The app falls back to generating the next short code from PostgreSQL state.

Redis cache failures are handled gracefully. Cached endpoints behave like cache misses and continue serving from PostgreSQL.

## Endpoint Failure Modes

### `GET /health`

Purpose:
- Liveness check for the Flask app.

Failure behavior:
- If the app process is running, this returns `200` with `{"status":"ok"}`.
- If Nginx is up but both app containers are down, callers will see `502 Bad Gateway` from Nginx instead of JSON from Flask.
- If the app container itself is down and Nginx is bypassed, the connection fails at the transport layer.

### `GET /debug/fail`

Purpose:
- Synthetic incident route used for drills.

Failure behavior:
- If `ENABLE_INCIDENT_DEBUG_ROUTES=false`, this route is intentionally hidden and returns `404` with `{"error":"Not found"}`.
- If `ENABLE_INCIDENT_DEBUG_ROUTES=true`, it raises a runtime error and the global handler returns `500` with `{"error":"Internal server error"}`.

### `GET /`

Purpose:
- Serves the HTML landing page.

Failure behavior:
- Template rendering problems would surface as an unhandled exception and return `500` with `{"error":"Internal server error"}`.
- This route is HTML on success, not JSON.

### `POST /shorten-ui`

Purpose:
- HTML form endpoint for creating URLs from the browser UI.

Handled failures:
- If the submitted URL is missing or invalid, the route returns an HTML fragment with an error message, not JSON.
- If URL creation fails because `user_id` references a non-existent user, the route returns an HTML fragment with the service error message.

Unhandled failures:
- If `user_id` is present but not parseable as an integer, `int(user_id_raw)` raises `ValueError` and the route falls through to the global `500` handler.

Operational note:
- This endpoint does not follow the JSON error shape used by the API routes.

### `POST /users/bulk`

Purpose:
- Bulk import users from uploaded CSV.

Handled failures:
- Missing file upload returns `400` with `{"error":"Field 'file' is required"}`.
- A CSV row missing `username` or `email` returns `400` with `{"error":"CSV rows must include username and email"}`.
- An empty CSV imports nothing and returns `200` with `{"count":0}`.

Partially handled behavior:
- Duplicate rows are ignored because inserts use `on_conflict_ignore()`. The response count reflects only newly inserted rows.

Unhandled failures:
- Invalid `created_at` text raises `ValueError` inside `_parse_created_at` and returns `500` with `{"error":"Internal server error"}`.
- Non-numeric `id` values raise `ValueError` during `int(row["id"])` conversion and return `500`.
- Database failures during insert return `500`.

### `GET /users`

Purpose:
- List users, optionally with pagination.

Handled failures:
- If `page` or `per_page` is provided and either value is less than `1`, the route returns `400` with `{"error":"Pagination parameters must be positive integers"}`.

Current behavior worth knowing:
- Non-integer `page` or `per_page` values are not rejected explicitly. Flask's typed query parsing turns them into `None`, so the route falls back to the unpaginated list unless one of the parsed values becomes a non-positive integer.

Dependency failures:
- Database read failures return `500`.

### `GET /users/<user_id>`

Purpose:
- Fetch a single user.

Handled failures:
- Missing user returns `404` with `{"error":"User not found"}`.

Dependency failures:
- Database read failures return `500`.

### `POST /users`

Purpose:
- Create a user.

Handled failures:
- Non-object or malformed JSON returns `422` with:

```json
{
  "errors": {
    "request": "JSON body must be an object"
  }
}
```

- Missing `username` or `email` returns `422` under the `errors` key.
- Non-string or blank `username` and `email` values return `422`.
- Invalid email format returns `422`.
- Duplicate email returns `422` with `{"errors":{"email":"Field 'email' must be unique"}}`.

Recovery behavior:
- If user creation hits a sequence drift `IntegrityError`, the route attempts to resync the PostgreSQL sequence and retry once.

Unhandled failures:
- Database failures unrelated to the retry path return `500`.

### `PUT /users/<user_id>`

Purpose:
- Update a user partially.

Handled failures:
- Missing user returns `404` with `{"error":"User not found"}`.
- Non-object or malformed JSON returns `422` with an `errors` object.
- Invalid `username` or `email` values return `422`.

Current behavior worth knowing:
- Updating a user's email to an address already used by another user is not pre-checked in the route. A database unique-constraint failure would bubble up as `500`, not a clean validation error.

### `DELETE /users/<user_id>`

Purpose:
- Delete a user while preserving related URLs and events.

Handled failures:
- Missing user returns `404` with `{"error":"User not found"}`.

Current behavior:
- Related `urls.user_id` and `events.user_id` values are set to `null` before the user row is deleted.
- Successful deletion returns `204` with an empty body.

Dependency failures:
- Database transaction failures return `500`.

### `POST /urls`

Purpose:
- Create a short URL through the JSON API.

Handled failures:
- Missing or malformed JSON is treated as `{}` and returns `400` with `{"error":"Field 'original_url' is required"}`.
- Non-object JSON returns `400` with `{"error":"JSON body must be an object"}`.
- Non-string `original_url` returns `400`.
- Blank `original_url` returns `400`.
- Invalid URL format returns `400` with `{"error":"Field 'original_url' must be a valid http or https URL"}`.
- Overlong URLs above 2048 characters return `400`.
- Non-string `title` returns `400`.
- Non-integer `user_id` returns `400`.
- Unknown `user_id` returns `400` with `{"error":"Field 'user_id' must reference an existing user"}`.

Graceful dependency behavior:
- If Redis counter access fails, the route falls back to a PostgreSQL-backed short-code generator and can still return `201`.

Current behavior worth knowing:
- If an active mapping for the same `original_url` already exists, the route returns that existing URL with status `200` instead of creating a second active row.
- On a new URL, the route also writes a `created` event.
- Successful responses include `X-Cache: BYPASS`.

Unhandled failures:
- Database failures outside the handled `IntegrityError` cases return `500`.

### `GET /urls`

Purpose:
- List URLs, optionally filtered by `user_id` and `is_active`.

Handled failures:
- Invalid `user_id` query string returns `400` with `{"error":"Query parameter 'user_id' must be an integer"}`.
- Invalid `is_active` text returns `400` with `{"error":"Query parameter 'is_active' must be true or false"}`.

Graceful dependency behavior:
- Cache Redis failures are ignored. The route reads directly from PostgreSQL and still responds.

Current behavior:
- Cache hits include `X-Cache: HIT`.
- Cache misses include `X-Cache: MISS`.

Unhandled failures:
- Database read failures return `500`.

### `GET /urls/<url_id>`

Purpose:
- Fetch a single URL by numeric ID.

Handled failures:
- Missing URL returns `404` with `{"error":"URL not found"}`.

Graceful dependency behavior:
- Cache Redis failures are ignored and the route falls back to PostgreSQL.

Current behavior:
- Cache hits include `X-Cache: HIT`.
- Cache misses include `X-Cache: MISS`.

Unhandled failures:
- Database read failures return `500`.

### `PUT /urls/<url_id>`

Purpose:
- Update URL metadata and activation state.

Handled failures:
- Missing URL returns `404` with `{"error":"URL not found"}`.
- Non-object or malformed JSON returns `400` with `{"error":"JSON body must be an object"}`.
- Unknown fields return `400` with `{"error":"Field '<name>' cannot be updated"}`.
- Non-string `title` returns `400`.
- Non-boolean `is_active` returns `400`.

Current behavior:
- Only `title` and `is_active` can be changed.
- Successful updates create an `updated` event and invalidate cached URL and analytics entries.
- Successful responses include `X-Cache: BYPASS`.

Unhandled failures:
- Database write failures return `500`.

### `DELETE /urls/<url_id>`

Purpose:
- Delete a URL and its related events.

Handled failures:
- Missing URL returns `404` with `{"error":"URL not found"}`.

Current behavior:
- Related `events` rows are deleted before the URL row is deleted.
- Successful deletion returns `204` with an empty body.

Unhandled failures:
- Database transaction failures return `500`.

### `GET /r/<short_code>`
### `GET /urls/short/<short_code>`
### `GET /urls/<short_code>/redirect`

Purpose:
- Redirect a short code to its original URL.

Handled failures:
- Missing short code returns `404` with `{"error":"URL not found"}`.
- Inactive URLs are treated the same as missing URLs because the lookup filters on `is_active == true`.

Current behavior:
- Successful requests return `302` with `Location: <original_url>`.
- Successful redirects create a `redirect` event.
- Failed redirects do not create an event because the lookup exits early.

Unhandled failures:
- Database read failures or event-write failures return `500`.

### `GET /events`

Purpose:
- List events, optionally filtered by URL, user, and event type.

Handled failures:
- Invalid `url_id` query string returns `400` with `{"error":"Query parameter 'url_id' must be an integer"}`.
- Invalid `user_id` query string returns `400` with `{"error":"Query parameter 'user_id' must be an integer"}`.

Current behavior:
- `event_type` is matched exactly as provided and is not normalized.
- Event `details` are deserialized from stored JSON when possible.

Unhandled failures:
- Database read failures return `500`.

### `GET /events/<event_id>`

Purpose:
- Fetch a single event.

Handled failures:
- Missing event returns `404` with `{"error":"Event not found"}`.

Unhandled failures:
- Database read failures return `500`.

### `POST /events`

Purpose:
- Create an event manually.

Handled failures:
- Non-object or malformed JSON returns `400` with `{"error":"JSON body must be an object"}`.
- Missing `event_type` returns `400`.
- Blank or non-string `event_type` returns `400` with `{"error":"Field 'event_type' must be a non-empty string"}`.
- Missing `url_id` returns `400`.
- Non-integer `url_id` returns `400`.
- Non-integer `user_id` returns `400`.
- Non-object `details` returns `400` with `{"error":"Field 'details' must be a JSON object"}`.
- Unknown URL returns `404` with `{"error":"URL not found"}`.
- Unknown user returns `404` with `{"error":"User not found"}`.

Current behavior:
- `event_type` is trimmed before persistence.
- `details` is stored as JSON text or `null`.
- Successful creation invalidates the analytics cache for that URL.

Unhandled failures:
- Database write failures return `500`.

### `GET /urls/<url_id>/analytics`

Purpose:
- Return aggregate counts for a single URL.

Handled failures:
- Missing URL returns `404` with `{"error":"URL not found"}`.

Graceful dependency behavior:
- Cache Redis failures are ignored and analytics are recomputed from PostgreSQL.

Current behavior:
- Cache hits include `X-Cache: HIT`.
- Cache misses include `X-Cache: MISS`.
- `latest_event_at` is `null` when the URL has no events.
- `click_count` and `redirect_count` default to `0`.

Unhandled failures:
- Database read failures return `500`.

## Container and Process Failure Modes

### App Process Crash

Docker Compose configures both `app` and `app2` with a restart policy. If an app process dies unexpectedly, Docker attempts to start the container again.

Recommended demo:

```bash
docker compose exec app sh -lc 'kill -9 1'
docker compose ps
curl -i http://localhost:5000/health
```

Expected outcome:

- `app` briefly restarts
- Nginx can still serve traffic through the other app container while restart is happening
- `/health` returns `200` once at least one healthy upstream is available

### Both App Containers Down

If both `app` and `app2` are unavailable while `nginx` is still up, callers see `502 Bad Gateway` from Nginx. This is the primary user-visible symptom for a total app-tier outage in Docker.

### PostgreSQL Down

If PostgreSQL is unavailable:

- any route that touches the database can fail
- the common response is `500` with `{"error":"Internal server error"}`
- there is no read-only fallback mode

### Counter Redis Down

If `REDIS_URL` is unavailable:

- `POST /urls` and `/shorten-ui` can still create URLs
- short-code generation falls back to the next PostgreSQL row ID
- callers should still receive success unless a separate database error occurs

### Cache Redis Down

If `CACHE_REDIS_URL` is unavailable:

- `GET /urls`
- `GET /urls/<id>`
- `GET /urls/<id>/analytics`

continue to work, but all requests behave like cache misses.
