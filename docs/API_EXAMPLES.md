# API Examples

These examples assume the app is running on `http://localhost:5000`.

## Health Check

```bash
curl -i http://localhost:5000/health
```

## Create a Short URL

```bash
curl -i -X POST http://localhost:5000/apis/url/shorten \
  -H "Content-Type: application/json" \
  -d '{"long_url":"https://www.wikipedia.org/"}'
```

Example response:

```json
{
  "short_url": "000001"
}
```

## Create a Short URL With Metadata

```bash
curl -i -X POST http://localhost:5000/apis/url/shorten \
  -H "Content-Type: application/json" \
  -d '{
    "long_url":"https://www.wikipedia.org/",
    "title":"Wikipedia",
    "user_id": 1
  }'
```

## Redirect a Short URL

Replace `<short_code>` with the value returned by the shorten endpoint.

```bash
curl -i http://localhost:5000/apis/url/<short_code>
```

Expected result:

- `302 Found`
- `Location` header pointing to the original URL

## Error Examples

### Missing `long_url`

```bash
curl -i -X POST http://localhost:5000/apis/url/shorten \
  -H "Content-Type: application/json" \
  -d '{}'
```

### Malformed JSON

```bash
curl -i -X POST http://localhost:5000/apis/url/shorten \
  -H "Content-Type: application/json" \
  -d '{"long_url": '
```

### Invalid `user_id`

```bash
curl -i -X POST http://localhost:5000/apis/url/shorten \
  -H "Content-Type: application/json" \
  -d '{"long_url":"https://www.wikipedia.org/","user_id":999999}'
```

### Missing Short URL

```bash
curl -i http://localhost:5000/apis/url/doesnotexist
```

### Unknown Route

```bash
curl -i http://localhost:5000/does-not-exist
```

### Redis Unavailable During Short-Code Generation

```bash
docker compose stop redis
curl -i -X POST http://localhost:5000/apis/url/shorten \
  -H "Content-Type: application/json" \
  -d '{"long_url":"https://www.wikipedia.org/"}'
docker compose start redis
```
