# Error Handling

This document describes the JSON error responses returned by the app.

## Response Shape

Errors are returned as JSON objects with an `error` field:

```json
{
  "error": "message here"
}
```

## Current Behaviors

### 400 Bad Request

Returned when the request is syntactically acceptable but invalid for the endpoint logic.

Examples:

- `POST /apis/url/shorten` without `long_url`
- malformed JSON that results in no usable `long_url`
- database integrity failures such as an invalid `user_id`

Typical response:

```json
{
  "error": "Field 'long_url' is required"
}
```

### 404 Not Found

Returned when the route or short URL does not exist.

Examples:

- unknown application route
- inactive or missing short code

Typical responses:

```json
{
  "error": "Not found"
}
```

```json
{
  "error": "Short URL not found"
}
```

### 500 Internal Server Error

Returned for unhandled exceptions inside the app.

Typical response:

```json
{
  "error": "Internal server error"
}
```

### 503 Service Unavailable

Returned when Redis is unavailable during short-code generation.

Typical response:

```json
{
  "error": "Short URL generation is temporarily unavailable."
}
```

## Notes

- The app is designed to return JSON errors instead of Flask HTML error pages.
- Redirect lookups still fall back to PostgreSQL; Redis is currently used for short-code generation, not redirect caching.
