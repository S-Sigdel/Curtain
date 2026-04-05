# Error Handling

Curtain does not use a single error envelope for every route. The current implementation has two main response shapes.

## Response Shapes

Most routes return:

```json
{
  "error": "message here"
}
```

`/users` validation routes return:

```json
{
  "errors": {
    "field_name": "message here"
  }
}
```

## Current Status Codes

### `400 Bad Request`

Used by URL and event routes for invalid request bodies, invalid query params, and invalid foreign-key references on URL creation.

Examples:

- missing `original_url`
- invalid `user_id` on `POST /urls`
- invalid `url_id` on `GET /events`
- invalid `is_active` on `GET /urls`

### `404 Not Found`

Used for unknown routes and missing resources.

Examples:

- unknown Flask route
- missing URL
- missing event
- disabled `/debug/fail`

### `422 Unprocessable Entity`

Used by `POST /users` and `PUT /users/<id>` validation.

Examples:

- missing `username`
- invalid email format
- duplicate email on user creation

### `500 Internal Server Error`

Used for uncaught exceptions. The app logs the failure and returns:

```json
{
  "error": "Internal server error"
}
```

## Dependency Behavior

- PostgreSQL failures generally surface as `500`
- counter Redis failures during short-code generation fall back to PostgreSQL-based code allocation
- cache Redis failures behave like cache misses
- click-counter shard failures are swallowed in the redirect path so the redirect can still succeed

There is no current `503` path for Redis unavailability in the URL-shortening flow.
