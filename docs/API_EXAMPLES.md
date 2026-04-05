# API Examples

These examples assume the stack is exposed through Nginx on `http://localhost:5000`.

## Health and Metrics

```bash
curl -i http://localhost:5000/health
curl -i http://localhost:5000/metrics
```

## Users

Create a user:

```bash
curl -i -X POST http://localhost:5000/users \
  -H "Content-Type: application/json" \
  -d '{"username":"newuser","email":"newuser@example.com"}'
```

List users:

```bash
curl -i http://localhost:5000/users
curl -i "http://localhost:5000/users?page=1&per_page=20"
```

Bulk import users:

```bash
curl -i -X POST http://localhost:5000/users/bulk \
  -F "file=@users.csv"
```

## URLs

Create a URL:

```bash
curl -i -X POST http://localhost:5000/urls \
  -H "Content-Type: application/json" \
  -d '{"user_id":1,"original_url":"https://example.com/test","title":"Test URL"}'
```

List and fetch URLs:

```bash
curl -i http://localhost:5000/urls
curl -i "http://localhost:5000/urls?user_id=1&is_active=true"
curl -i http://localhost:5000/urls/1
```

Update a URL:

```bash
curl -i -X PUT http://localhost:5000/urls/1 \
  -H "Content-Type: application/json" \
  -d '{"title":"Updated Title","is_active":false}'
```

Redirect by short code:

```bash
curl -i http://localhost:5000/r/000001
curl -i http://localhost:5000/urls/short/000001
curl -i http://localhost:5000/urls/000001/redirect
```

## Events and Analytics

Create an event:

```bash
curl -i -X POST http://localhost:5000/events \
  -H "Content-Type: application/json" \
  -d '{"url_id":1,"user_id":1,"event_type":"click","details":{"source":"manual"}}'
```

List events and analytics:

```bash
curl -i http://localhost:5000/events
curl -i "http://localhost:5000/events?url_id=1&user_id=1&event_type=created"
curl -i http://localhost:5000/urls/1/analytics
```

## Error Examples

Missing `original_url`:

```bash
curl -i -X POST http://localhost:5000/urls \
  -H "Content-Type: application/json" \
  -d '{}'
```

Invalid `user_id`:

```bash
curl -i -X POST http://localhost:5000/urls \
  -H "Content-Type: application/json" \
  -d '{"original_url":"https://www.wikipedia.org/","user_id":999999}'
```

Unknown route:

```bash
curl -i http://localhost:5000/does-not-exist
```
