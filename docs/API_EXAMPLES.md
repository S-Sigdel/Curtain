# API Examples

These examples assume the app is running on `http://localhost:5000`.

## Health Check

```bash
curl -i http://localhost:5000/health
```

## Create a URL

```bash
curl -i -X POST http://localhost:5000/urls \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": 1,
    "original_url": "https://example.com/test",
    "title": "Test URL"
  }'
```

## List URLs

```bash
curl -i http://localhost:5000/urls
curl -i "http://localhost:5000/urls?user_id=1"
```

## Get URL By ID

```bash
curl -i http://localhost:5000/urls/1
```

## Update a URL

```bash
curl -i -X PUT http://localhost:5000/urls/1 \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Updated Title",
    "is_active": false
  }'
```

## List Events

```bash
curl -i http://localhost:5000/events
curl -i "http://localhost:5000/events?url_id=1&user_id=1&event_type=created"
```

## URL Analytics

```bash
curl -i http://localhost:5000/urls/1/analytics
```

## Error Examples

### Missing `original_url`

```bash
curl -i -X POST http://localhost:5000/urls \
  -H "Content-Type: application/json" \
  -d '{}'
```

### Malformed JSON

```bash
curl -i -X POST http://localhost:5000/urls \
  -H "Content-Type: application/json" \
  -d '{"original_url": '
```

### Invalid `user_id`

```bash
curl -i -X POST http://localhost:5000/urls \
  -H "Content-Type: application/json" \
  -d '{"original_url":"https://www.wikipedia.org/","user_id":999999}'
```

### Missing URL Resource

```bash
curl -i http://localhost:5000/urls/999999
```

### Missing Analytics Resource

```bash
curl -i http://localhost:5000/urls/999999/analytics
```

### Unknown Route

```bash
curl -i http://localhost:5000/does-not-exist
```

### Redis Unavailable During Short-Code Generation

```bash
docker compose stop redis
curl -i -X POST http://localhost:5000/urls \
  -H "Content-Type: application/json" \
  -d '{"original_url":"https://www.wikipedia.org/"}'
docker compose start redis
```
