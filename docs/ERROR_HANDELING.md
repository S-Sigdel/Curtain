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

- `POST /urls` without `original_url`
- malformed JSON that results in no usable `original_url`
- database integrity failures such as an invalid `user_id`
- invalid query parameters such as `GET /urls?user_id=abc`
- invalid query parameters such as `GET /events?url_id=abc`

Typical response:

```json
{
  "error": "Field 'original_url' is required"
}
```

### 404 Not Found

Returned when the route or short URL does not exist.

Examples:

- unknown application route
- missing URL resource ID

Typical responses:

```json
{
  "error": "Not found"
}
```

```json
{
  "error": "URL not found"
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
- Redis is currently used for short-code generation when creating URL rows.
